"""Polymarket public-API signal fetcher for the TradingAgents dashboard.

Read-only, no auth, no account required. Pulls active markets from the Gamma API,
keeps only macro / geopolitics / AI markets that are useful as a global
"sentiment thermometer" for mid-term A-share swing trading, and tags each by
topic. Probability time series (for the trend chart) comes from the CLOB
prices-history endpoint.

Everything here is public market data — nothing places trades.
Verified against the live API on 2026-05-29.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
CLOB_HISTORY_URL = "https://clob.polymarket.com/prices-history"

# Snapshot path for TradingAgents-CN
_SNAPSHOT_DIR = Path(os.getenv("TRADINGAGENTS_DATA_DIR", "data")) / "pulse"


def _snapshot_path() -> Path:
    return _SNAPSHOT_DIR / "polymarket_snapshot.json"


_TTL_SECONDS = 300  # 5 min cache — respect Polymarket rate limits
_CACHE: dict[str, tuple[float, Any]] = {}

# Some events spawn dozens of near-duplicate markets (e.g. the Iran situation:
# many "US-Iran peace deal by <date>" variants). Keep only the N largest of
# each flood-prone cluster so the panel stays a thermometer, not a wall of dupes.
CLUSTER_CAPS: dict[str, int] = {"iran": 4, "world cup": 8}

# 决定每个 cluster 保留哪 N 个时的排序依据（默认 volume_24h）。
CLUSTER_RANK_KEY: dict[str, str] = {"world cup": "prob_yes"}

# 每个分类整体最多展示 N 个
TOPIC_CAPS: dict[str, int] = {"体育": 6, "加密": 6, "政治选举": 6}


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
        logger.warning("polymarket snapshot save failed: %s", exc)


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_json_field(raw: Any, default: Any) -> Any:
    """Gamma returns some array fields as JSON-encoded strings."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return default
    return raw if raw is not None else default


def _cap_clusters(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cap flood-prone clusters to their top-N."""
    def cluster_of(market: dict[str, Any]) -> str | None:
        q = (market.get("question") or "").lower()
        for keyword in CLUSTER_CAPS:
            if keyword in q:
                return keyword
        return None

    capped: dict[str, list[dict[str, Any]]] = {}
    kept: list[dict[str, Any]] = []
    for market in markets:
        kw = cluster_of(market)
        if kw is None:
            kept.append(market)
        else:
            capped.setdefault(kw, []).append(market)

    for kw, group in capped.items():
        rank_key = CLUSTER_RANK_KEY.get(kw, "volume_24h")
        group.sort(key=lambda m: m.get(rank_key) or 0.0, reverse=True)
        kept.extend(group[: CLUSTER_CAPS[kw]])

    kept.sort(key=lambda m: m.get("volume_24h") or 0.0, reverse=True)
    return kept


def _cap_topics(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Limit each topic to its top-N by 24h volume."""
    ordered = sorted(markets, key=lambda m: m.get("volume_24h") or 0.0, reverse=True)
    counts: dict[str, int] = {}
    kept: list[dict[str, Any]] = []
    for market in ordered:
        topic = market.get("topic")
        cap = TOPIC_CAPS.get(topic)
        if cap is not None:
            counts[topic] = counts.get(topic, 0) + 1
            if counts[topic] > cap:
                continue
        kept.append(market)
    return kept


def _shape(market: dict[str, Any], topic: str) -> dict[str, Any]:
    outcomes = _parse_json_field(market.get("outcomes"), [])
    prices = _parse_json_field(market.get("outcomePrices"), [])
    token_ids = _parse_json_field(market.get("clobTokenIds"), [])
    return {
        "question": market.get("question"),
        "question_zh": None,  # Disabled translation for initial version
        "topic": topic,
        "outcomes": outcomes,
        "prices": [_safe_float(p) for p in prices],
        "prob_yes": _safe_float(prices[0]) if prices else None,
        "change_24h": _safe_float(market.get("oneDayPriceChange")),
        "change_7d": _safe_float(market.get("oneWeekPriceChange")),
        "volume_24h": _safe_float(market.get("volume24hr")),
        "liquidity": _safe_float(market.get("liquidity")),
        "end_date": market.get("endDateIso") or market.get("endDate"),
        "slug": market.get("slug"),
        "token_id_yes": token_ids[0] if token_ids else None,
        "source": "polymarket",
    }


async def pull_raw_markets(pages: int = 3, force: bool = False) -> list[dict[str, Any]]:
    """Raw Gamma markets (top pages x 100 by 24h volume), deduped by id."""
    cache_key = f"markets:{pages}"
    raw = None if force else _cache_get(cache_key)
    if raw is not None:
        return raw
    raw = []
    seen_ids: set[str] = set()
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (TradingAgents-CN)"}
    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        for page in range(pages):
            params = {
                "active": "true",
                "closed": "false",
                "limit": "100",
                "offset": str(page * 100),
                "order": "volume24hr",
                "ascending": "false",
            }
            resp = await client.get(GAMMA_MARKETS_URL, params=params)
            resp.raise_for_status()
            batch = resp.json()
            if not isinstance(batch, list):
                batch = batch.get("data", []) if isinstance(batch, dict) else []
            if not batch:
                break
            for market in batch:
                mid = market.get("id")
                if mid not in seen_ids:
                    seen_ids.add(mid)
                    raw.append(market)
    _cache_set(cache_key, raw)
    return raw


async def fetch_markets(pages: int = 3, force: bool = False) -> list[dict[str, Any]]:
    """Active macro/geo/AI markets, tagged by topic, sorted by 24h volume."""
    # Normal load → serve the pinned snapshot (instant)
    if not force:
        snapshot = _load_snapshot()
        if snapshot is not None:
            return snapshot

    from tradingagents.pulse.market_taxonomy import classify

    raw = await pull_raw_markets(pages=pages, force=force)

    shaped: list[dict[str, Any]] = []
    for market in raw:
        question = market.get("question") or ""
        topic = classify(question)
        if topic == "其他":
            continue  # Skip irrelevant markets
        shaped.append(_shape(market, topic))

    shaped = _cap_clusters(shaped)
    shaped = _cap_topics(shaped)

    # Pin this fresh set so subsequent normal loads are instant
    _save_snapshot(shaped)
    return shaped


async def fetch_history(token_id: str, interval: str = "1w", fidelity: int = 720) -> list[dict[str, Any]]:
    """Probability time series for one outcome token (for the trend chart)."""
    cache_key = f"history:{token_id}:{interval}:{fidelity}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    params = {"market": token_id, "interval": interval, "fidelity": str(fidelity)}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(CLOB_HISTORY_URL, params=params, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
    history = data.get("history", []) if isinstance(data, dict) else []
    points = [{"t": p.get("t"), "p": _safe_float(p.get("p"))} for p in history]
    _cache_set(cache_key, points)
    return points