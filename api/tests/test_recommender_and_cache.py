import time

import pytest

from app.cache import InMemoryCache, make_key
from app.recommender import fit_curve, greedy_allocate, recommend

API = "/api/v1"


# ---------------- curve fitting ----------------
def test_fit_curve_recovers_power_law():
    a, b = 5.0, 0.7
    pts = [(s, a * s**b) for s in (100, 200, 400, 800, 1600)]
    c = fit_curve(pts)
    assert c.method == "loglog_ols"
    assert c.b == pytest.approx(b, abs=1e-6)
    assert c.a == pytest.approx(a, rel=1e-6)
    assert c.r2 == pytest.approx(1.0, abs=1e-6)


def test_fit_curve_clamps_slope_to_diminishing_returns():
    pts = [(s, 2 * s**1.3) for s in (100, 200, 400, 800)]  # increasing returns -> clamp
    c = fit_curve(pts)
    assert c.b <= 0.95
    assert c.marginal_roas(100) > c.marginal_roas(1000)  # concave


def test_fit_curve_fallback_with_sparse_data():
    c = fit_curve([(100.0, 300.0)])
    assert c.method == "fallback_avg_roas" and c.n_points == 1
    assert c.revenue(100.0) == pytest.approx(300.0)


def test_fit_curve_constant_spend_uses_default_slope():
    c = fit_curve([(100.0, 300.0), (100.0, 310.0), (100.0, 290.0)])
    assert c.method == "anchored_default_slope" and c.b == 0.8


# ---------------- allocation ----------------
def test_greedy_allocation_sums_to_budget_and_favors_stronger_channel():
    curves = {
        "google": fit_curve([(s, 4 * s**0.8 * 1000**0.2) for s in (600, 800, 1000, 1200, 1400)]),
        "meta": fit_curve([(s, 1.5 * s**0.8 * 800**0.2) for s in (500, 650, 800, 950, 1100)]),
    }
    alloc = greedy_allocate(curves, 10_000.0, {"google": 1000.0, "meta": 800.0}, min_share=0.05)
    assert sum(alloc.values()) == pytest.approx(10_000.0, abs=1e-6)
    assert alloc["google"] > alloc["meta"] >= 500.0


def test_greedy_allocation_equalises_marginal_roas_when_unconstrained():
    curves = {
        "a": fit_curve([(s, 3 * s**0.6) for s in (100, 200, 400, 800)]),
        "b": fit_curve([(s, 2 * s**0.7) for s in (100, 200, 400, 800)]),
    }
    alloc = greedy_allocate(curves, 5000.0, {"a": 1000.0, "b": 1000.0}, min_share=0.0, steps=2000)
    ma, mb = curves["a"].marginal_roas(alloc["a"]), curves["b"].marginal_roas(alloc["b"])
    assert ma == pytest.approx(mb, rel=0.05)


def test_greedy_allocation_respects_max_shift():
    curves = {
        "google": fit_curve([(s, 4 * s**0.8) for s in (600, 800, 1000, 1200)]),
        "meta": fit_curve([(s, 1.0 * s**0.8) for s in (600, 800, 1000, 1200)]),
    }
    current = {"google": 1000.0, "meta": 1000.0}
    alloc = greedy_allocate(curves, 2000.0, current, min_share=0.0, max_shift_pct=0.2)
    assert alloc["google"] <= 1200.0 + 1e-6 and alloc["meta"] >= 800.0 - 1e-6
    assert sum(alloc.values()) == pytest.approx(2000.0)


def test_recommend_payload_has_explanations():
    history = {
        "google": [(s, 4.0 * s) for s in (600, 800, 1000, 1200, 1400)],
        "meta": [(s, 1.5 * s) for s in (500, 650, 800, 950, 1100)],
    }
    rec = recommend(history, total_budget=10_000)
    assert rec["total_budget"] == 10_000
    assert {c["channel"] for c in rec["channels"]} == {"google", "meta"}
    g = next(c for c in rec["channels"] if c["channel"] == "google")
    assert g["delta"] > 0 and "Increase google" in g["explanation"]
    assert "marginal ROAS" in g["explanation"]
    assert rec["projected_uplift"] >= 0
    assert "Reallocating" in rec["summary"]


