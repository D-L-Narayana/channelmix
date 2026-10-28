import { mount } from '@vue/test-utils'
import ChannelMixChart from '../components/ChannelMixChart.vue'
import DateRangeFilter from '../components/DateRangeFilter.vue'
import KpiCards from '../components/KpiCards.vue'
import mix from '../mock/channel_mix.json'
import type { ChannelMixReport } from '../lib/types'

const report = mix as ChannelMixReport

describe('ChannelMixChart', () => {
  it('lists each channel with share and ROAS and toggles donut/bar', async () => {
    const w = mount(ChannelMixChart, { props: { report } })
    const rows = w.findAll('[data-testid="mix-table"] tbody tr')
    expect(rows).toHaveLength(3)
    expect(w.text()).toContain('Google Ads')
    expect(w.text()).toMatch(/\d+\.\d%/)
    await w.find('[data-testid="mode-bar"]').trigger('click')
    expect(w.find('[data-testid="mode-bar"]').classes()).toContain('active')
  })

  it('emits select when a channel row is clicked', async () => {
    const w = mount(ChannelMixChart, { props: { report } })
    await w.findAll('[data-testid="mix-table"] tbody tr')[0].trigger('click')
    expect(w.emitted('select')?.[0]).toEqual([report.channels[0].channel])
  })

  it('shows skeletons while loading', () => {
    const w = mount(ChannelMixChart, { props: { report: null, loading: true } })
    expect(w.find('.skeleton').exists()).toBe(true)
  })
})

describe('KpiCards', () => {
  it('computes blended KPIs from the report', () => {
    const w = mount(KpiCards, { props: { report } })
    expect(w.text()).toContain('Total spend')
    expect(w.text()).toContain(`${report.blended_roas!.toFixed(2)}x`)
  })
})

describe('DateRangeFilter', () => {
  it('emits a 7-day window anchored to the given date', async () => {
    const w = mount(DateRangeFilter, { props: { modelValue: { start: '2024-01-01', end: '2024-01-31' }, anchor: '2024-01-31' } })
    await w.find('[data-testid="preset-7D"]').trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual([{ start: '2024-01-25', end: '2024-01-31' }])
  })
})
