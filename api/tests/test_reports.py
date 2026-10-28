from datetime import date, timedelta

import pytest

API = "/api/v1"


def test_channel_mix_totals_and_shares(client, seeded):
    aid = seeded["account"]["id"]
    r = client.get(f"{API}/accounts/{aid}/reports/channel-mix")
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


def test_channel_mix_respects_date_window(client, seeded):
    aid = seeded["account"]["id"]
    end = date.today()
    start = end - timedelta(days=6)
    full = client.get(f"{API}/accounts/{aid}/reports/channel-mix").json()
    week = client.get(f"{API}/accounts/{aid}/reports/channel-mix", params={"start": start, "end": end}).json()
    assert week["total_spend"] < full["total_spend"]
    assert week["start"] == start.isoformat()


def test_channel_mix_empty_account(client, account):
    r = client.get(f"{API}/accounts/{account['id']}/reports/channel-mix")
    assert r.status_code == 200
    assert r.json()["channels"] == [] and r.json()["blended_roas"] is None


def test_trend_window_functions(client, seeded):
    aid = seeded["account"]["id"]
    r = client.get(f"{API}/accounts/{aid}/reports/trend")
    assert r.status_code == 200
    pts = [p for p in r.json()["points"] if p["channel"] == "google"]
    assert len(pts) == 30
    # first point: no previous day -> no DoD change; 7d avg equals its own spend
    assert pts[0]["spend_dod_change"] is None
    assert pts[0]["spend_7d_avg"] == pts[0]["spend"]
    # 7-day rolling average on day 7 equals mean of first 7 days
    assert pts[6]["spend_7d_avg"] == pytest.approx(sum(p["spend"] for p in pts[:7]) / 7, abs=0.01)
    # cumulative is monotonically increasing and ends at the channel total
    cums = [p["cumulative_spend"] for p in pts]
    assert cums == sorted(cums)
    assert cums[-1] == pytest.approx(sum(p["spend"] for p in pts), abs=0.05)
    assert pts[10]["roas_7d"] == pytest.approx(4.0, abs=0.01)


def test_trend_group_by_total(client, seeded):
    aid = seeded["account"]["id"]
    r = client.get(f"{API}/accounts/{aid}/reports/trend", params={"group_by": "total"})
    pts = r.json()["points"]
    assert len(pts) == 30 and {p["channel"] for p in pts} == {"all"}
    assert r.json()["group_by"] == "total"


def test_trend_group_by_invalid(client, seeded):
    aid = seeded["account"]["id"]
    assert client.get(f"{API}/accounts/{aid}/reports/trend", params={"group_by": "bogus"}).status_code == 422


def test_campaign_drilldown_report(client, seeded):
    aid = seeded["account"]["id"]
    r = client.get(f"{API}/accounts/{aid}/reports/campaigns")
    rows = r.json()
    assert len(rows) == 3
    assert all(row["spend_share_in_channel"] == 1.0 for row in rows)  # one campaign per channel
    assert all(row["roas_rank_in_channel"] == 1 for row in rows)
    only_meta = client.get(f"{API}/accounts/{aid}/reports/campaigns", params={"channel": "meta"}).json()
    assert len(only_meta) == 1 and only_meta[0]["channel"] == "meta"


def test_reports_are_cached_and_hit_header(client, seeded, cache):
    aid = seeded["account"]["id"]
    r1 = client.get(f"{API}/accounts/{aid}/reports/trend")
    r2 = client.get(f"{API}/accounts/{aid}/reports/trend")
    assert r1.headers["X-Cache"] == "MISS" and r2.headers["X-Cache"] == "HIT"
    assert r1.json() == r2.json()
    assert cache.hits == 1


def test_cache_isolated_per_account(client, seeded, cache):
    aid = seeded["account"]["id"]
    other = client.post(f"{API}/accounts", json={"name": "Other"}).json()
    client.get(f"{API}/accounts/{aid}/reports/channel-mix")
    client.get(f"{API}/accounts/{other['id']}/reports/channel-mix")
    # a write on the other account must not evict this account's reports
    client.post(f"{API}/accounts/{other['id']}/campaigns", json={"channel": "google", "external_id": "x", "name": "x"})
    assert client.get(f"{API}/accounts/{aid}/reports/channel-mix").headers["X-Cache"] == "HIT"
    assert client.get(f"{API}/accounts/{other['id']}/reports/channel-mix").headers["X-Cache"] == "MISS"


def test_campaign_update_invalidates_cache(client, seeded):
    aid = seeded["account"]["id"]
    cid = seeded["campaigns"]["google"]["id"]
    client.get(f"{API}/accounts/{aid}/reports/campaigns")
    client.patch(f"{API}/accounts/{aid}/campaigns/{cid}", json={"status": "paused"})
    r = client.get(f"{API}/accounts/{aid}/reports/campaigns")
    assert r.headers["X-Cache"] == "MISS"
    assert next(x for x in r.json() if x["campaign_id"] == cid)["status"] == "paused"


def test_reports_404_unknown_account(client):
    assert client.get(f"{API}/accounts/404/reports/channel-mix").status_code == 404
    assert client.get(f"{API}/accounts/404/reports/trend").status_code == 404