def test_recommend_defaults_budget_to_current_spend():
    history = {"google": [(1000.0, 4000.0)] * 5, "meta": [(500.0, 800.0)] * 5}
    rec = recommend(history, total_budget=None)
    assert rec["total_budget"] == 1500.0


def test_recommend_empty_history():
    rec = recommend({}, total_budget=1000)
    assert rec["channels"] == [] and rec["projected_uplift"] == 0


# ---------------- recommendation endpoint ----------------
def test_recommendations_get_endpoint(seeded):
    ws = seeded["ws"]
    r = ws.get(f"{API}/recommendations", params={"total_budget": 3000, "lookback_days": 30})
    assert r.status_code == 200, r.text
    body = r.json()
    by = {c["channel"]: c for c in body["channels"]}
    assert sum(c["recommended_daily_spend"] for c in by.values()) == pytest.approx(3000, abs=0.05)
    assert by["google"]["recommended_daily_spend"] > by["meta"]["recommended_daily_spend"]
    assert by["google"]["curve"]["method"] == "loglog_ols"
    assert all(c["explanation"] for c in by.values())
    assert body["window_start"] < body["window_end"]


def test_recommendations_post_matches_get(seeded):
    ws = seeded["ws"]
    g = ws.get(f"{API}/recommendations", params={"total_budget": 3000}).json()
    p = ws.post(f"{API}/recommendations/budget", json={"total_budget": 3000}).json()
    assert g == p


def test_recommendations_cached_and_validated(seeded):
    ws = seeded["ws"]
    url = f"{API}/recommendations"
    assert ws.get(url, params={"total_budget": 3000}).headers["X-Cache"] == "MISS"
    assert ws.get(url, params={"total_budget": 3000}).headers["X-Cache"] == "HIT"
    assert ws.get(url, params={"total_budget": 2999}).headers["X-Cache"] == "MISS"
    assert ws.get(url, params={"total_budget": -1}).status_code == 422
    assert ws.get(url, params={"lookback_days": 2}).status_code == 422


def test_recommendations_empty_workspace(ws):
    r = ws.get(f"{API}/recommendations", params={"total_budget": 1000})
    assert r.status_code == 200 and r.json()["channels"] == []


# ---------------- cache unit ----------------
def test_make_key_is_stable_and_namespaced():
    k1 = make_key(7, "trend", {"start": "2024-01-01", "group_by": "channel"})
    k2 = make_key(7, "trend", {"group_by": "channel", "start": "2024-01-01"})
    assert k1 == k2 and k1.startswith("cm:7:trend:")
    assert make_key(8, "trend", {"start": "2024-01-01", "group_by": "channel"}) != k1


def test_memory_cache_ttl_and_invalidate():
    c = InMemoryCache()
    c.set("cm:1:a", {"x": 1}, ttl=60, workspace_id=1)
    c.set("cm:1:b", {"x": 2}, ttl=60, workspace_id=1)
    c.set("cm:2:a", {"x": 3}, ttl=60, workspace_id=2)
    assert c.get("cm:1:a") == {"x": 1}
    assert c.invalidate_workspace(1) == 2
    assert c.get("cm:1:a") is None and c.get("cm:1:b") is None
    assert c.get("cm:2:a") == {"x": 3}
    c.set("cm:3:a", 1, ttl=0, workspace_id=3)
    time.sleep(0.01)
    assert c.get("cm:3:a") is None
    assert c.hits == 2 and c.misses == 3


def test_memory_cache_is_bounded_lru():
    c = InMemoryCache(max_entries=3)
    for i in range(3):
        c.set(f"cm:1:k{i}", i, ttl=60, workspace_id=1)
    assert c.get("cm:1:k0") == 0  # touch -> most recently used
    c.set("cm:2:k3", 3, ttl=60, workspace_id=2)  # evicts k1 (least recently used)
    assert len(c) == 3 and c.evictions == 1
    assert c.get("cm:1:k1") is None and c.get("cm:1:k0") == 0 and c.get("cm:2:k3") == 3
    assert c.invalidate_workspace(1) == 2  # k0 + k2 (evicted k1 no longer indexed)
    assert len(c) == 1
