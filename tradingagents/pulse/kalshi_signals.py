"""Kalshi public-API signal fetcher for the multi-source probability overview.

Read-only, no auth (market data is public; only trading needs a key). Kalshi is a
US CFTC-regulated venue, so its macro/economics/commodities markets complement
Polymarket's geopolitics/crypto depth.

Kalshi has no server-side volume sort and buries hot markets behind thousands of
dead single-day sports/weather contracts, so we paginate *all* open events
(``with_nested_markets``), sum nested-market volume per event, and rank client-side.

Shapes every event into the same dict schema as ``polymarket_signals`` so the
aggregator can merge the two sources transparently. ``source="kalshi"``.
Verified against the live API on 2026-06-04 (note: price fields are ``*_dollars``).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EVENTS_URL = "https://api.elections.kalshi.com/trade-api/v2/events"

# Snapshot path for TradingAgents-CN
_SNAPSHOT_DIR = Path("/app/data/pulse")


def _snapshot_path() -> Path:
    return _SNAPSHOT_DIR / "kalshi_snapshot.json"


_TTL_SECONDS = 300
_CACHE: dict[str, tuple[float, Any]] = {}
_MAX_PAGES = 30  # 200 events/page; ~6k events
_PAGE_TIMEOUT = 22.0


def _cache_get(key: str) -> Any | None:
    hit = _CACHE.get(key)
    if hit and (time.time() - hit[0]) < _TTL_SECONDS:
        return hit[1]
    return None


def _cache_set(key: str, value: Any) -> None:
    _CACHE[key] = (time.time(), value)


def _load_snapshot() -> list[dict[str, Any]] | None:
    try:
        data = json.loads(_snapshot_path().read_text("utf-8"))
        return data if isinstance(data, list) else None
    except (FileNotFoundError, ValueError, OSError):
        return None


def _save_snapshot(markets: list[dict[str, Any]]) -> None:
    try:
        path = _snapshot_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(markets, ensure_ascii=False), "utf-8")
    except OSError as exc:
        logger.warning("kalshi snapshot save failed: %s", exc)


def _safe_float(value: Any) -> float | None:
    try:
        f = float(value)
        return f
    except (ValueError, TypeError):
        return None


async def pull_raw_events(force: bool = False) -> list[dict[str, Any]]:
    """All open events with nested markets, paginated via cursor. Cached for TTL."""
    cache_key = "events:open"
    cached = None if force else _cache_get(cache_key)
    if cached is not None:
        return cached

    events: list[dict[str, Any]] = []
    cursor = ""
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (TradingAgents-CN)"}
    async with httpx.AsyncClient(timeout=_PAGE_TIMEOUT, headers=headers) as client:
        for page in range(_MAX_PAGES):
            params: dict[str, str] = {
                "limit": "200",
                "status": "open",
                "with_nested_markets": "true",
            }
            if cursor:
                params["cursor"] = cursor
            # Kalshi's TLS/edge is flaky, so retry a page a few times
            data = None
            for attempt in range(3):
                try:
                    resp = await client.get(EVENTS_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("kalshi events page %d attempt %d failed: %s", page, attempt, exc)
                    await asyncio.sleep(1.0 * (attempt + 1))
            if data is None:
                break
            batch = data.get("events", []) if isinstance(data, dict) else []
            if not batch:
                break
            events.extend(batch)
            cursor = data.get("cursor", "") if isinstance(data, dict) else ""
            if not cursor:
                break
    _cache_set(cache_key, events)
    return events


def _market_prob(market: dict[str, Any]) -> float | None:
    return _safe_float(market.get("yes_ask_dollars")) or _safe_float(market.get("last_price_dollars"))


def _shape_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Collapse one Kalshi event (+ nested markets) into the common market schema."""
    from tradingagents.pulse.market_taxonomy import classify

    markets = event.get("markets") or []
    if not markets:
        return None

    multi = len(markets) > 1
    if multi:
        priced = [m for m in markets if _market_prob(m) is not None]
        rep = min(priced or markets, key=lambda m: abs((_market_prob(m) or 0.0) - 0.5))
        pick_label = (rep.get("yes_sub_title") or "").strip() or None
    else:
        rep = markets[0]
        pick_label = None

    vol_24h = sum(_safe_float(m.get("volume_24h_fp")) or 0.0 for m in markets)
    liquidity = sum(_safe_float(m.get("liquidity_dollars")) or 0.0 for m in markets)

    prob_yes = _market_prob(rep)
    last = _safe_float(rep.get("last_price_dollars"))
    prev = _safe_float(rep.get("previous_price_dollars"))
    change_24h = (last - prev) if (last not in (None, 0.0) and prev not in (None, 0.0)) else None

    title = (event.get("title") or "").strip()
    module = classify(title, event.get("category"))

    outcomes = [pick_label or "Yes", "No"]
    prices = [prob_yes, (1 - prob_yes) if prob_yes is not None else None]

    return {
        "question": title,
        "question_zh": None,  # Disabled translation for initial version
        "topic": module,
        "outcomes": outcomes,
        "prices": prices,
        "prob_yes": prob_yes,
        "pick_label": pick_label,
        "change_24h": change_24h,
        "change_7d": None,
        "volume_24h": vol_24h,
        "liquidity": liquidity,
        "end_date": rep.get("close_time") or event.get("close_time"),
        "slug": event.get("event_ticker"),
        "series_ticker": event.get("series_ticker"),
        "token_id_yes": None,
        "source": "kalshi",
        "kalshi_category": event.get("category"),
    }


async def fetch_shaped(force: bool = False) -> list[dict[str, Any]]:
    """Every open event shaped into the common schema, tagged by module."""
    if not force:
        snap = _load_snapshot()
        if snap is not None:
            return snap

    events = await pull_raw_events(force=force)
    shaped: list[dict[str, Any]] = []
    for event in events:
        row = _shape_event(event)
        if row and (row["volume_24h"] or 0) > 0:
            shaped.append(row)
    shaped.sort(key=lambda m: m.get("volume_24h") or 0.0, reverse=True)

    # Never let a failed/empty pull wipe good data
    if not shaped:
        prev = _load_snapshot()
        if prev:
            logger.warning("kalshi pull returned empty; serving previous snapshot (%d events)", len(prev))
            return prev
        return []
    _save_snapshot(shaped)
    return shaped