"""pytest-bdd step definitions for tests/features/*.feature."""

from datetime import date

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.conftest import make_campaign, metric_rows

API = "/api/v1"

scenarios("budget_reallocation.feature", "metrics_ingestion.feature", "reports.feature")


@pytest.fixture
def ctx():
    return {}


def _bulk(client, aid, rows, key=None):
    headers = {"Idempotency-Key": key} if key else {}
    return client.post(f"{API}/accounts/{aid}/metrics/bulk", json={"rows": rows}, headers=headers)


def _seed_account(client, name: str, channels: dict[str, tuple[float, float]], days: int = 30) -> dict:
    acc = client.post(f"{API}/accounts", json={"name": name}).json()
    camps, rows = {}, []
    for ch, (spend, roas) in channels.items():
        camps[ch] = make_campaign(client, acc["id"], ch)
        rows += metric_rows(camps[ch]["id"], days, spend, roas, spend_jitter=0.4)
    assert _bulk(client, acc["id"], rows).status_code == 200
    return {"account": acc, "campaigns": camps, "rows": rows}


# ---------------- Given ----------------
@given(parsers.parse('an account with channels "{c1}" (ROAS {r1:g}) and "{c2}" (ROAS {r2:g})'), target_fixture="ctx")
def account_two_channels(client, c1, r1, c2, r2):
    seeded = _seed_account(client, "BDD", {c1: (1000.0, r1), c2: (800.0, r2)})
    return {"seeded": seeded, "aid": seeded["account"]["id"], "current": {c1: 1000.0, c2: 800.0}}


@given("an account with 30 days of metrics", target_fixture="ctx")
def account_30_days(client):
    seeded = _seed_account(client, "BDD", {"google": (1000.0, 4.0), "meta": (800.0, 1.5), "amazon": (500.0, 3.0)})
    return {"seeded": seeded, "aid": seeded["account"]["id"]}


@given("another account with 30 days of metrics")
def other_account(client, ctx):
    ctx["other"] = _seed_account(client, "Other", {"google": (300.0, 2.0)})


@given(parsers.parse('an account with a "{channel}" campaign'), target_fixture="ctx")
def account_with_campaign(client, channel):
    acc = client.post(f"{API}/accounts", json={"name": "Ingest"}).json()
    camp = make_campaign(client, acc["id"], channel)
    return {"aid": acc["id"], "cid": camp["id"]}


@given(parsers.parse("a total daily budget of {budget:g}"))
def total_budget(ctx, budget):
    ctx["budget"] = budget


# ---------------- When ----------------
@when("I request a budget recommendation")
def request_recommendation(client, ctx):
    r = client.post(f"{API}/accounts/{ctx['aid']}/recommendations/budget", json={"total_budget": ctx["budget"]})
    assert r.status_code == 200, r.text
    ctx["rec"] = r.json()


@when(parsers.parse("I request a budget recommendation with max shift {pct:d}%"))
def request_recommendation_capped(client, ctx, pct):
    r = client.post(
        f"{API}/accounts/{ctx['aid']}/recommendations/budget",
        json={"total_budget": ctx["budget"], "max_shift_pct": pct / 100, "min_share": 0},
    )
    assert r.status_code == 200, r.text
    ctx["rec"] = r.json()
    ctx["max_shift"] = pct / 100


@when("I request the channel-mix report twice")
def request_mix_twice(client, ctx):
    url = f"{API}/accounts/{ctx['aid']}/reports/channel-mix"
    ctx["r1"] = client.get(url)
    ctx["r2"] = client.get(url)


@when("I request the channel-mix report")
def request_mix(client, ctx):
    ctx["r1"] = client.get(f"{API}/accounts/{ctx['aid']}/reports/channel-mix")
    assert ctx["r1"].status_code == 200


@when("I request the trend report")
def request_trend(client, ctx):
    ctx["trend"] = client.get(f"{API}/accounts/{ctx['aid']}/reports/trend").json()


@when("new metrics are uploaded for the other account")
def upload_other(client, ctx):
    other = ctx["other"]
    assert _bulk(client, other["account"]["id"], other["rows"][:3]).status_code == 200


@when("new metrics are uploaded for the account")
def upload_self(client, ctx):
    assert _bulk(client, ctx["aid"], ctx["seeded"]["rows"][:3]).status_code == 200


@when(parsers.parse("I bulk-upload {days:d} days of metrics with spend {spend:g}"))
def upload_days(client, ctx, days, spend):
    ctx["rows"] = metric_rows(ctx["cid"], days, spend, 2.0, end=date(2024, 6, 30))
    ctx["resp"] = _bulk(client, ctx["aid"], ctx["rows"])
    assert ctx["resp"].status_code == 200


@when(parsers.parse("I bulk-upload the same {days:d} days again with spend {spend:g}"))
def upload_again(client, ctx, days, spend):
    for r in ctx["rows"]:
        r["spend"] = spend
    ctx["resp"] = _bulk(client, ctx["aid"], ctx["rows"])
    assert ctx["resp"].status_code == 200


