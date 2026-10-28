import { compact, daysBetween, delta, money, pct, previousRange, roas, slugify } from '../lib/format'

describe('format helpers', () => {
  it('formats money with currency and digits', () => {
    expect(money(1234.5, 'USD')).toBe('$1,235')
    expect(money(1234.5, 'USD', 2)).toBe('$1,234.50')
    expect(money(null)).toBe('–')
    expect(money('99.9', 'EUR', 1)).toBe('€99.9')
  })
  it('compacts large numbers and keeps small ones exact', () => {
    expect(compact(0, 'USD')).toBe('$0')
    expect(compact(42.5, 'USD')).toBe('$42.50')
    expect(compact(1_234_567)).toBe('1.23M')
    expect(compact(250_000, 'USD')).toBe('$250.0K')
  })
  it('pct / roas / delta', () => {
    expect(pct(0.1234, 1, true)).toBe('+12.3%')
    expect(pct(-0.05)).toBe('-5.0%')
    expect(roas(3.456)).toBe('3.46×')
    expect(delta(110, 100)).toBeCloseTo(0.1)
    expect(delta(110, 0)).toBeNull()
  })
  it('date ranges', () => {
    expect(daysBetween('2025-10-01', '2025-10-07')).toBe(7)
    expect(previousRange({ start: '2025-10-08', end: '2025-10-14' })).toEqual({ start: '2025-10-01', end: '2025-10-07' })
  })
  it('slugify', () => {
    expect(slugify('Acme Retail  (India)!')).toBe('acme-retail-india')
  })
})
