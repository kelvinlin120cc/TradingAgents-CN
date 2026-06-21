"""Global macro probability panel API router.

Provides endpoints for the Polymarket + Kalshi probability overview panel.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from tradingagents.pulse.market_pulse import fetch_overview
from tradingagents.pulse.polymarket_signals import fetch_history

router = APIRouter(prefix="/pulse", tags=["Global Macro Probability"])


@router.get("/overview")
async def get_pulse_overview(refresh: bool = Query(False, description="Force refresh from sources")):
    """全球宏观预期概率面板
    
    Returns module-grouped probability data from Polymarket + Kalshi.
    Normal loads serve cached snapshot instantly; refresh=True triggers background rebuild.
    """
    try:
        return await fetch_overview(force=refresh)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market pulse fetch failed: {exc}")


@router.get("/polymarket/history")
async def get_polymarket_history(
    token_id: str = Query(..., description="Polymarket outcome token ID"),
    interval: str = Query("1w", description="Time interval: 1d, 1w, 1m, max")
):
    """Polymarket 概率历史趋势
    
    Returns probability time series for a single outcome token (for trend charts).
    """
    try:
        history = await fetch_history(token_id=token_id, interval=interval)
        return {"token_id": token_id, "interval": interval, "history": history}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Polymarket history fetch failed: {exc}")