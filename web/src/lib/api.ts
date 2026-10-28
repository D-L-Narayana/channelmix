/**
 * API client. Talks to VITE_API_URL; if the API is unreachable (or the env var is
 * unset) every call transparently falls back to the bundled mock dataset so the
 * hosted demo works standalone. `source` tells the UI which mode is active.
 */
import { ref } from 'vue'
import accountsMock from '../mock/accounts.json'
import campaignsMock from '../mock/campaigns.json'
import channelMixMock from '../mock/channel_mix.json'
import trendMock from '../mock/trend.json'
import trendTotalMock from '../mock/trend_total.json'
import campaignReportMock from '../mock/campaign_report.json'
import recommendationMock from '../mock/recommendation.json'
import { reallocate } from './recommender'
import type {
  Account,
  Campaign,
  CampaignPerformanceRow,
  Channel,
  ChannelMixReport,
  DateRange,
  RecommendationRequest,
  RecommendationResponse,
  TrendReport,
} from './types'

export const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''
export const source = ref<'api' | 'mock' | 'probing'>(API_URL ? 'probing' : 'mock')
export const lastCache = ref<string | null>(null)

let apiAvailable: boolean | null = API_URL ? null : false

async function probe(): Promise<boolean> {
  if (apiAvailable !== null) return apiAvailable
  try {
    const ctrl = new AbortController()
    const t = setTimeout(() => ctrl.abort(), 2500)
    const r = await fetch(`${API_URL}/health`, { signal: ctrl.signal })
    clearTimeout(t)
    apiAvailable = r.ok
  } catch {
    apiAvailable = false
  }
  source.value = apiAvailable ? 'api' : 'mock'
  return apiAvailable
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${await r.text()}`)
  lastCache.value = r.headers.get('X-Cache')
  return (await r.json()) as T
}

async function withFallback<T>(live: () => Promise<T>, mock: () => T): Promise<T> {
  if (!(await probe())) return mock()
  try {
    return await live()
  } catch (e) {
    console.warn('[channelmix] API call failed, using mock data', e)
    apiAvailable = false
    source.value = 'mock'
    return mock()
  }
}

const qs = (params: Record<string, string | number | undefined | null>) => {
  const u = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') u.set(k, String(v))
  const s = u.toString()
  return s ? `?${s}` : ''
}

const inRange = (day: string, range: DateRange) => day >= range.start && day <= range.end

// ---- mock helpers: make the date filter meaningful offline ---------------------
function mockChannelMix(range: DateRange): ChannelMixReport {
  const base = channelMixMock as ChannelMixReport
  const pts = (trendMock as TrendReport).points.filter((p) => inRange(p.day, range))
  const agg: Record<string, { spend: number; revenue: number; conversions: number }> = {}
  for (const p of pts) {
    agg[p.channel] ??= { spend: 0, revenue: 0, conversions: 0 }
    agg[p.channel].spend += p.spend
    agg[p.channel].revenue += p.revenue
    agg[p.channel].conversions += p.conversions
  }
  const totalSpend = Object.values(agg).reduce((a, b) => a + b.spend, 0)
  const totalRevenue = Object.values(agg).reduce((a, b) => a + b.revenue, 0)
  const channels = base.channels
    .filter((c) => agg[c.channel])
    .map((c) => {
      const a = agg[c.channel]
      const ratio = c.spend ? a.spend / c.spend : 0
      const impressions = Math.round(c.impressions * ratio)
      const clicks = Math.round(c.clicks * ratio)
      return {
        ...c,
        spend: a.spend,
        revenue: a.revenue,
        conversions: a.conversions,
        impressions,
        clicks,
        spend_share: totalSpend ? a.spend / totalSpend : 0,
        revenue_share: totalRevenue ? a.revenue / totalRevenue : 0,
        roas: a.spend ? a.revenue / a.spend : null,
        cpa: a.conversions ? a.spend / a.conversions : null,
        ctr: impressions ? clicks / impressions : null,
        cpc: clicks ? a.spend / clicks : null,
      }
    })
    .sort((x, y) => y.spend - x.spend)
  const ranked = [...channels].sort((x, y) => (y.roas ?? 0) - (x.roas ?? 0))
  for (const c of channels) c.roas_rank = ranked.indexOf(c) + 1
  return {
    ...base,
    start: range.start,
    end: range.end,
    total_spend: totalSpend,
    total_revenue: totalRevenue,
    blended_roas: totalSpend ? totalRevenue / totalSpend : null,
    channels,
  }
}

function mockTrend(range: DateRange, groupBy: 'channel' | 'total'): TrendReport {
  const base = (groupBy === 'total' ? trendTotalMock : trendMock) as TrendReport
  return { ...base, start: range.start, end: range.end, points: base.points.filter((p) => inRange(p.day, range)) }
}

function mockCampaigns(range: DateRange, channel?: Channel | null): CampaignPerformanceRow[] {
  // scale the 90-day campaign totals by the share of in-range days so the drill-down reacts to the filter
  const all = (trendMock as TrendReport).points
  const byChannel: Record<string, number> = {}
  for (const ch of ['google', 'meta', 'amazon']) {
    const total = all.filter((p) => p.channel === ch).reduce((a, p) => a + p.spend, 0)
    const sel = all.filter((p) => p.channel === ch && inRange(p.day, range)).reduce((a, p) => a + p.spend, 0)
    byChannel[ch] = total ? sel / total : 0
  }
  return (campaignReportMock as CampaignPerformanceRow[])
    .filter((r) => !channel || r.channel === channel)
    .map((r) => {
      const k = byChannel[r.channel] ?? 1
      return {
        ...r,
        spend: r.spend * k,
        revenue: r.revenue * k,
        impressions: Math.round(r.impressions * k),
        clicks: Math.round(r.clicks * k),
        conversions: Math.round(r.conversions * k),
      }
    })
    .filter((r) => r.spend > 0)
}

// ---- public API ------------------------------------------------------------------
export const api = {
  probe,
  accounts: () => withFallback(() => request<Account[]>('/accounts'), () => accountsMock as Account[]),

  campaigns: (accountId: number) =>
    withFallback(() => request<Campaign[]>(`/accounts/${accountId}/campaigns`), () => campaignsMock as Campaign[]),

  channelMix: (accountId: number, range: DateRange) =>
    withFallback(
      () => request<ChannelMixReport>(`/accounts/${accountId}/reports/channel-mix${qs({ ...range })}`),
      () => mockChannelMix(range),
    ),

  trend: (accountId: number, range: DateRange, groupBy: 'channel' | 'total' = 'channel') =>
    withFallback(
      () => request<TrendReport>(`/accounts/${accountId}/reports/trend${qs({ ...range, group_by: groupBy })}`),
      () => mockTrend(range, groupBy),
    ),

  campaignReport: (accountId: number, range: DateRange, channel?: Channel | null) =>
    withFallback(
      () => request<CampaignPerformanceRow[]>(`/accounts/${accountId}/reports/campaigns${qs({ ...range, channel })}`),
      () => mockCampaigns(range, channel),
    ),

  recommend: (accountId: number, body: RecommendationRequest) =>
    withFallback(
      () =>
        request<RecommendationResponse>(`/accounts/${accountId}/recommendations/budget`, {
          method: 'POST',
          body: JSON.stringify(body),
        }),
      () => {
        const base = recommendationMock as RecommendationResponse
        const budget = body.total_budget ?? base.channels.reduce((a, c) => a + c.current_daily_spend, 0)
        return reallocate(base, budget, body.min_share ?? 0.05, body.max_shift_pct ?? null)
      },
    ),
}
