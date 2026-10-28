import { mount } from '@vue/test-utils'
import KpiRow from '../components/KpiRow.vue'
import { summary } from './fixtures'

describe('KpiRow', () => {
  it('renders six tiles with values and WoW deltas (arrow + sign, not colour alone)', () => {
    const w = mount(KpiRow, { props: { report: summary, currency: 'USD' } })
    expect(w.findAll('.tile')).toHaveLength(6)
    const spend = w.find('[data-testid="kpi-spend"]')
    expect(spend.text()).toContain('$12,346')
    expect(spend.text()).toContain('↑')
    expect(spend.text()).toContain('+12.2%')
    expect(spend.text()).toContain('WoW')
    expect(spend.find('.delta').classes()).toContain('neutral') // volume metrics are not judged good/bad
    expect(w.find('[data-testid="kpi-conversions"] .delta').classes()).toContain('down')
  })
  it('treats a rising CPA as worse and a missing delta as "no prior data"', () => {
    const w = mount(KpiRow, { props: { report: { ...summary, delta_pct: { ...summary.delta_pct, roas: null } }, currency: 'USD' } })
    const cpa = w.find('[data-testid="kpi-cpa"]')
    expect(cpa.text()).toContain('$102.88')
    expect(cpa.find('.delta').classes()).toContain('down')
    expect(w.find('[data-testid="kpi-roas"]').text()).toContain('no prior data')
  })
  it('shows sized skeletons while loading (no layout shift)', () => {
    const w = mount(KpiRow, { props: { report: null, loading: true, currency: 'USD' } })
    expect(w.findAll('.tile')).toHaveLength(6)
    expect(w.findAll('.sk').length).toBeGreaterThan(0)
  })
})
