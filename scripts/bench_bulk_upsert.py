#!/usr/bin/env python3
"""Benchmark the idempotent bulk upsert path with 50k daily_metrics rows.

Usage (from repo root, with api/.venv active):
    DATABASE_URL=sqlite:////tmp/bench.db python scripts/bench_bulk_upsert.py
    DATABASE_URL=postgresql+psycopg://postgres:ci@localhost:5432/channelmix python scripts/bench_bulk_upsert.py

Phases measured:
  1. cold insert   - 50k brand-new rows (all INSERT branch of ON CONFLICT)
  2. warm upsert   - the same 50k rows with changed spend (all UPDATE branch)
  3. HTTP end-to-end - one 10k-row POST /metrics/bulk through FastAPI (validation + upsert)
"""

from __future__ import annotations

import os
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

ROWS = int(os.environ.get("BENCH_ROWS", "50000"))
CAMPAIGNS = 50
DAYS = ROWS // CAMPAIGNS


def main() -> None:
    from sqlalchemy import func, select
    from sqlalchemy.orm import sessionmaker

    from app.auth import generate_api_key, hash_api_key
    from app.config import get_settings
    from app.db import Base, init_db, make_engine
    from app.ingest import upsert_metrics
    from app.models import Campaign, Channel, Workspace

    url = get_settings().database_url
    engine = make_engine(url)
    Base.metadata.drop_all(engine)
    init_db(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    rng = random.Random(1)

    with Session() as db:
        api_key = generate_api_key()
        acc = Workspace(slug="bench", name="bench", email="bench@example.com", api_key_hash=hash_api_key(api_key))
        db.add(acc)
        db.flush()
        camps = [
            Campaign(workspace_id=acc.id, channel=list(Channel)[i % 3], external_id=f"c{i}", name=f"c{i}")
            for i in range(CAMPAIGNS)
        ]
        db.add_all(camps)
        db.commit()
        camp_ids = [c.id for c in camps]

    end = date(2024, 12, 31)
    rows = []
    for cid in camp_ids:
        for d in range(DAYS):
            s = rng.uniform(50, 500)
            rows.append(
                {
                    "campaign_id": cid,
                    "day": end - timedelta(days=d),
                    "impressions": rng.randint(1000, 50000),
                    "clicks": rng.randint(10, 1000),
                    "conversions": rng.randint(0, 50),
                    "spend": round(s, 2),
                    "revenue": round(s * rng.uniform(0.5, 5), 2),
                }
            )
    print(f"backend={engine.dialect.name} rows={len(rows):,}")

    with Session() as db:
        t0 = time.perf_counter()
        upsert_metrics(db, rows)
        db.commit()
        cold = time.perf_counter() - t0
    print(f"cold insert : {cold:6.2f}s  ({len(rows) / cold:,.0f} rows/s)")

    for r in rows:
        r["spend"] = round(r["spend"] * 1.1, 2)
    with Session() as db:
        t0 = time.perf_counter()
        upsert_metrics(db, rows)
        db.commit()
        warm = time.perf_counter() - t0
    print(f"warm upsert : {warm:6.2f}s  ({len(rows) / warm:,.0f} rows/s)")

    # HTTP end-to-end with a 10k-row payload
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    payload = {"rows": [{**r, "day": r["day"].isoformat()} for r in rows[:10_000]]}
    with TestClient(app) as client:
        t0 = time.perf_counter()
        hdr = {"Idempotency-Key": "bench-1", "X-Api-Key": api_key}
        resp = client.post("/api/v1/metrics/bulk", json=payload, headers=hdr)
        http = time.perf_counter() - t0
        assert resp.status_code == 200, resp.text
        t0 = time.perf_counter()
        client.post("/api/v1/metrics/bulk", json=payload, headers=hdr)
        replay = time.perf_counter() - t0
    print(f"http 10k    : {http:6.2f}s  ({10_000 / http:,.0f} rows/s incl. validation)")
    print(f"idem replay : {replay * 1000:6.1f}ms (same key, no write)")

    with engine.connect() as conn:
        from app.models import DailyMetric

        n = conn.execute(select(func.count()).select_from(DailyMetric)).scalar()
    print(f"rows in table after all phases: {n:,} (no duplicates)")
    assert n == len(rows)


if __name__ == "__main__":
    main()
