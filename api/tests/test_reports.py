from datetime import date, timedelta

import pytest

from tests.conftest import API, make_campaign, metric_rows, seed_workspace


# ---------------- summary ----------------
def test_summary_totals_and_ratios(seeded):
    ws = seeded["ws"]
    r = ws.get(f"{API}/reports/summary")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["days_with_data"] == 30 and b["campaigns"] == 3
    assert b["spend"] == pytest.approx(sum(r["spend"] for r in seeded["rows"]), abs=0.05)
    assert b["roas"] == pytest.approx(b["revenue"] / b["spend"], abs=1e-3)
    assert b["ctr"] == pytest.approx(0.02) and b["cpa"] == pytest.approx(b["spend"] / b["conversions"], abs=1e-3)
    assert b["previous"] is None and all(v is None for v in b["delta_pct"].values())


def test_summary_previous_period_and_delta(ws):
    c = make_campaign(ws, "google")
    end = date(2025, 3, 14)
    rows = metric_rows(c["id"], 7, 100, 2.0, end=end - timedelta(days=7)) + metric_rows(c["id"], 7, 120, 3.0, end=end)
    ws.bulk(rows)
    b = ws.get(f"{API}/reports/summary", params={"start": "2025-03-08", "end": "2025-03-14"}).json()
    assert b["spend"] == pytest.approx(840) and b["previous"]["spend"] == pytest.approx(700)
    assert b["delta_pct"]["spend"] == pytest.approx(0.2) and b["delta_pct"]["roas"] == pytest.approx(0.5)


def test_summary_empty_workspace(ws):
    b = ws.get(f"{API}/reports/summary").json()
    assert b["spend"] == 0 and b["roas"] is None and b["campaigns"] == 0 and b["previous"] is None


# ---------------- by-channel ----------------
def test_by_channel_totals_and_shares(seeded):
    ws = seeded["ws"]
    r = ws.get(f"{API}/reports/by-channel")
    assert r.status_code == 200
    body = r.json()
    chans = {c["channel"]: c for c in body["channels"]}
    assert set(chans) == {"google", "meta", "amazon"}
    assert pytest.approx(sum(c["spend_share"] for c in chans.values()), abs=1e-3) == 1.0
    assert pytest.approx(body["total_spend"], rel=1e-6) == sum(c["spend"] for c in chans.values())
    assert chans["google"]["roas"] == pytest.approx(4.0, abs=0.01)
    assert chans["meta"]["roas"] == pytest.approx(1.5, abs=0.01)
    assert chans["google"]["roas_rank"] == 1 and chans["meta"]["roas_rank"] == 3
    assert chans["google"]["ctr"] == pytest.approx(0.02)


def test_by_channel_respects_date_window(seeded):
    ws = seeded["ws"]
    end = date.today()
    start = end - timedelta(days=6)
    full = ws.get(f"{API}/reports/by-channel").json()
    week = ws.get(f"{API}/reports/by-channel", params={"start": start, "end": end}).json()
    assert week["total_spend"] < full["total_spend"]
    assert week["start"] == start.isoformat()


def test_by_channel_empty_workspace(ws):
    r = ws.get(f"{API}/reports/by-channel")
    assert r.status_code == 200
    assert r.json()["channels"] == [] and r.json()["blended_roas"] is None


# ---------------- trend ----------------
def test_trend_window_functions(seeded):
    ws = seeded["ws"]
    r = ws.get(f"{API}/reports/trend")
    assert r.status_code == 200
    pts = [p for p in r.json()["points"] if p["channel"] == "google"]
    assert len(pts) == 30
    assert pts[0]["spend_dod_change"] is None
    assert pts[0]["spend_7d_avg"] == pts[0]["spend"]
    assert pts[6]["spend_7d_avg"] == pytest.approx(sum(p["spend"] for p in pts[:7]) / 7, abs=0.01)
    cums = [p["cumulative_spend"] for p in pts]
    assert cums == sorted(cums)
    assert cums[-1] == pytest.approx(sum(p["spend"] for p in pts), abs=0.05)
    assert pts[10]["roas_7d"] == pytest.approx(4.0, abs=0.01)


def test_trend_group_by_total(seeded):
    ws = seeded["ws"]
    r = ws.get(f"{API}/reports/trend", params={"group_by": "total"})
    pts = r.json()["points"]
    assert len(pts) == 30 and {p["channel"] for p in pts} == {"all"}
    assert r.json()["group_by"] == "total"


def test_trend_group_by_invalid(seeded):
    assert seeded["ws"].get(f"{API}/reports/trend", params={"group_by": "bogus"}).status_code == 422


# ---------------- campaigns ----------------
def test_campaign_drilldown_report(seeded):
    ws = seeded["ws"]
    rows = ws.get(f"{API}/reports/campaigns").json()
    assert len(rows) == 3
    assert all(row["spend_share_in_channel"] == 1.0 for row in rows)
    assert all(row["roas_rank_in_channel"] == 1 for row in rows)
    only_meta = ws.get(f"{API}/reports/campaigns", params={"channel": "meta"}).json()
    assert len(only_meta) == 1 and only_meta[0]["channel"] == "meta"


# ---------------- cache ----------------
def test_reports_are_cached_and_hit_header(seeded, cache):
    ws = seeded["ws"]
    r1 = ws.get(f"{API}/reports/trend")
    r2 = ws.get(f"{API}/reports/trend")
    assert r1.headers["X-Cache"] == "MISS" and r2.headers["X-Cache"] == "HIT"
    assert r1.json() == r2.json()
    assert cache.hits == 1


def test_cache_isolated_per_workspace(seeded, other_ws):
    ws = seeded["ws"]
    ws.get(f"{API}/reports/by-channel")
    other_ws.get(f"{API}/reports/by-channel")
    make_campaign(other_ws, "google")  # write on the other tenant must not evict ours
    assert ws.get(f"{API}/reports/by-channel").headers["X-Cache"] == "HIT"
    assert other_ws.get(f"{API}/reports/by-channel").headers["X-Cache"] == "MISS"


def test_campaign_update_invalidates_cache(seeded):
    ws = seeded["ws"]
    cid = seeded["campaigns"]["google"]["id"]
    ws.get(f"{API}/reports/campaigns")
    ws.patch(f"{API}/campaigns/{cid}", json={"status": "paused"})
    r = ws.get(f"{API}/reports/campaigns")
    assert r.headers["X-Cache"] == "MISS"
    assert next(x for x in r.json() if x["campaign_id"] == cid)["status"] == "paused"


# ---------------- isolation ----------------
def test_reports_never_leak_across_workspaces(seeded, other_ws):
    seed_workspace(other_ws, {"linkedin": (300.0, 2.0)})
    mine = seeded["ws"].get(f"{API}/reports/by-channel").json()
    theirs = other_ws.get(f"{API}/reports/by-channel").json()
    assert {c["channel"] for c in mine["channels"]} == {"google", "meta", "amazon"}
    assert {c["channel"] for c in theirs["channels"]} == {"linkedin"}
    assert len(other_ws.get(f"{API}/reports/campaigns").json()) == 1
    assert {p["channel"] for p in other_ws.get(f"{API}/reports/trend").json()["points"]} == {"linkedin"}
