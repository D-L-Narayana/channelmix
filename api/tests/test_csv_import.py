from datetime import date

import pytest

from app.csv_import import detect_format, parse_csv, parse_day, parse_number
from tests.conftest import API, FIXTURES, upload


# ---------------- unit: detection & value parsing ----------------
@pytest.mark.parametrize(
    "headers, expected",
    [
        (["campaign", "day", "cost", "impressions", "clicks", "conversions"], "google_ads"),
        (["campaign", "campaign id", "campaign state", "day", "cost", "impr.", "clicks", "conv. value"], "google_ads"),
        (["campaign name", "day", "amount spent (inr)", "impressions", "link clicks", "results"], "meta_ads"),
        (
            ["reporting starts", "reporting ends", "campaign name", "amount spent (usd)", "impressions", "results"],
            "meta_ads",
        ),
        (["campaign name", "start date (in utc)", "total spent", "impressions", "clicks"], "linkedin_ads"),
        (
            ["date", "campaign name", "spend", "impressions", "clicks", "7 day total sales", "7 day total orders (#)"],
            "amazon_ads",
        ),
        (["day", "channel", "campaign", "spend", "revenue"], "generic"),
        (["date", "name", "cost", "views"], "generic"),
    ],
)
def test_detect_format(headers, expected):
    fmt, confidence = detect_format(headers)
    assert fmt == expected
    assert 0 < confidence <= 1


def test_parse_number_variants():
    assert float(parse_number("1,234.56")) == pytest.approx(1234.56)
    assert parse_number('"45,678"') == 45678
    assert parse_number("₹1,234.00") == 1234
    assert parse_number("$ 12.5") == 12.5
    assert parse_number("--") == 0
    assert parse_number("") is None
    assert float(parse_number("1.234,56", european=True)) == pytest.approx(1234.56)
    assert float(parse_number("1.234,56")) == pytest.approx(1234.56)  # auto-detected European


def test_parse_day_variants():
    assert parse_day("2025-10-01") == date(2025, 10, 1)
    assert parse_day("2025/10/01") == date(2025, 10, 1)
    assert parse_day("Oct 1, 2025") == date(2025, 10, 1)
    assert parse_day("01/10/2025", day_first=True) == date(2025, 10, 1)
    assert parse_day("10/01/2025", day_first=False) == date(2025, 10, 1)
    assert parse_day("2025-10-01T00:00:00") == date(2025, 10, 1)
    assert parse_day("n/a") is None


# ---------------- parser on real-world shaped files ----------------
def test_parse_google_ads_export_with_preamble_and_totals():
    p = parse_csv((FIXTURES / "google_ads.csv").read_bytes())
    assert p.detected_format == "google_ads" and p.channel.value == "google"
    assert p.mapping["spend"] == "Cost" and p.mapping["day"] == "Day" and p.mapping["revenue"] == "Conv. value"
    assert p.mapping["external_id"] == "Campaign ID" and p.currency == "INR"
    assert len(p.rows) == 5 and p.skipped_rows == 2  # 2 "Total:" rows
    first = p.rows[0]
    assert first["day"] == date(2025, 10, 1) and first["external_id"] == "1234567890"
    assert float(first["spend"]) == pytest.approx(1234.56) and first["impressions"] == 45678 and first["clicks"] == 1234
    assert first["conversions"] == 12 and float(first["revenue"]) == pytest.approx(8900)
    dash = next(r for r in p.rows if r["day"] == date(2025, 10, 2) and r["external_id"] == "9876543210")
    assert dash["spend"] == 0 and dash["impressions"] == 0  # '--' placeholders
    assert "Campaign status" in p.unmapped_columns


def test_parse_meta_ads_manager_export():
    p = parse_csv((FIXTURES / "meta_ads.csv").read_bytes())  # has a UTF-8 BOM
    assert p.detected_format == "meta_ads" and p.channel.value == "meta"
    assert p.mapping["spend"] == "Amount spent (INR)" and p.currency == "INR"
    assert p.mapping["clicks"] == "Link clicks" and p.mapping["conversions"] == "Results"
    assert p.mapping["revenue"] == "Purchases conversion value" and p.mapping["day"] == "Day"
    assert len(p.rows) == 4
    r0 = p.rows[0]
    assert r0["campaign_name"] == "Summer Sale - Conversions" and r0["external_id"] == "summer-sale-conversions"
    assert float(r0["spend"]) == pytest.approx(1234.56) and r0["clicks"] == 1234 and r0["conversions"] == 12
    empty = p.rows[3]
    assert empty["spend"] == 0  # blank Amount spent


def test_parse_generic_with_channel_column_and_unknown_channel():
    p = parse_csv((FIXTURES / "generic.csv").read_bytes())
    assert p.detected_format == "generic" and p.channel is None
    chans = [r["channel"].value for r in p.rows]
    assert chans == ["google", "meta", "google", "other"]
    assert any("tiktok" in w for w in p.warnings)


