import { mount } from '@vue/test-utils'
import CampaignTable from '../components/CampaignTable.vue'
import { campaigns, perfRows } from './fixtures'

const factory = (props = {}) => mount(CampaignTable, { props: { rows: perfRows, campaigns, days: 7, currency: 'USD', ...props } })
const names = (w: ReturnType<typeof factory>) => w.findAll('[data-testid="campaign-row"] .n').map((n) => n.text())

describe('CampaignTable', () => {
  it('renders every campaign sorted by spend desc with a totals row', () => {
    const w = factory()
    expect(names(w)).toEqual(['Brand search', 'Generic search', 'Retargeting — cart', 'Sponsored products'])
    expect(w.find('tfoot').text()).toContain('Total')
    expect(w.find('tfoot').text()).toContain('$7,400')
  })
  it('filters by channel through the chips and emits update:channel', async () => {
    const w = factory({ channel: 'google' })
    expect(names(w)).toHaveLength(2)
    await w.find('[data-testid="filter-meta"]').trigger('click')
    expect(w.emitted('update:channel')?.[0]).toEqual(['meta'])
  })
  it('sorts by a clicked column header and searches by name', async () => {
    const w = factory()
    const roasHeader = w.findAll('th').find((h) => h.text().startsWith('ROAS'))!
    await roasHeader.find('button').trigger('click') // desc first for numeric
    expect(names(w)[0]).toMatch(/Brand search|Retargeting/)
    await roasHeader.find('button').trigger('click') // asc
    expect(names(w)[0]).toMatch(/Generic search|Sponsored products/)
    await w.find('[data-testid="search"] input').setValue('retarget')
    expect(names(w)).toEqual(['Retargeting — cart'])
  })
  it('computes pacing from daily budget and shows a dash without one', () => {
    const w = factory()
    const rows = w.findAll('tbody tr')
    // Brand search: 3000 / 7 days = 428.6/day of 500 budget -> 86%
    expect(rows[0].text()).toContain('86%')
    // Retargeting has budget 0 -> dash
    expect(rows[2].find('.pace').exists()).toBe(false)
  })
  it('emits open with the campaign id when a row is activated by keyboard', async () => {
    const w = factory()
    await w.findAll('tbody tr')[1].trigger('keydown.enter')
    expect(w.emitted('open')?.[0]).toEqual([2])
  })
})
