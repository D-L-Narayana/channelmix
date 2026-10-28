"""pytest-bdd step definitions for tests/features/*.feature."""

import json
import threading
import time
from datetime import date

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.conftest import API, make_campaign, make_workspace, metric_rows, seed_workspace, upload
from tests.test_stream_and_datasets import read_sse

scenarios(
    "budget_reallocation.feature",
    "metrics_ingestion.feature",
    "reports.feature",
    "workspace_isolation.feature",
    "csv_import.feature",
    "live_events.feature",
)


@pytest.fixture
def ctx():
    return {}


# ---------------- Given ----------------
@given(parsers.parse('a workspace with channels "{c1}" (ROAS {r1:g}) and "{c2}" (ROAS {r2:g})'), target_fixture="ctx")
def ws_two_channels(client, c1, r1, c2, r2):
    ws = make_workspace(client, "BDD")
    seeded = seed_workspace(ws, {c1: (1000.0, r1), c2: (800.0, r2)})
    return {"ws": ws, "seeded": seeded, "current": {c1: 1000.0, c2: 800.0}}


@given("a workspace with 30 days of metrics", target_fixture="ctx")
def ws_30_days(client):
    ws = make_workspace(client, "BDD")
    seeded = seed_workspace(ws, {"google": (1000.0, 4.0), "meta": (800.0, 1.5), "amazon": (500.0, 3.0)})
    return {"ws": ws, "seeded": seeded}


@given("a workspace", target_fixture="ctx")
def ws_plain(client):
    return {"ws": make_workspace(client, "BDD")}


@given("another workspace with 30 days of metrics")
def other_ws_seeded(client, ctx):
    other = make_workspace(client, "Other")
    ctx["other"] = seed_workspace(other, {"linkedin": (300.0, 2.0)})
    ctx["other_ws"] = other


@given("another workspace")
def other_ws_plain(client, ctx):
    ctx["other_ws"] = make_workspace(client, "Other")


@given(parsers.parse('a workspace with a "{channel}" campaign'), target_fixture="ctx")
def ws_with_campaign(client, channel):
    ws = make_workspace(client, "Ingest")
    camp = make_campaign(ws, channel)
    return {"ws": ws, "cid": camp["id"]}


@given(parsers.parse("a total daily budget of {budget:g}"))
def total_budget(ctx, budget):
    ctx["budget"] = budget


@given("a fast SSE configuration")
def fast_sse_cfg(fast_sse):
    return fast_sse


# ---------------- When: workspaces ----------------
@when(parsers.parse('I create a workspace "{name}" with email "{email}"'), target_fixture="ctx")
def create_ws(client, name, email):
    r = client.post(f"{API}/workspaces", json={"name": name, "email": email})
    assert r.status_code == 201, r.text
    return {"created": r.json(), "client": client}


@when("I call the campaigns endpoint without an API key")
def call_without_key(client, ctx):
    ctx["resp2"] = client.get(f"{API}/campaigns")


@when("I call the campaigns endpoint with a forged API key")
def call_forged_key(client, ctx):
    ctx["resp2"] = client.get(f"{API}/campaigns", headers={"X-Api-Key": "cmx_" + "f" * 40})


@when("the other workspace reads my campaign")
def other_reads(ctx):
    ctx["resp2"] = ctx["other_ws"].get(f"{API}/campaigns/{ctx['cid']}")


@when("the other workspace pushes metrics for my campaign")
def other_pushes(ctx):
    ctx["resp2"] = ctx["other_ws"].bulk(metric_rows(ctx["cid"], 3, 10, 1.0))


# ---------------- When: recommendations / reports ----------------
@when("I request a budget recommendation")
def request_recommendation(ctx):
    r = ctx["ws"].get(f"{API}/recommendations", params={"total_budget": ctx["budget"]})
    assert r.status_code == 200, r.text
    ctx["rec"] = r.json()


@when(parsers.parse("I request a budget recommendation with max shift {pct:d}%"))
def request_recommendation_capped(ctx, pct):
    r = ctx["ws"].get(
        f"{API}/recommendations",
        params={"total_budget": ctx["budget"], "max_shift_pct": pct / 100, "min_share": 0},
    )
    assert r.status_code == 200, r.text
    ctx["rec"] = r.json()


@when("I request the channel-mix report twice")
def request_mix_twice(ctx):
    ctx["r1"] = ctx["ws"].get(f"{API}/reports/by-channel")
    ctx["r2"] = ctx["ws"].get(f"{API}/reports/by-channel")


@when("I request the channel-mix report")
def request_mix(ctx):
    ctx["r1"] = ctx["ws"].get(f"{API}/reports/by-channel")
    assert ctx["r1"].status_code == 200


