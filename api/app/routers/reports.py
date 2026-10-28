from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app import recommender, reports
from app.auth import current_workspace
from app.cache import make_key
from app.config import get_settings
from app.db import get_db
from app.deps import get_cache
from app.models import Channel, Workspace
from app.schemas import (
    CampaignPerformanceRow,
    ChannelMixReport,
    RecommendationRequest,
    RecommendationResponse,
    SummaryReport,
    TrendReport,
)

router = APIRouter(tags=["reports"])


def _window(start: date | None, end: date | None, default_days: int = 30) -> tuple[date, date]:
    end = end or date.today()
    start = start or end - timedelta(days=default_days - 1)
    return start, end


def _cached(cache, ws_id: int, name: str, params: dict, response: Response, compute):
    key = make_key(ws_id, name, params)
    hit = cache.get(key)
    if hit is not None:
        response.headers["X-Cache"] = "HIT"
        return hit
    data = compute()
    cache.set(key, data, get_settings().cache_ttl_seconds, ws_id)
    response.headers["X-Cache"] = "MISS"
    return data


@router.get("/reports/summary", response_model=SummaryReport)
def summary_report(
    response: Response,
    start: date | None = None,
    end: date | None = None,
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    start, end = _window(start, end)
    return _cached(
        cache, ws.id, "summary", {"start": start, "end": end}, response,
        lambda: _jsonable(reports.summary(db, ws.id, start, end)),
    )


@router.get("/reports/by-channel", response_model=ChannelMixReport)
def by_channel_report(
    response: Response,
    start: date | None = None,
    end: date | None = None,
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    start, end = _window(start, end)
    return _cached(
        cache, ws.id, "by_channel", {"start": start, "end": end}, response,
        lambda: _jsonable(reports.channel_mix(db, ws.id, start, end)),
    )


@router.get("/reports/trend", response_model=TrendReport)
def trend_report(
    response: Response,
    start: date | None = None,
    end: date | None = None,
    group_by: str = Query(default="channel", pattern="^(channel|total)$"),
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    start, end = _window(start, end)
    return _cached(
        cache, ws.id, "trend", {"start": start, "end": end, "group_by": group_by}, response,
        lambda: _jsonable(reports.trend(db, ws.id, start, end, group_by)),
    )


@router.get("/reports/campaigns", response_model=list[CampaignPerformanceRow])
def campaign_report(
    response: Response,
    start: date | None = None,
    end: date | None = None,
    channel: Channel | None = None,
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    start, end = _window(start, end)
    ch = channel.value if channel else None
    return _cached(
        cache, ws.id, "campaigns", {"start": start, "end": end, "channel": ch}, response,
        lambda: reports.campaign_performance(db, ws.id, start, end, ch),
    )


def _recommend(req: RecommendationRequest, response: Response, ws: Workspace, db: Session, cache):
    end = req.end or date.today()
    start = end - timedelta(days=req.lookback_days - 1)
    params = {**req.model_dump(mode="json"), "start": start, "end": end}

    def compute():
        history = reports.channel_history(db, ws.id, start, end)
        rec = recommender.recommend(
            history,
            float(req.total_budget) if req.total_budget else None,
            min_share=req.min_share,
            max_shift_pct=req.max_shift_pct,
        )
        return {
            "lookback_days": req.lookback_days,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            **rec,
        }

    return _cached(cache, ws.id, "recommendation", params, response, compute)


@router.get("/recommendations", response_model=RecommendationResponse, tags=["recommendations"])
def recommendations(
    response: Response,
    total_budget: Decimal | None = Query(default=None, gt=0),
    lookback_days: int = Query(default=30, ge=7, le=365),
    min_share: float = Query(default=0.05, ge=0, lt=0.5),
    max_shift_pct: float | None = Query(default=None, ge=0, le=1),
    end: date | None = None,
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    req = RecommendationRequest(
        total_budget=total_budget, lookback_days=lookback_days, min_share=min_share, max_shift_pct=max_shift_pct, end=end
    )
    return _recommend(req, response, ws, db, cache)


@router.post("/recommendations/budget", response_model=RecommendationResponse, tags=["recommendations"])
def budget_recommendation(
    payload: RecommendationRequest,
    response: Response,
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    return _recommend(payload, response, ws, db, cache)


def _jsonable(d: dict) -> dict:
    """Make dates JSON/Redis friendly (pydantic parses ISO strings back on the way out)."""
    out = {}
    for k, v in d.items():
        if isinstance(v, date):
            out[k] = v.isoformat()
        elif isinstance(v, dict):
            out[k] = _jsonable(v)
        elif isinstance(v, list):
            out[k] = [_jsonable(x) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v
    return out