def test_parse_semicolon_european_google_export():
    p = parse_csv((FIXTURES / "google_ads_de.csv").read_bytes())
    assert p.delimiter == ";" and p.detected_format == "google_ads"
    assert p.rows[0]["day"] == date(2025, 10, 1) and float(p.rows[0]["spend"]) == pytest.approx(1234.56)
    assert p.rows[0]["impressions"] == 45678


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        parse_csv(b"hello,world\n1,2\n")
    with pytest.raises(ValueError):
        parse_csv(b"")


# ---------------- endpoint ----------------
def test_dry_run_returns_mapping_preview_and_writes_nothing(ws):
    r = upload(ws, "google_ads.csv", dry_run=True)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "dry_run" and b["import_id"] is None and b["summary"] is None
    assert b["detected_format"] == "google_ads" and b["channel"] == "google" and b["currency"] == "INR"
    assert b["mapping"]["spend"] == "Cost" and b["row_count"] == 5 and len(b["preview"]) == 5
    assert b["preview"][0]["campaign_name"] == "Brand - Search" and b["preview"][0]["spend"] == 1234.56
    assert ws.get(f"{API}/campaigns").json() == [] and ws.get(f"{API}/imports").json() == []


def test_commit_google_export_creates_campaigns_and_metrics(ws):
    r = upload(ws, "google_ads.csv")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "completed" and b["import_id"]
    assert b["summary"] == {
        "rows_upserted": 5,
        "campaigns_created": 2,
        "campaigns_touched": 2,
        "first_day": "2025-10-01",
        "last_day": "2025-10-03",
    }
    camps = ws.get(f"{API}/campaigns").json()
    assert {c["external_id"] for c in camps} == {"1234567890", "9876543210"}
    assert all(c["channel"] == "google" for c in camps)
    rep = ws.get(f"{API}/reports/summary", params={"start": "2025-10-01", "end": "2025-10-03"}).json()
    assert rep["spend"] == pytest.approx(7434.56) and rep["impressions"] == 330678
    imp = ws.get(f"{API}/imports/{b['import_id']}").json()
    assert imp["source"] == "google_ads" and imp["filename"] == "google_ads.csv" and imp["rows_upserted"] == 5
    # re-import is idempotent (upsert on campaign+day)
    r2 = upload(ws, "google_ads.csv").json()
    assert r2["summary"]["campaigns_created"] == 0 and r2["summary"]["rows_upserted"] == 5
    assert ws.get(f"{API}/reports/summary", params={"start": "2025-10-01", "end": "2025-10-03"}).json()[
        "spend"
    ] == pytest.approx(7434.56)


def test_commit_meta_export(ws):
    b = upload(ws, "meta_ads.csv").json()
    assert b["detected_format"] == "meta_ads" and b["summary"]["campaigns_created"] == 2
    mix = ws.get(f"{API}/reports/by-channel", params={"start": "2025-10-01", "end": "2025-10-02"}).json()
    assert [c["channel"] for c in mix["channels"]] == ["meta"]
    assert mix["total_spend"] == pytest.approx(1234.56 + 1300 + 500.25)


def test_segmented_rows_are_summed(ws):
    b = upload(ws, "google_ads_segmented.csv").json()
    assert any("summed" in w for w in b["warnings"])
    assert b["summary"]["rows_upserted"] == 2  # 3 source rows -> 2 (campaign, day) rows
    rows = ws.get(f"{API}/metrics").json()
    by_day = {r["day"]: r for r in rows}
    assert float(by_day["2025-10-01"]["spend"]) == 150 and by_day["2025-10-01"]["impressions"] == 1500


def test_format_and_channel_override(ws):
    b = upload(ws, "generic.csv", dry_run=True, format="generic", channel="linkedin").json()
    # explicit channel column still wins; unknown 'tiktok' falls back to the override
    assert [r["channel"] for r in b["preview"]] == ["google", "meta", "google", "linkedin"]
    assert b["confidence"] == 1.0
    assert upload(ws, "generic.csv", format="nope").status_code == 422


def test_import_rejects_unparseable_file(ws):
    r = ws.post(f"{API}/imports/csv", files={"file": ("x.csv", b"foo,bar\n1,2\n", "text/csv")})
    assert r.status_code == 422 and "could not parse" in r.json()["detail"]


def test_imports_are_isolated(ws, other_ws):
    b = upload(ws, "meta_ads.csv").json()
    assert other_ws.get(f"{API}/imports").json() == []
    assert other_ws.get(f"{API}/imports/{b['import_id']}").status_code == 404
    assert other_ws.get(f"{API}/campaigns").json() == []


def test_import_emits_events(ws):
    upload(ws, "meta_ads.csv")
    types = [e["type"] for e in ws.get(f"{API}/events", params={"after": 0}).json()]
    assert types[-2:] == ["metrics.upserted", "import.completed"]
    assert types.count("campaign.changed") == 2
