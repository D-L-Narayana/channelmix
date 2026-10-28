"""Vendored public sample dataset (see app/datasets/SOURCE.md for provenance + licence)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import current_workspace
from app.csv_import import ParsedCSV, parse_csv
from app.db import get_db
from app.deps import get_cache
from app.models import Workspace
from app.routers.imports import commit_parsed
from app.schemas import DatasetInfo, ImportResult

router = APIRouter(prefix="/datasets", tags=["datasets"])

DATA_DIR = Path(__file__).resolve().parent.parent / "datasets"
SAMPLE_FILE = DATA_DIR / "channelmix-sample.csv"

SAMPLE_META = {
    "name": "Online Advertising Digital Marketing data (Company X, Apr-Jun 2020)",
    "source_url": "https://www.kaggle.com/datasets/naniruddhan/online-advertising-digital-marketing-data",
    "license": "MIT",
    "attribution": "Online Advertising Digital Marketing data, published by n. aniruddhan on Kaggle (MIT licence); "
    "converted to ChannelMix's generic CSV (see api/app/datasets/SOURCE.md).",
    "description": "Real daily display-advertising performance of an anonymised advertiser on one ad network: "
    "3 campaigns x 6 publisher placements, 1 Apr - 30 Jun 2020, USD. Spend = what the advertiser paid the "
    "network, revenue = attributed on-site sales (30-day post-click). Single network, so channel = 'other'.",
    "currency": "USD",
}


def sample_bytes() -> bytes:
    return SAMPLE_FILE.read_bytes()


@lru_cache
def sample_parsed() -> ParsedCSV:
    return parse_csv(sample_bytes(), format_override="generic")


@router.get("/sample", summary="Download the sample dataset (generic CSV)")
def download_sample():
    return Response(
        content=sample_bytes(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="channelmix-sample.csv"',
            "X-Dataset-Source": SAMPLE_META["source_url"],
            "X-Dataset-License": SAMPLE_META["license"],
        },
    )


@router.get("/sample/info", response_model=DatasetInfo)
def sample_info():
    p = sample_parsed()
    days = [r["day"] for r in p.rows]
    return {
        **SAMPLE_META,
        "rows": len(p.rows),
        "campaigns": len({(r["channel"], r["external_id"]) for r in p.rows}),
        "channels": sorted({r["channel"].value for r in p.rows}),
        "first_day": min(days),
        "last_day": max(days),
    }


@router.post("/sample/import", response_model=ImportResult, summary="Import the sample dataset into my workspace")
def import_sample(
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    result = commit_parsed(db, ws.id, sample_parsed(), source="sample", filename=SAMPLE_FILE.name)
    db.commit()
    cache.invalidate_workspace(ws.id)
    return result
