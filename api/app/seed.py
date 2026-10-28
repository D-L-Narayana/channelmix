"""Seed a demo account with 90 days of synthetic Google / Meta / Amazon data.

Usage: python -m app.seed  (uses DATABASE_URL)
"""

import random
from datetime import date, timedelta

from app.db import SessionLocal, init_db
from app.models import Account, Campaign, Channel
from app.routers.metrics import upsert_metrics

PROFILES = {  # base ROAS, concavity, daily spend range
    Channel.google: (4.2, 0.85, (900, 1400)),
    Channel.meta: (2.1, 0.75, (700, 1300)),
    Channel.amazon: (3.0, 0.80, (400, 800)),
}


def seed(days: int = 90, seed: int = 7) -> int:
    rng = random.Random(seed)
    init_db()
    with SessionLocal() as db:
        acc = Account(name="Acme Retail", currency="USD")
        db.add(acc)
        db.flush()
        rows = []
        end = date.today()
        for ch, (roas, b, (lo, hi)) in PROFILES.items():
            for i in range(1, 4):
                camp = Campaign(
                    account_id=acc.id,
                    channel=ch,
                    external_id=f"{ch.value}-{i}",
                    name=f"{ch.value.title()} {['Brand', 'Prospecting', 'Retargeting'][i - 1]}",
                    daily_budget=(lo + hi) / 2 / 3,
                )
                db.add(camp)
                db.flush()
                for d in range(days):
                    day = end - timedelta(days=days - 1 - d)
                    weekend = 0.8 if day.weekday() >= 5 else 1.0
                    ref = (lo + hi) / 2 / 3  # mean per-campaign spend; ROAS == profile ROAS at the mean
                    spend = rng.uniform(lo, hi) / 3 * weekend
                    revenue = roas * ref * (spend / ref) ** b * rng.uniform(0.85, 1.15)
                    clicks = int(spend / rng.uniform(0.6, 1.4))
                    rows.append(
                        {
                            "campaign_id": camp.id,
                            "day": day,
                            "spend": round(spend, 2),
                            "revenue": round(revenue, 2),
                            "clicks": clicks,
                            "impressions": int(clicks / rng.uniform(0.01, 0.03)),
                            "conversions": max(1, int(revenue / rng.uniform(40, 90))),
                        }
                    )
        upsert_metrics(db, rows)
        db.commit()
        print(f"seeded account {acc.id} with {len(rows)} metric rows")
        return acc.id


if __name__ == "__main__":
    seed()