@when("I request the trend report")
def request_trend(ctx):
    ctx["trend"] = ctx["ws"].get(f"{API}/reports/trend").json()


@when("new metrics are uploaded for the other workspace")
def upload_other(ctx):
    other = ctx["other"]
    assert ctx["other_ws"].bulk(other["rows"][:3]).status_code == 200


@when("new metrics are uploaded for the workspace")
def upload_self(ctx):
    assert ctx["ws"].bulk(ctx["seeded"]["rows"][:3]).status_code == 200


# ---------------- When: ingestion ----------------
@when(parsers.parse("I bulk-upload {days:d} days of metrics with spend {spend:g}"))
def upload_days(ctx, days, spend):
    ctx["rows"] = metric_rows(ctx["cid"], days, spend, 2.0, end=date(2024, 6, 30))
    ctx["resp"] = ctx["ws"].bulk(ctx["rows"])
    assert ctx["resp"].status_code == 200


@when(parsers.parse("I bulk-upload the same {days:d} days again with spend {spend:g}"))
def upload_again(ctx, days, spend):
    for r in ctx["rows"]:
        r["spend"] = spend
    ctx["resp"] = ctx["ws"].bulk(ctx["rows"])
    assert ctx["resp"].status_code == 200


@when(parsers.parse('I bulk-upload {days:d} days of metrics with Idempotency-Key "{key}"'))
def upload_with_key(ctx, days, key):
    ctx["rows"] = metric_rows(ctx["cid"], days, 100.0, 2.0, end=date(2024, 6, 30))
    ctx["resp"] = ctx["ws"].bulk(ctx["rows"], key=key)
    assert ctx["resp"].status_code == 200


@when(parsers.parse('I retry the same upload with Idempotency-Key "{key}"'))
def retry_with_key(ctx, key):
    ctx["resp2"] = ctx["ws"].bulk(ctx["rows"], key=key)


@when(parsers.parse('I upload a different payload with Idempotency-Key "{key}"'))
def different_payload_same_key(ctx, key):
    rows = metric_rows(ctx["cid"], 5, 999.0, 2.0, end=date(2024, 6, 30))
    ctx["resp2"] = ctx["ws"].bulk(rows, key=key)


# ---------------- When: CSV ----------------
@when(parsers.parse('I dry-run import the "{name}" export'))
def csv_dry_run(ctx, name):
    ctx["imp"] = upload(ctx["ws"], name, dry_run=True)
    assert ctx["imp"].status_code == 200, ctx["imp"].text


@when(parsers.parse('I import the "{name}" export'))
def csv_commit(ctx, name):
    ctx["imp"] = upload(ctx["ws"], name)
    assert ctx["imp"].status_code == 200, ctx["imp"].text


# ---------------- When: SSE ----------------
@when("I subscribe to the stream and 5 days of metrics are pushed meanwhile")
def subscribe_and_push(ctx):
    def writer():
        time.sleep(0.4)
        ctx["ws"].bulk(metric_rows(ctx["cid"], 5, 10, 2.0))

    th = threading.Thread(target=writer)
    th.start()
    ctx["events"], ctx["comments"] = read_sse(ctx["ws"])
    th.join()


@when("the campaign is paused while I am disconnected")
def pause_offline(ctx):
    events, _ = read_sse(ctx["ws"])  # first connection: learn the cursor, then disconnect
    ctx["cursor"] = events[0]["id"]
    ctx["ws"].patch(f"{API}/campaigns/{ctx['cid']}", json={"status": "paused"})


@when("I reconnect with the Last-Event-ID of the ready event")
def reconnect(ctx):
    ctx["events"], ctx["comments"] = read_sse(ctx["ws"], headers={"Last-Event-ID": ctx["cursor"]})


# ---------------- Then ----------------
@then("the response contains an API key and a slug")
def has_key(ctx):
    assert ctx["created"]["api_key"].startswith("cmx_") and ctx["created"]["slug"].startswith("acme-retail-")


@then("the API key is not returned by GET /workspaces/me")
def key_not_returned(ctx):
    me = ctx["client"].get(f"{API}/workspaces/me", headers={"X-Api-Key": ctx["created"]["api_key"]}).json()
    assert "api_key" not in me and ctx["created"]["api_key"] not in json.dumps(me)


@then(parsers.parse("my campaign still has {n:d} metric rows"))
def my_rows(ctx, n):
    assert len(ctx["ws"].get(f"{API}/metrics", params={"campaign_id": ctx["cid"]}).json()) == n


@then("the other workspace sees only its own channels")
def other_sees_own(ctx):
    chans = [c["channel"] for c in ctx["other_ws"].get(f"{API}/reports/by-channel").json()["channels"]]
    assert chans == ["linkedin"]


