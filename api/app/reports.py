"""Report queries. Written as portable SQL (PostgreSQL + SQLite) using window functions."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session


def _f(v) -> float:
    return float(v or 0)


def _ratio(num, den) -> float | None:
    den = _f(den)
    return round(_f(num) / den, 4) if den else None


CHANNEL_MIX_SQL = text(
    """
    WITH per_channel AS (
        SELECT c.channel                 AS channel,
               SUM(m.spend)              AS spend,
               SUM(m.revenue)            AS revenue,
               SUM(m.impressions)        AS impressions,
               SUM(m.clicks)             AS clicks,
               SUM(m.conversions)        AS conversions
        FROM daily_metrics m
        JOIN campaigns c ON c.id = m.campaign_id
        WHERE c.account_id = :account_id AND m.day BETWEEN :start AND :end
        GROUP BY c.channel
    )
    SELECT channel, spend, revenue, impressions, clicks, conversions,
           SUM(spend)   OVER ()                                           AS total_spend,
           SUM(revenue) OVER ()                                           AS total_revenue,
           spend   * 1.0 / NULLIF(SUM(spend)   OVER (), 0)                AS spend_share,
           revenue * 1.0 / NULLIF(SUM(revenue) OVER (), 0)                AS revenue_share,
           RANK() OVER (ORDER BY revenue * 1.0 / NULLIF(spend, 0) DESC)   AS roas_rank
    FROM per_channel
    ORDER BY spend DESC
    """
)


def channel_mix(db: Session, account_id: int, start: date, end: date) -> dict:
    rows = db.execute(CHANNEL_MIX_SQL, {"account_id": account_id, "start": start, "end": end}).mappings().all()
    total_spend = _f(rows[0]["total_spend"]) if rows else 0.0
    total_revenue = _f(rows[0]["total_revenue"]) if rows else 0.0
    channels = []
    for r in rows:
        channels.append(
            {
                "channel": r["channel"],
                "spend": round(_f(r["spend"]), 2),
                "revenue": round(_f(r["revenue"]), 2),
                "impressions": int(r["impressions"] or 0),
                "clicks": int(r["clicks"] or 0),
                "conversions": int(r["conversions"] or 0),
                "spend_share": round(_f(r["spend_share"]), 4),
                "revenue_share": round(_f(r["revenue_share"]), 4),
                "roas": _ratio(r["revenue"], r["spend"]),
                "cpa": _ratio(r["spend"], r["conversions"]),
                "ctr": _ratio(r["clicks"], r["impressions"]),
                "cpc": _ratio(r["spend"], r["clicks"]),
                "roas_rank": int(r["roas_rank"]),
            }
        )
    return {
        "account_id": account_id,
        "start": start,
        "end": end,
        "total_spend": round(total_spend, 2),
        "total_revenue": round(total_revenue, 2),
        "blended_roas": _ratio(total_revenue, total_spend),
        "channels": channels,
    }


TREND_SQL = {
    "channel": text(
        """
        WITH daily AS (
            SELECT m.day AS day, c.channel AS grp,
                   SUM(m.spend) AS spend, SUM(m.revenue) AS revenue, SUM(m.conversions) AS conversions
            FROM daily_metrics m JOIN campaigns c ON c.id = m.campaign_id
            WHERE c.account_id = :account_id AND m.day BETWEEN :start AND :end
            GROUP BY m.day, c.channel
        )
        SELECT day, grp, spend, revenue, conversions,
               AVG(spend)   OVER w7 AS spend_7d_avg,
               SUM(revenue) OVER w7 * 1.0 / NULLIF(SUM(spend) OVER w7, 0) AS roas_7d,
               LAG(spend)   OVER (PARTITION BY grp ORDER BY day) AS prev_spend,
               SUM(spend)   OVER (PARTITION BY grp ORDER BY day ROWS UNBOUNDED PRECEDING) AS cumulative_spend
        FROM daily
        WINDOW w7 AS (PARTITION BY grp ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
        ORDER BY day, grp
        """
    ),
    "total": text(
        """
        WITH daily AS (
            SELECT m.day AS day, 'all' AS grp,
                   SUM(m.spend) AS spend, SUM(m.revenue) AS revenue, SUM(m.conversions) AS conversions
            FROM daily_metrics m JOIN campaigns c ON c.id = m.campaign_id
            WHERE c.account_id = :account_id AND m.day BETWEEN :start AND :end
            GROUP BY m.day
        )
        SELECT day, grp, spend, revenue, conversions,
               AVG(spend)   OVER w7 AS spend_7d_avg,
               SUM(revenue) OVER w7 * 1.0 / NULLIF(SUM(spend) OVER w7, 0) AS roas_7d,
               LAG(spend)   OVER (ORDER BY day) AS prev_spend,
               SUM(spend)   OVER (ORDER BY day ROWS UNBOUNDED PRECEDING) AS cumulative_spend
        FROM daily
        WINDOW w7 AS (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
        ORDER BY day
        """
    ),
}


def trend(db: Session, account_id: int, start: date, end: date, group_by: str = "channel") -> dict:
    sql = TREND_SQL["total" if group_by == "total" else "channel"]
    rows = db.execute(sql, {"account_id": account_id, "start": start, "end": end}).mappings().all()
    points = []
    for r in rows:
        prev = r["prev_spend"]
        spend = _f(r["spend"])
        points.append(
            {
                "day": r["day"] if isinstance(r["day"], date) else date.fromisoformat(str(r["day"])),
                "channel": r["grp"],
                "spend": round(spend, 2),
                "revenue": round(_f(r["revenue"]), 2),
                "conversions": int(r["conversions"] or 0),
                "roas": _ratio(r["revenue"], r["spend"]),
                "spend_7d_avg": round(_f(r["spend_7d_avg"]), 2),
                "roas_7d": round(_f(r["roas_7d"]), 4) if r["roas_7d"] is not None else None,
                "spend_dod_change": round((spend - _f(prev)) / _f(prev), 4) if prev not in (None, 0) else None,
                "cumulative_spend": round(_f(r["cumulative_spend"]), 2),
            }
        )
    return {"account_id": account_id, "start": start, "end": end, "group_by": group_by, "points": points}


CAMPAIGN_PERF_SQL = """
    WITH per_campaign AS (
        SELECT c.id AS campaign_id, c.name AS name, c.channel AS channel, c.status AS status,
               COALESCE(SUM(m.spend), 0) AS spend, COALESCE(SUM(m.revenue), 0) AS revenue,
               COALESCE(SUM(m.impressions), 0) AS impressions, COALESCE(SUM(m.clicks), 0) AS clicks,
               COALESCE(SUM(m.conversions), 0) AS conversions
        FROM campaigns c
        LEFT JOIN daily_metrics m ON m.campaign_id = c.id AND m.day BETWEEN :start AND :end
        WHERE c.account_id = :account_id {channel_filter}
        GROUP BY c.id, c.name, c.channel, c.status
    )
    SELECT *,
           spend * 1.0 / NULLIF(SUM(spend) OVER (PARTITION BY channel), 0)              AS spend_share_in_channel,
           RANK() OVER (PARTITION BY channel ORDER BY revenue * 1.0 / NULLIF(spend, 0) DESC) AS roas_rank_in_channel
    FROM per_campaign
    ORDER BY spend DESC
"""


def campaign_performance(db: Session, account_id: int, start: date, end: date, channel: str | None) -> list[dict]:
    sql = text(CAMPAIGN_PERF_SQL.format(channel_filter="AND c.channel = :channel" if channel else ""))
    params: dict = {"account_id": account_id, "start": start, "end": end}
    if channel:
        params["channel"] = channel
    rows = db.execute(sql, params).mappings()
    out = []
    for r in rows:
        out.append(
            {
                "campaign_id": r["campaign_id"],
                "name": r["name"],
                "channel": r["channel"],
                "status": r["status"],
                "spend": round(_f(r["spend"]), 2),
                "revenue": round(_f(r["revenue"]), 2),
                "impressions": int(r["impressions"]),
                "clicks": int(r["clicks"]),
                "conversions": int(r["conversions"]),
                "roas": _ratio(r["revenue"], r["spend"]),
                "cpa": _ratio(r["spend"], r["conversions"]),
                "spend_share_in_channel": round(_f(r["spend_share_in_channel"]), 4),
                "roas_rank_in_channel": int(r["roas_rank_in_channel"]),
            }
        )
    return out


CHANNEL_HISTORY_SQL = text(
    """
    SELECT c.channel AS channel, m.day AS day, SUM(m.spend) AS spend, SUM(m.revenue) AS revenue
    FROM daily_metrics m JOIN campaigns c ON c.id = m.campaign_id
    WHERE c.account_id = :account_id AND m.day BETWEEN :start AND :end
    GROUP BY c.channel, m.day
    ORDER BY c.channel, m.day
    """
)


def channel_history(db: Session, account_id: int, start: date, end: date) -> dict[str, list[tuple[float, float]]]:
    """Per-channel list of (daily_spend, daily_revenue) observations used to fit response curves."""
    rows = db.execute(CHANNEL_HISTORY_SQL, {"account_id": account_id, "start": start, "end": end})
    history: dict[str, list[tuple[float, float]]] = {}
    for channel, _day, spend, revenue in rows:
        history.setdefault(channel, []).append((_f(spend), _f(revenue)))
    return history
