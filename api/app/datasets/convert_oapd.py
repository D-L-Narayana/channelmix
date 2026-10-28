"""Convert the Kaggle "Online Advertising Digital Marketing data" export into ChannelMix's generic CSV.

Source (MIT licence): https://www.kaggle.com/datasets/naniruddhan/online-advertising-digital-marketing-data
Raw columns: month, day, campaign_number, user_engagement, banner, placement, displays, cost, clicks,
             revenue, post_click_conversions, post_click_sales_amount

Mapping (advertiser's point of view, see SOURCE.md):
  day          = 2020-<month>-<day>
  channel      = other   (one anonymised display network, "Advert Firm A")
  campaign     = "<campaign_number> / placement <placement>"   (aggregated over engagement + banner)
  impressions  = sum(displays)
  clicks       = sum(clicks)
  conversions  = sum(post_click_conversions)
  spend        = sum(revenue)                 <- what Company X paid the ad network for the clicks
  revenue      = sum(post_click_sales_amount) <- on-site sales attributed to those clicks (30-day window)

Usage: python -m app.datasets.convert_oapd raw_ad_data.csv > app/datasets/channelmix-sample.csv
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal

MONTHS = {"april": 4, "may": 5, "june": 6}
HEADER = ["day", "channel", "campaign", "external_id", "impressions", "clicks", "conversions", "spend", "revenue"]


def convert(src: str, out) -> int:
    agg: dict[tuple[date, str, str], list] = defaultdict(lambda: [0, 0, 0, Decimal(0), Decimal(0)])
    with open(src, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if not r.get("month"):
                continue
            d = date(2020, MONTHS[r["month"].strip().lower()], int(r["day"]))
            camp = r["campaign_number"].strip().replace("camp ", "Campaign ")
            placement = r["placement"].strip()
            placement = "unknown" if placement in ("", "#N/A") else placement
            key = (d, camp, placement)
            a = agg[key]
            a[0] += int(r["displays"] or 0)
            a[1] += int(r["clicks"] or 0)
            a[2] += int(r["post_click_conversions"] or 0)
            a[3] += Decimal(r["revenue"] or 0)
            a[4] += Decimal(r["post_click_sales_amount"] or 0)
    w = csv.writer(out, lineterminator="\n")
    w.writerow(HEADER)
    n = 0
    for (d, camp, placement), (imp, clk, conv, spend, rev) in sorted(agg.items()):
        ext = f"{camp.lower().replace(' ', '')}-{placement}"
        w.writerow(
            [d.isoformat(), "other", f"{camp} / placement {placement}", ext, imp, clk, conv,
             f"{spend.quantize(Decimal('0.0001'))}", f"{rev.quantize(Decimal('0.0001'))}"]
        )
        n += 1
    return n


if __name__ == "__main__":
    convert(sys.argv[1], sys.stdout)