@when(parsers.parse('I bulk-upload {days:d} days of metrics with Idempotency-Key "{key}"'))
def upload_with_key(client, ctx, days, key):
    ctx["rows"] = metric_rows(ctx["cid"], days, 100.0, 2.0, end=date(2024, 6, 30))
    ctx["resp"] = _bulk(client, ctx["aid"], ctx["rows"], key=key)
    assert ctx["resp"].status_code == 200


@when(parsers.parse('I retry the same upload with Idempotency-Key "{key}"'))
def retry_with_key(client, ctx, key):
    ctx["resp2"] = _bulk(client, ctx["aid"], ctx["rows"], key=key)


@when(parsers.parse('I upload a different payload with Idempotency-Key "{key}"'))
def different_payload_same_key(client, ctx, key):
    rows = metric_rows(ctx["cid"], 5, 999.0, 2.0, end=date(2024, 6, 30))
    ctx["resp2"] = _bulk(client, ctx["aid"], rows, key=key)


# ---------------- Then ----------------
@then(parsers.parse('"{winner}" receives more budget than "{loser}"'))
def winner_gets_more(ctx, winner, loser):
    by = {c["channel"]: c["recommended_daily_spend"] for c in ctx["rec"]["channels"]}
    assert by[winner] > by[loser], by


@then(parsers.parse("the recommended budgets sum to {budget:g}"))
def budgets_sum(ctx, budget):
    total = sum(c["recommended_daily_spend"] for c in ctx["rec"]["channels"])
    assert total == pytest.approx(budget, abs=0.05)


@then("every channel has an explanation mentioning marginal ROAS")
def explanations_present(ctx):
    assert all("marginal ROAS" in c["explanation"] for c in ctx["rec"]["channels"])
    assert ctx["rec"]["summary"]


@then(parsers.parse("no channel moves more than {pct:d}% from its current spend"))
def shift_capped(ctx, pct):
    for c in ctx["rec"]["channels"]:
        assert abs(c["delta_pct"]) <= pct / 100 + 0.01, c


@then("the second response is served from cache")
def second_from_cache(ctx):
    assert ctx["r1"].headers["X-Cache"] == "MISS"
    assert ctx["r2"].headers["X-Cache"] == "HIT"
    assert ctx["r1"].json() == ctx["r2"].json()


@then("the channel-mix report is still served from cache")
def still_cached(client, ctx):
    assert client.get(f"{API}/accounts/{ctx['aid']}/reports/channel-mix").headers["X-Cache"] == "HIT"


@then("the channel-mix report is recomputed")
def recomputed(client, ctx):
    assert client.get(f"{API}/accounts/{ctx['aid']}/reports/channel-mix").headers["X-Cache"] == "MISS"


@then("every channel appears exactly once")
def channels_once(ctx):
    chans = [c["channel"] for c in ctx["r1"].json()["channels"]]
    assert sorted(chans) == ["amazon", "google", "meta"]


@then("the spend shares sum to 1.0")
def shares_sum(ctx):
    assert sum(c["spend_share"] for c in ctx["r1"].json()["channels"]) == pytest.approx(1.0, abs=1e-3)


@then(parsers.parse('"{channel}" has the best ROAS rank'))
def best_rank(ctx, channel):
    by = {c["channel"]: c["roas_rank"] for c in ctx["r1"].json()["channels"]}
    assert by[channel] == 1


@then(parsers.parse("each channel has {n:d} trend points"))
def trend_points(ctx, n):
    pts = ctx["trend"]["points"]
    for ch in ("google", "meta", "amazon"):
        assert len([p for p in pts if p["channel"] == ch]) == n


@then("the 7-day average on day 7 equals the mean of the first 7 days")
def rolling_avg(ctx):
    pts = [p for p in ctx["trend"]["points"] if p["channel"] == "google"]
    assert pts[6]["spend_7d_avg"] == pytest.approx(sum(p["spend"] for p in pts[:7]) / 7, abs=0.01)


@then(parsers.parse("the campaign has exactly {n:d} metric rows"))
def metric_count(client, ctx, n):
    rows = client.get(f"{API}/accounts/{ctx['aid']}/metrics", params={"campaign_id": ctx["cid"]}).json()
    assert len(rows) == n


@then(parsers.parse("the total spend is {total:g}"))
def total_spend(client, ctx, total):
    rows = client.get(f"{API}/accounts/{ctx['aid']}/metrics", params={"campaign_id": ctx["cid"]}).json()
    assert sum(float(r["spend"]) for r in rows) == pytest.approx(total)


@then("the second response is marked as an idempotent replay")
def replayed(ctx):
    assert ctx["resp2"].status_code == 200
    assert ctx["resp2"].headers["Idempotent-Replayed"] == "true"
    assert ctx["resp2"].json()["idempotent_replay"] is True


@then(parsers.parse("the request is rejected with status {status:d}"))
def rejected(ctx, status):
    assert ctx["resp2"].status_code == status
