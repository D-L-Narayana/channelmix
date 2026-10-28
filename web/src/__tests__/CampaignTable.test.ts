import { mount } from '@vue/test-utils'
import CampaignTable from '../components/CampaignTable.vue'
import rows from '../mock/campaign_report.json'
import type { CampaignPerformanceRow } from '../lib/types'

const data = rows as CampaignPerformanceRow[]

describe('CampaignTable', () => {
  it('renders every campaign and a totals row', () => {
    const w = mount(CampaignTable, { props: { rows: data } })
    expect(w.findAll('[data-testid="campaign-row"]')).toHaveLength(data.length)
    expect(w.find('tfoot').text()).toContain('Total')
  })

  it('filters by channel through v-model:selected', async () => {
    const w = mount(CampaignTable, { props: { rows: data, selected: 'meta' } })
    const shown = w.findAll('[data-testid="campaign-row"]')
    expect(shown).toHaveLength(data.filter((r) => r.channel === 'meta').length)
    await w.find('[data-testid="filter-google"]').trigger('click')
    expect(w.emitted('update:selected')?.[0]).toEqual(['google'])
  })

  it('sorts by the clicked column and searches by name', async () => {
    const w = mount(CampaignTable, { props: { rows: data } })
    // default: spend desc
    const firstSpend = w.findAll('[data-testid="campaign-row"]')[0].findAll('td')[3].text()
    const top = [...data].sort((a, b) => b.spend - a.spend)[0]
    expect(firstSpend).toBe(top.spend.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }))
    const headers = w.findAll('th')
    await headers.find((h) => h.text().startsWith('Campaign'))!.trigger('click')
    const names = w.findAll('[data-testid="campaign-row"]').map((r) => r.findAll('td')[0].text())
    expect(names).toEqual([...names].sort())
    await w.find('[data-testid="search"]').setValue('retarget')
    expect(w.findAll('[data-testid="campaign-row"]').every((r) => r.text().toLowerCase().includes('retarget'))).toBe(true)
  })
})
