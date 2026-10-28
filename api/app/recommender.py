"""Budget reallocation recommender.

1. For each channel fit a diminishing-returns response curve
       revenue(spend) = a * spend ** b          (0 < b < 1)
   from historical daily (spend, revenue) points via ordinary least squares in
   log-log space. ``b`` is clamped to (B_MIN, B_MAX) so the curve is concave
   (diminishing returns) and the marginal ROAS d(rev)/d(spend) = a*b*spend^(b-1)
   is strictly decreasing, which makes greedy marginal allocation optimal.
2. Greedy marginal allocation: start every channel at its floor (min_share of
   the budget), then hand out the remaining budget in small increments, each
   time to the channel with the highest marginal ROAS at its current level.
   Optional max_shift_pct caps how far a channel can move from its current spend.
3. Produce a human-readable explanation per channel plus an overall summary.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

B_MIN, B_MAX = 0.35, 0.95
DEFAULT_B = 0.80
STEPS = 400


@dataclass
class Curve:
    a: float
    b: float
    r2: float | None
    n_points: int
    method: str

    def revenue(self, spend: float) -> float:
        return self.a * spend**self.b if spend > 0 else 0.0

    def marginal_roas(self, spend: float) -> float:
        if spend <= 0:
            return float("inf")
        return self.a * self.b * spend ** (self.b - 1)


def fit_curve(points: list[tuple[float, float]]) -> Curve:
    """Fit revenue = a * spend^b by OLS on log(spend), log(revenue)."""
    pts = [(s, r) for s, r in points if s > 0 and r > 0]
    total_s = sum(s for s, _ in points)
    total_r = sum(r for _, r in points)
    if len(pts) < 3:
        # Not enough signal: assume default concavity and anchor on average ROAS.
        avg_spend = total_s / len(points) if points else 1.0
        roas = total_r / total_s if total_s else 0.0
        a = roas * avg_spend ** (1 - DEFAULT_B) if avg_spend > 0 else 0.0
        return Curve(a=a, b=DEFAULT_B, r2=None, n_points=len(points), method="fallback_avg_roas")

    xs = [math.log(s) for s, _ in pts]
    ys = [math.log(r) for _, r in pts]
    n = len(pts)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    if sxx < 1e-9:  # all days spent the same amount -> slope undefined
        b = DEFAULT_B
        method = "anchored_default_slope"
    else:
        b = min(B_MAX, max(B_MIN, sxy / sxx))
        method = "loglog_ols"
    # Re-anchor intercept with the clamped slope so the curve passes through the centroid.
    ln_a = my - b * mx
    a = math.exp(ln_a)
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (ln_a + b * x)) ** 2 for x, y in zip(xs, ys, strict=True))
    r2 = round(1 - ss_res / ss_tot, 4) if ss_tot > 1e-12 else None
    return Curve(a=a, b=b, r2=r2, n_points=n, method=method)


def greedy_allocate(
    curves: dict[str, Curve],
    total_budget: float,
    current: dict[str, float],
    min_share: float = 0.05,
    max_shift_pct: float | None = None,
    steps: int = STEPS,
) -> dict[str, float]:
    channels = list(curves)
    if not channels:
        return {}
    floor = {c: total_budget * min_share for c in channels}
    cap = {c: total_budget for c in channels}
    if max_shift_pct is not None:
        for c in channels:
            cur = current.get(c, 0.0)
            if cur > 0:
                floor[c] = max(floor[c], cur * (1 - max_shift_pct))
                cap[c] = min(cap[c], cur * (1 + max_shift_pct))
    alloc = dict(floor)
    remaining = total_budget - sum(alloc.values())
    if remaining < 0:  # floors over-constrained; scale down proportionally
        scale = total_budget / sum(alloc.values())
        return {c: v * scale for c, v in alloc.items()}
    step = remaining / steps if steps else remaining
    for _ in range(steps):
        best, best_m = None, -1.0
        for c in channels:
            if alloc[c] + step > cap[c] + 1e-9:
                continue
            m = curves[c].marginal_roas(alloc[c])
            if m > best_m:
                best, best_m = c, m
        if best is None:  # every channel capped -> spread evenly
            for c in channels:
                alloc[c] += step / len(channels)
            continue
        alloc[best] += step
    # fix floating drift so the result sums exactly to the budget
    drift = total_budget - sum(alloc.values())
    alloc[max(alloc, key=alloc.get)] += drift
    return alloc


def _fmt(x: float) -> str:
    return f"{x:,.0f}"


def recommend(
    history: dict[str, list[tuple[float, float]]],
    total_budget: float | None,
    min_share: float = 0.05,
    max_shift_pct: float | None = None,
) -> dict:
    """Return the full recommendation payload (dict matching RecommendationResponse minus account meta)."""
    current = {c: (sum(s for s, _ in pts) / len(pts) if pts else 0.0) for c, pts in history.items()}
    current_roas = {
        c: (sum(r for _, r in pts) / sum(s for s, _ in pts) if sum(s for s, _ in pts) else None)
        for c, pts in history.items()
    }
    budget = float(total_budget) if total_budget else sum(current.values())
    curves = {c: fit_curve(pts) for c, pts in history.items()}
    alloc = greedy_allocate(curves, budget, current, min_share, max_shift_pct)

    current_rev = sum(curves[c].revenue(current[c]) for c in curves)
    rec_rev = sum(curves[c].revenue(alloc[c]) for c in curves)
    channels = []
    for c in sorted(curves, key=lambda k: alloc[k], reverse=True):
        cur, rec, curve = current[c], alloc[c], curves[c]
        delta = rec - cur
        m_cur = curve.marginal_roas(cur) if cur > 0 else None
        m_rec = curve.marginal_roas(rec) if rec > 0 else None
        if abs(delta) < max(1.0, 0.01 * budget):
            verdict = f"Hold {c} roughly flat at ${_fmt(rec)}/day"
        elif delta > 0:
            verdict = (
                f"Increase {c} by ${_fmt(delta)}/day ({delta / cur * 100:+.0f}%)"
                if cur
                else f"Fund {c} at ${_fmt(rec)}/day"
            )
        else:
            verdict = f"Decrease {c} by ${_fmt(-delta)}/day ({delta / cur * 100:+.0f}%)"
        reason = (
            f"fitted curve revenue = {curve.a:.2f} * spend^{curve.b:.2f} "
            f"({curve.method}, n={curve.n_points}" + (f", R2={curve.r2}" if curve.r2 is not None else "") + "); "
            f"marginal ROAS {m_cur:.2f} at current spend"
            if m_cur is not None
            else "no historical spend"
        )
        if m_rec is not None and m_cur is not None:
            reason += f" -> {m_rec:.2f} at recommended spend"
        channels.append(
            {
                "channel": c,
                "current_daily_spend": round(cur, 2),
                "recommended_daily_spend": round(rec, 2),
                "delta": round(delta, 2),
                "delta_pct": round(delta / cur, 4) if cur else None,
                "current_roas": round(current_roas[c], 4) if current_roas[c] is not None else None,
                "marginal_roas_at_current": round(m_cur, 4) if m_cur not in (None, float("inf")) else None,
                "marginal_roas_at_recommended": round(m_rec, 4) if m_rec not in (None, float("inf")) else None,
                "projected_daily_revenue": round(curve.revenue(rec), 2),
                "curve": {
                    "a": round(curve.a, 4),
                    "b": round(curve.b, 4),
                    "r2": curve.r2,
                    "n_points": curve.n_points,
                    "method": curve.method,
                },
                "explanation": f"{verdict}: {reason}.",
            }
        )
    uplift = rec_rev - current_rev
    winners = [x["channel"] for x in channels if x["delta"] > 0]
    losers = [x["channel"] for x in channels if x["delta"] < 0]
    summary = (
        f"Reallocating ${_fmt(budget)}/day"
        + (f" toward {', '.join(winners)}" if winners else "")
        + (f" and away from {', '.join(losers)}" if losers else "")
        + f" is projected to lift daily revenue by ${_fmt(uplift)}"
        + (f" ({uplift / current_rev * 100:+.1f}%)" if current_rev else "")
        + ". Marginal ROAS is equalised across channels where floors/caps allow."
    )
    return {
        "total_budget": round(budget, 2),
        "current_projected_revenue": round(current_rev, 2),
        "recommended_projected_revenue": round(rec_rev, 2),
        "projected_uplift": round(uplift, 2),
        "projected_uplift_pct": round(uplift / current_rev, 4) if current_rev else None,
        "channels": channels,
        "summary": summary,
        "method": "power-law response curves (log-log OLS) + greedy marginal allocation",
    }
