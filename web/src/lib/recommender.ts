/**
 * Client-side mirror of the API's greedy marginal allocator.
 *
 * Used only in demo/offline mode: the per-channel response curves
 * (revenue = a * spend^b) fitted by the API are bundled in the mock payload,
 * so the panel can re-run the allocation locally when the user changes the
 * budget or the shift cap without a backend.
 */
import type { ChannelRecommendation, CurveFit, RecommendationResponse } from './types'

const STEPS = 400

export function revenueAt(curve: CurveFit, spend: number): number {
  return spend > 0 ? curve.a * Math.pow(spend, curve.b) : 0
}

export function marginalRoas(curve: CurveFit, spend: number): number {
  return spend > 0 ? curve.a * curve.b * Math.pow(spend, curve.b - 1) : Infinity
}

export function greedyAllocate(
  curves: Record<string, CurveFit>,
  totalBudget: number,
  current: Record<string, number>,
  minShare = 0.05,
  maxShiftPct: number | null = null,
): Record<string, number> {
  const channels = Object.keys(curves)
  const floor: Record<string, number> = {}
  const cap: Record<string, number> = {}
  for (const c of channels) {
    floor[c] = totalBudget * minShare
    cap[c] = totalBudget
    const cur = current[c] ?? 0
    if (maxShiftPct !== null && cur > 0) {
      floor[c] = Math.max(floor[c], cur * (1 - maxShiftPct))
      cap[c] = Math.min(cap[c], cur * (1 + maxShiftPct))
    }
  }
  const alloc = { ...floor }
  const floorSum = Object.values(alloc).reduce((a, b) => a + b, 0)
  if (floorSum > totalBudget) {
    const scale = totalBudget / floorSum
    for (const c of channels) alloc[c] *= scale
    return alloc
  }
  const step = (totalBudget - floorSum) / STEPS
  for (let i = 0; i < STEPS; i++) {
    let best: string | null = null
    let bestM = -1
    for (const c of channels) {
      if (alloc[c] + step > cap[c] + 1e-9) continue
      const m = marginalRoas(curves[c], alloc[c])
      if (m > bestM) {
        bestM = m
        best = c
      }
    }
    if (best === null) {
      for (const c of channels) alloc[c] += step / channels.length
    } else {
      alloc[best] += step
    }
  }
  return alloc
}

const fmt0 = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 0 })

/** Re-run the allocation on top of a server-produced recommendation (demo mode). */
export function reallocate(
  base: RecommendationResponse,
  totalBudget: number,
  minShare: number,
  maxShiftPct: number | null,
): RecommendationResponse {
  const curves: Record<string, CurveFit> = {}
  const current: Record<string, number> = {}
  for (const ch of base.channels) {
    curves[ch.channel] = ch.curve
    current[ch.channel] = ch.current_daily_spend
  }
  const alloc = greedyAllocate(curves, totalBudget, current, minShare, maxShiftPct)
  let currentRev = 0
  let recRev = 0
  const channels: ChannelRecommendation[] = base.channels.map((ch) => {
    const rec = alloc[ch.channel]
    const cur = ch.current_daily_spend
    const delta = rec - cur
    currentRev += revenueAt(ch.curve, cur)
    recRev += revenueAt(ch.curve, rec)
    const mCur = marginalRoas(ch.curve, cur)
    const mRec = marginalRoas(ch.curve, rec)
    const verdict =
      Math.abs(delta) < Math.max(1, 0.01 * totalBudget)
        ? `Hold ${ch.channel} roughly flat at $${fmt0(rec)}/day`
        : delta > 0
          ? `Increase ${ch.channel} by $${fmt0(delta)}/day (${((delta / cur) * 100).toFixed(0)}%)`
          : `Decrease ${ch.channel} by $${fmt0(-delta)}/day (${((delta / cur) * 100).toFixed(0)}%)`
    return {
      ...ch,
      recommended_daily_spend: Math.round(rec * 100) / 100,
      delta: Math.round(delta * 100) / 100,
      delta_pct: cur ? delta / cur : null,
      marginal_roas_at_current: isFinite(mCur) ? mCur : null,
      marginal_roas_at_recommended: isFinite(mRec) ? mRec : null,
      projected_daily_revenue: revenueAt(ch.curve, rec),
      explanation: `${verdict}: fitted curve revenue = ${ch.curve.a.toFixed(2)} * spend^${ch.curve.b.toFixed(2)} (${ch.curve.method}, n=${ch.curve.n_points}${ch.curve.r2 !== null ? `, R2=${ch.curve.r2}` : ''}); marginal ROAS ${mCur.toFixed(2)} at current spend -> ${mRec.toFixed(2)} at recommended spend.`,
    }
  })
  channels.sort((x, y) => y.recommended_daily_spend - x.recommended_daily_spend)
  const uplift = recRev - currentRev
  const winners = channels.filter((c) => c.delta > 0).map((c) => c.channel)
  const losers = channels.filter((c) => c.delta < 0).map((c) => c.channel)
  return {
    ...base,
    total_budget: totalBudget,
    channels,
    current_projected_revenue: currentRev,
    recommended_projected_revenue: recRev,
    projected_uplift: uplift,
    projected_uplift_pct: currentRev ? uplift / currentRev : null,
    summary:
      `Reallocating $${fmt0(totalBudget)}/day` +
      (winners.length ? ` toward ${winners.join(', ')}` : '') +
      (losers.length ? ` and away from ${losers.join(', ')}` : '') +
      ` is projected to lift daily revenue by $${fmt0(uplift)}` +
      (currentRev ? ` (${uplift >= 0 ? '+' : ''}${((uplift / currentRev) * 100).toFixed(1)}%)` : '') +
      '. Marginal ROAS is equalised across channels where floors/caps allow.',
  }
}