@then("the other workspace sees none of my events")
def other_sees_no_events(ctx):
    mine = {e["id"] for e in ctx["ws"].get(f"{API}/events", params={"after": 0}).json()}
    theirs = {e["id"] for e in ctx["other_ws"].get(f"{API}/events", params={"after": 0}).json()}
    assert mine and theirs and not (mine & theirs)


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
def still_cached(ctx):
    assert ctx["ws"].get(f"{API}/reports/by-channel").headers["X-Cache"] == "HIT"


@then("the channel-mix report is recomputed")
def recomputed(ctx):
    assert ctx["ws"].get(f"{API}/reports/by-channel").headers["X-Cache"] == "MISS"


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
def metric_count(ctx, n):
    rows = ctx["ws"].get(f"{API}/metrics", params={"campaign_id": ctx["cid"]}).json()
    assert len(rows) == n


@then(parsers.parse("the total spend is {total:g}"))
def total_spend(ctx, total):
    rows = ctx["ws"].get(f"{API}/metrics", params={"campaign_id": ctx["cid"]}).json()
    assert sum(float(r["spend"]) for r in rows) == pytest.approx(total)


@then("the second response is marked as an idempotent replay")
def replayed(ctx):
    assert ctx["resp2"].status_code == 200
    assert ctx["resp2"].headers["Idempotent-Replayed"] == "true"
    assert ctx["resp2"].json()["idempotent_replay"] is True


@then(parsers.parse("the request is rejected with status {status:d}"))
def rejected(ctx, status):
    assert ctx["resp2"].status_code == status, ctx["resp2"].text


# ---- CSV ----
@then(parsers.parse('the detected format is "{fmt}" with channel "{channel}"'))
def detected_with_channel(ctx, fmt, channel):
    b = ctx["imp"].json()
    assert b["detected_format"] == fmt and b["channel"] == channel


@then(parsers.parse('the detected format is "{fmt}"'))
def detected(ctx, fmt):
    assert ctx["imp"].json()["detected_format"] == fmt


@then(parsers.parse('the mapping uses "{src}" for {field} and "{src2}" for {field2}'))
def mapping_uses(ctx, src, field, src2, field2):
    m = ctx["imp"].json()["mapping"]
    assert m[field] == src and m[field2] == src2, m


@then(parsers.parse("the preview has {n:d} rows and nothing was written"))
def preview_rows(ctx, n):
    b = ctx["imp"].json()
    assert len(b["preview"]) == n and b["status"] == "dry_run" and b["import_id"] is None
    assert ctx["ws"].get(f"{API}/campaigns").json() == []


@then(parsers.parse("{c:d} campaigns were created and {r:d} rows upserted"))
def created_upserted(ctx, c, r):
    s = ctx["imp"].json()["summary"]
    assert s["campaigns_created"] == c and s["rows_upserted"] == r


@then(parsers.parse('an "{etype}" event was emitted'))
def event_emitted(ctx, etype):
    assert etype in [e["type"] for e in ctx["ws"].get(f"{API}/events", params={"after": 0}).json()]


@then(parsers.parse('the channel-mix report for {start} to {end} lists channels "{chans}"'))
def mix_lists(ctx, start, end, chans):
    mix = ctx["ws"].get(f"{API}/reports/by-channel", params={"start": start, "end": end}).json()
    assert sorted(c["channel"] for c in mix["channels"]) == sorted(x.strip() for x in chans.split(","))


@then(parsers.parse("the total spend for {start} to {end} is {total:g}"))
def spend_window(ctx, start, end, total):
    s = ctx["ws"].get(f"{API}/reports/summary", params={"start": start, "end": end}).json()
    assert s["spend"] == pytest.approx(total, abs=0.01)


# ---- SSE ----
@then(parsers.parse('I receive a "{first}" event followed by a "{second}" event'))
def events_in_order(ctx, first, second):
    kinds = [e["event"] for e in ctx["events"]]
    assert kinds[0] == first and second in kinds[1:], kinds


@then("the stream closes with a reconnect hint")
def closes_with_hint(ctx):
    assert ctx["comments"][-1].startswith(": reconnect")


@then(parsers.parse('I receive exactly {n:d} "{etype}" event'))
def exactly_n_events(ctx, n, etype):
    assert [e["event"] for e in ctx["events"] if e["event"] == etype] == [etype] * n


@then(parsers.parse('exactly {n:d} "{etype}" event exists'))
def exactly_n_in_feed(ctx, n, etype):
    evs = ctx["ws"].get(f"{API}/events", params={"after": 0}).json()
    assert len([e for e in evs if e["type"] == etype]) == n
