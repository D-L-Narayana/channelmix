export const money = (n: number | null | undefined, digits = 0) =>
  n === null || n === undefined
    ? '–'
    : n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: digits, minimumFractionDigits: digits })

export const num = (n: number | null | undefined, digits = 0) =>
  n === null || n === undefined ? '–' : n.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits })

export const pct = (n: number | null | undefined, digits = 1, signed = false) =>
  n === null || n === undefined ? '–' : `${signed && n > 0 ? '+' : ''}${(n * 100).toFixed(digits)}%`

export const roas = (n: number | null | undefined) => (n === null || n === undefined ? '–' : `${n.toFixed(2)}x`)

export const CHANNEL_COLORS: Record<string, string> = {
  google: '#4285F4',
  meta: '#A855F7',
  amazon: '#F59E0B',
  all: '#0ea5e9',
}

export const CHANNEL_LABELS: Record<string, string> = {
  google: 'Google Ads',
  meta: 'Meta Ads',
  amazon: 'Amazon Ads',
  all: 'All channels',
}

export const isoDaysAgo = (days: number, from = new Date()) => {
  const d = new Date(from)
  d.setUTCDate(d.getUTCDate() - days)
  return d.toISOString().slice(0, 10)
}
