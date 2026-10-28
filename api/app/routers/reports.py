from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app import recommender, reports
from app.cache import make_key
from app.config import get_settings
from app.db import get_db
from app.deps import get_cache
from app.models import Channel
from app.routers.accounts import get_account_or_404
from app.schemas import (
    CampaignPerformanceRow,
    ChannelMixReport,
    RecommendationRequest,
    RecommendationResponse,
    TrendReport,
)

router = APIRouter(prefix="/accounts/{account_id}", tags=["reports"])


def _window(start: date | None, end: date | None, default_days: int = 30) -> tuple[date, date]:
    end = end or date.today()
    start = start or end - timedelta(days=default_days - 1)
    return start, end


def _cached(cache, account_id: int, name: str, params: dict, response: Response, compute):
    key = make_key(account_id, name, params)
    hit = cache.get(key)
    if hit is not None:
        response.headers["X-Cache"] = "HIT"
        return hit
    data = compute()
    cache.set(key, data, get_settings().cache_ttl_seconds, account_id)
    response.headers["X-Cache"] = "MISS"
    return data


@router.get("/reports/channel-mix", response_model=ChannelMixReport)
def channel_mix_report(
    account_id: int,
    response: Response,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    get_account_or_404(db, account_id)
    start, end = _window(start, end)
    params = {"start": start, "end": end}
    return _cached(
        cache,
        account_id,
        "channel_mix",
        params,
        response,
        lambda: _jsonable(reports.channel_mix(db, account_id, start, end)),
    )


@router.get("/reports/trend", response_model=TrendReport)
def trend_report(
    account_id: int,
    response: Response,
    start: date | None = None,
    end: date | None = None,
    group_by: str = Query(default="channel", pattern="^(channel|total)$"),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    get_account_or_404(db, account_id)
    start, end = _window(start, end)
    params = {"start": start, "end": end, "group_by": group_by}
    return _cached(
        cache,
        account_id,
        "trend",
        params,
        response,
        lambda: _jsonable(reports.trend(db, account_id, start, end, group_by)),
    )


@router.get("/reports/campaigns", response_model=list[CampaignPerformanceRow])
def campaign_report(
    account_id: int,
    response: Response,
    start: date | None = None,
    end: date | None = None,
    channel: Channel | None = None,
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    get_account_or_404(db, account_id)
    start, end = _window(start, end)
    ch = channel.value if channel else None
    params = {"start": start, "end": end, "channel": ch}
    return _cached(
        cache,
        account_id,
        "campaigns",
        params,
        response,
        lambda: reports.campaign_performance(db, account_id, start, end, ch),
    )


@router.post("/recommendations/budget", response_model=RecommendationResponse)
def budget_recommendation(
    account_id: int,
    payload: RecommendationRequest,
    response: Response,
    end: date | None = None,
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    get_account_or_404(db, account_id)
    end = end or date.today()
    start = end - timedelta(days=payload.lookback_days - 1)
    params = {**payload.model_dump(mode="json"), "start": start, "end": end}

    def compute():
        history = reports.channel_history(db, account_id, start, end)
        rec = recommender.recommend(
            history,
            float(payload.total_budget) if payload.total_budget else None,
            min_share=payload.min_share,
            max_shift_pct=payload.max_shift_pct,
        )
        return {
            "account_id": account_id,
            "lookback_days": payload.lookback_days,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            **rec,
        }

    return _cached(cache, account_id, "recommendation", params, response, compute)


def _jsonable(d: dict) -> dict:
    """Make dates JSON/Redis friendly (pydantic parses ISO strings back on the way out)."""
    out = {}
    for k, v in d.items():
        if isinstance(v, date):
            out[k] = v.isoformat()
        elif isinstance(v, list):
            out[k] = [_jsonable(x) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v
    return out
