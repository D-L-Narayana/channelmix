const NBSP = '\u00a0'

export const money = (n: number | string | null | undefined, currency = 'USD', digits = 0) => {
  const v = typeof n === 'string' ? Number(n) : n
  if (v === null || v === undefined || Number.isNaN(v)) return '–'
  try {
    return v.toLocaleString('en-US', { style: 'currency', currency, maximumFractionDigits: digits, minimumFractionDigits: digits })
  } catch {
    return `${currency}${NBSP}${num(v, digits)}`
  }
}

/** 1.2K / 3.4M style for KPI tiles; full digits below 10k */
export const compact = (n: number | null | undefined, currency?: string) => {
  if (n === null || n === undefined || Number.isNaN(n)) return '–'
  const abs = Math.abs(n)
  const fmt = (v: number, d: number) =>
    currency ? money(v, currency, d) : v.toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d })
  if (abs >= 1_000_000_000) return `${fmt(n / 1_000_000_000, 2)}B`
  if (abs >= 1_000_000) return `${fmt(n / 1_000_000, 2)}M`
  if (abs >= 100_000) return `${fmt(n / 1_000, 1)}K`
  return fmt(n, currency ? (abs < 100 ? 2 : 0) : 0)
}

export const num = (n: number | string | null | undefined, digits = 0) => {
  const v = typeof n === 'string' ? Number(n) : n
  if (v === null || v === undefined || Number.isNaN(v)) return '–'
  return v.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits })
}

export const pct = (n: number | null | undefined, digits = 1, signed = false) =>
  n === null || n === undefined || Number.isNaN(n) ? '–' : `${signed && n > 0 ? '+' : ''}${(n * 100).toFixed(digits)}%`

export const roas = (n: number | null | undefined) => (n === null || n === undefined || Number.isNaN(n) ? '–' : `${n.toFixed(2)}×`)

/** Week-over-week style delta: ratio (cur/prev - 1) or null when prev is 0/missing. */
export const delta = (cur: number | null | undefined, prev: number | null | undefined): number | null => {
  if (cur === null || cur === undefined || prev === null || prev === undefined) return null
  if (!prev) return null
  return cur / prev - 1
}

export const CHANNEL_LABELS: Record<string, string> = {
  google: 'Google Ads',
  meta: 'Meta Ads',
  amazon: 'Amazon Ads',
  all: 'All channels',
}
export const channelLabel = (c: string) => CHANNEL_LABELS[c] ?? c.charAt(0).toUpperCase() + c.slice(1)

/** Chart series palette (dark). ≤5 series; order = stable channel order. */
export const SERIES = ['#FDAB43', '#5591C7', '#6DAA45', '#A86FDF', '#DD6974']
const FIXED: Record<string, string> = { google: '#5591C7', meta: '#A86FDF', amazon: '#FDAB43', all: '#FDAB43' }
export function seriesColor(channel: string, index = 0): string {
  return FIXED[channel] ?? SERIES[index % SERIES.length]
}

export const isoDaysAgo = (days: number, from = new Date()) => {
  const d = new Date(from)
  d.setUTCDate(d.getUTCDate() - days)
  return d.toISOString().slice(0, 10)
}
export const todayIso = () => new Date().toISOString().slice(0, 10)

export const daysBetween = (start: string, end: string) =>
  Math.round((Date.parse(end) - Date.parse(start)) / 86_400_000) + 1

/** Previous window of the same length, ending the day before `start`. */
export const previousRange = (r: { start: string; end: string }) => {
  const len = daysBetween(r.start, r.end)
  const end = isoDaysAgo(1, new Date(r.start))
  const start = isoDaysAgo(len - 1, new Date(end))
  return { start, end }
}

export const shortDate = (iso: string) => {
  const d = new Date(iso + (iso.length === 10 ? 'T00:00:00Z' : ''))
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
}
export const longDate = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export const relTime = (ms: number) => {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s}s ago`
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 48) return `${h}h ago`
  return `${Math.round(h / 24)}d ago`
}

export const titleCase = (s: string) => s.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export const slugify = (s: string) =>
  s
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
