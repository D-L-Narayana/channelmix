import { greedyAllocate, marginalRoas, reallocate } from '../lib/recommender'
import rec from '../mock/recommendation.json'
import type { RecommendationResponse } from '../lib/types'

const base = rec as RecommendationResponse

describe('client-side recommender (demo mode)', () => {
  it('allocations sum to the budget and favour the higher marginal ROAS curve', () => {
    const curves = {
      google: { a: 8, b: 0.9, r2: 1, n_points: 10, method: 'test' },
      meta: { a: 4, b: 0.8, r2: 1, n_points: 10, method: 'test' },
    }
    const alloc = greedyAllocate(curves, 10000, { google: 1000, meta: 1000 }, 0.05)
    expect(alloc.google + alloc.meta).toBeCloseTo(10000, 6)
    expect(alloc.google).toBeGreaterThan(alloc.meta)
    expect(alloc.meta).toBeGreaterThanOrEqual(500)
  })

  it('respects the max shift cap', () => {
    const curves = {
      google: { a: 8, b: 0.9, r2: 1, n_points: 10, method: 'test' },
      meta: { a: 1, b: 0.8, r2: 1, n_points: 10, method: 'test' },
    }
    const alloc = greedyAllocate(curves, 2000, { google: 1000, meta: 1000 }, 0, 0.1)
    expect(alloc.google).toBeLessThanOrEqual(1100 + 1e-6)
    expect(alloc.meta).toBeGreaterThanOrEqual(900 - 1e-6)
  })

  it('marginal ROAS decreases with spend (diminishing returns)', () => {
    const c = { a: 5, b: 0.7, r2: null, n_points: 3, method: 'test' }
    expect(marginalRoas(c, 100)).toBeGreaterThan(marginalRoas(c, 1000))
  })

  it('reallocate rebuilds explanations for a new budget', () => {
    const out = reallocate(base, 5000, 0.05, null)
    expect(out.total_budget).toBe(5000)
    expect(out.channels.reduce((a, c) => a + c.recommended_daily_spend, 0)).toBeCloseTo(5000, 0)
    expect(out.channels.every((c) => /marginal ROAS/.test(c.explanation))).toBe(true)
    expect(out.summary).toContain('$5,000/day')
  })
})
