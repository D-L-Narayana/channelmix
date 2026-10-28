#!/usr/bin/env python3
"""Seed a throwaway SQLite DB and export API responses as mock JSON for the standalone web demo."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

OUT = ROOT / "web" / "src" / "mock"


def main() -> None:
    with TestClient(app) as client:
        aid = seed(days=90)
        base = f"/api/v1/accounts/{aid}"
        dump = {
            "accounts.json": client.get("/api/v1/accounts").json(),
            "campaigns.json": client.get(f"{base}/campaigns").json(),
            "channel_mix.json": client.get(f"{base}/reports/channel-mix", params={"start": "1900-01-01"}).json(),
            "trend.json": client.get(f"{base}/reports/trend", params={"start": "1900-01-01"}).json(),
            "trend_total.json": client.get(
                f"{base}/reports/trend", params={"start": "1900-01-01", "group_by": "total"}
            ).json(),
            "campaign_report.json": client.get(f"{base}/reports/campaigns", params={"start": "1900-01-01"}).json(),
            "recommendation.json": client.post(
                f"{base}/recommendations/budget", json={"lookback_days": 30, "min_share": 0.05, "max_shift_pct": 0.3}
            ).json(),
        }
        for name, data in dump.items():
            (OUT / name).write_text(json.dumps(data, indent=1, default=str))
            print(f"wrote {name}")


if __name__ == "__main__":
    main()
