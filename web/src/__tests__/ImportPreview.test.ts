import { mount } from '@vue/test-utils'
import ImportPreview from '../components/ImportPreview.vue'
import { preview } from './fixtures'

const factory = (p = {}) => mount(ImportPreview, { props: { preview: { ...preview, ...p }, fileName: 'export.csv', format: null, channel: null, currency: 'USD' } })

describe('ImportPreview (CSV dry-run)', () => {
  it('shows detected format, confidence, counts and the first rows', () => {
    const w = factory()
    const t = w.text()
    expect(t).toContain('Google Ads export')
    expect(t).toContain('92% confidence')
    expect(t).toContain('120')
    expect(t).toContain('2 skipped')
    expect(w.findAll('[data-testid="preview-row"]')).toHaveLength(2)
    expect(w.find('[data-testid="preview-row"]').text()).toContain('₹42.50') // currency from the file
  })
  it('lists the column mapping incl. defaults for missing optional fields', () => {
    const w = factory()
    const map = w.find('.mapping').text()
    expect(map).toContain('Cost')
    expect(map).toContain('defaults to 0')
    expect(map).toContain('Ignored columns')
    expect(map).toContain('Campaign status')
  })
  it('surfaces warnings and enables commit when the file is valid', async () => {
    const w = factory()
    expect(w.find('.warnings').text()).toContain('2 things to check')
    const btn = w.find('[data-testid="commit"]')
    expect(btn.attributes('disabled')).toBeUndefined()
    expect(btn.text()).toContain('Import 120 rows')
    await btn.trigger('click')
    expect(w.emitted('commit')).toHaveLength(1)
  })
  it('blocks commit when a required field is unmapped or no channel is known', () => {
    const noSpend = factory({ mapping: { ...preview.mapping, spend: null } })
    expect(noSpend.find('[data-testid="commit"]').attributes('disabled')).toBeDefined()
    expect(noSpend.text()).toContain('Required field Spend')
    const noChannel = factory({ channel: null, detected_format: 'generic' })
    expect(noChannel.find('[data-testid="commit"]').attributes('disabled')).toBeDefined()
    expect(noChannel.text()).toContain('Pick a channel')
  })
  it('emits format / channel overrides', async () => {
    const w = factory({ channel: null, detected_format: 'generic' })
    const selects = w.findAll('select')
    await selects[0].setValue('meta_ads')
    expect(w.emitted('update:format')?.[0]).toEqual(['meta_ads'])
    await selects[1].setValue('meta')
    expect(w.emitted('update:channel')?.[0]).toEqual(['meta'])
  })
})
