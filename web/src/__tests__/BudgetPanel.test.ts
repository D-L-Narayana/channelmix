import { mount } from '@vue/test-utils'
import BudgetPanel from '../components/BudgetPanel.vue'
import rec from '../mock/recommendation.json'
import type { RecommendationResponse } from '../lib/types'

const result = rec as RecommendationResponse

describe('BudgetPanel', () => {
  it('shows one recommendation card per channel with an explanation', () => {
    const w = mount(BudgetPanel, { props: { result } })
    const cards = w.findAll('[data-testid="recommendation"]')
    expect(cards).toHaveLength(result.channels.length)
    for (const c of cards) expect(c.find('[data-testid="explanation"]').text()).toMatch(/marginal ROAS/)
    expect(w.find('[data-testid="summary"]').text()).toContain('Reallocating')
    expect(w.find('[data-testid="uplift"]').text()).toMatch(/projected \+?[\d.]+% revenue/)
  })

  it('marks increases green and decreases red', () => {
    const w = mount(BudgetPanel, { props: { result } })
    const deltas = w.findAll('[data-testid="delta"]')
    const up = result.channels.findIndex((c) => c.delta > 0)
    const down = result.channels.findIndex((c) => c.delta < 0)
    expect(deltas[up].classes()).toContain('good')
    expect(deltas[down].classes()).toContain('bad')
  })

  it('emits a run request with the chosen budget and shift cap', async () => {
    const w = mount(BudgetPanel, { props: { result } })
    await w.find('[data-testid="budget-input"]').setValue(5000)
    await w.find('[data-testid="max-shift"]').setValue(20)
    await w.find('form').trigger('submit')
    const [payload] = w.emitted('run')![0] as [Record<string, unknown>]
    expect(payload.total_budget).toBe(5000)
    expect(payload.max_shift_pct).toBeCloseTo(0.2)
    expect(payload.min_share).toBeCloseTo(0.05)
  })
})
