/**
 * ChannelMix API client — implements api/CONTRACT.md v1. No mock fallbacks: every
 * failure surfaces as an ApiError that the UI renders as a designed state
 * (unreachable / key invalid / validation).
 *
 * Base URL: VITE_API_URL. Defaults: production -> https://channelmix-api.vercel.app,
 * dev -> http://localhost:8000. JSON endpoints live under `${API_URL}/api/v1`;
 * `/health` is at the root. The SSE stream is `${API_URL}/api/v1/stream?api_key=`
 * because EventSource cannot set headers.
 */
import type {
  BulkResult,
  Campaign,
  CampaignPerformanceRow,
  Channel,
  ChannelMixReport,
  DailyMetric,
  DateRange,
  ImportFormat,
  ImportRecord,
  ImportResponse,
  MetricRowIn,
  RecommendationRequest,
  RecommendationResponse,
  SampleDatasetInfo,
  StoredEvent,
  SummaryReport,
  TrendReport,
  Workspace,
  WorkspaceCreated,
} from './types'

const envUrl = (import.meta.env.VITE_API_URL as string | undefined)?.trim()
export const API_URL: string = (envUrl && envUrl.length > 0
  ? envUrl
  : import.meta.env.PROD
    ? 'https://channelmix-api.vercel.app'
    : 'http://localhost:8000'
).replace(/\/$/, '')
export const API_PREFIX = '/api/v1'
export const API_BASE = `${API_URL}${API_PREFIX}`
export const KEY_HEADER = 'X-Api-Key'

export type ApiErrorKind = 'unreachable' | 'unauthorized' | 'not_found' | 'validation' | 'conflict' | 'server' | 'aborted'

export class ApiError extends Error {
  kind: ApiErrorKind
  status: number
  detail: unknown
  constructor(kind: ApiErrorKind, status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
    this.detail = detail
  }
  /** true when the workspace key is missing/invalid (401) */
  get isAuth() {
    return this.kind === 'unauthorized'
  }
}

export function describeError(e: unknown): string {
  if (e instanceof ApiError) return e.message
  if (e instanceof Error) return e.message
  return String(e)
}

function kindFor(status: number): ApiErrorKind {
  if (status === 401 || status === 403) return 'unauthorized'
  if (status === 404) return 'not_found'
  if (status === 409) return 'conflict'
  if (status === 400 || status === 413 || status === 415 || status === 422) return 'validation'
  return 'server'
}

function humanize(status: number, detail: unknown): string {
  const d =
    detail && typeof detail === 'object' && 'detail' in (detail as Record<string, unknown>)
      ? (detail as { detail: unknown }).detail
      : detail
  if (typeof d === 'string' && d.trim().length > 0 && d.length < 400) return d
  if (Array.isArray(d) && d[0] && typeof d[0] === 'object' && 'msg' in d[0]) {
    return d
      .map((x: { loc?: unknown[]; msg: string }) => {
        const field = (x.loc ?? []).filter((p) => p !== 'body').slice(-1)[0]
        return `${field ? `${field}: ` : ''}${x.msg}`
      })
      .join('; ')
  }
  switch (status) {
    case 401:
    case 403:
      return 'This workspace key is not valid.'
    case 404:
      return 'Not found.'
    case 405:
      return 'This action is not available on the connected API.'
    case 413:
      return 'File too large.'
    case 429:
      return 'Too many requests — slow down a little.'
    default:
      return status >= 500 ? 'The API hit an internal error.' : `Request failed (${status}).`
  }
}

export const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const u = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') u.set(k, String(v))
  const s = u.toString()
  return s ? `?${s}` : ''
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  key?: string | null
  body?: unknown
  timeoutMs?: number
  raw?: boolean
}

let onUnauthorized: ((e: ApiError) => void) | null = null
/** The workspace store registers a handler so any 401 flips the UI into the 'key invalid' state. */
export function setUnauthorizedHandler(fn: ((e: ApiError) => void) | null) {
  onUnauthorized = fn
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { key, body, timeoutMs = 20_000, raw, headers, ...init } = opts
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  const h = new Headers(headers ?? {})
  if (key) h.set(KEY_HEADER, key)
  let payload: BodyInit | undefined
  if (body instanceof FormData) payload = body
  else if (body !== undefined) {
    h.set('Content-Type', 'application/json')
    payload = JSON.stringify(body)
  }
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const outer = init.signal
  outer?.addEventListener('abort', () => ctrl.abort(), { once: true })
  let r: Response
  try {
    r = await fetch(url, { ...init, headers: h, body: payload, signal: ctrl.signal })
  } catch (e) {
    clearTimeout(timer)
    if (outer?.aborted) throw new ApiError('aborted', 0, 'Request cancelled')
    if ((e as Error).name === 'AbortError') throw new ApiError('unreachable', 0, `The API at ${API_URL} did not answer in time.`, e)
    throw new ApiError('unreachable', 0, `Cannot reach the API at ${API_URL}.`, e)
  }
  clearTimeout(timer)
  if (!r.ok) {
    let detail: unknown = null
    const text = await r.text().catch(() => '')
    try {
      detail = text ? JSON.parse(text) : null
    } catch {
      detail = text
    }
    const err = new ApiError(kindFor(r.status), r.status, humanize(r.status, detail), detail)
    if (err.kind === 'unauthorized' && onUnauthorized) onUnauthorized(err)
    throw err
  }
  if (raw) return r as unknown as T
  if (r.status === 204) return undefined as T
  const ct = r.headers.get('content-type') ?? ''
  if (!ct.includes('json')) return (await r.text()) as unknown as T
  return (await r.json()) as T
}

/* ---------- endpoints (api/CONTRACT.md) ---------- */

export const api = {
  health: (signal?: AbortSignal) =>
    request<{ status: string; version?: string; cache?: string; database?: string }>(`${API_URL}/health`, { timeoutMs: 8000, signal }),

  // workspaces
  createWorkspace: (body: { name: string; email: string }) => request<WorkspaceCreated>('/workspaces', { method: 'POST', body }),
  me: (key: string, signal?: AbortSignal) => request<Workspace>('/workspaces/me', { key, signal }),
  /** Not in CONTRACT v1 — the UI degrades to a clear "not available" message if the API answers 404/405. */
  rotateKey: (key: string) => request<{ api_key: string }>('/workspaces/me/rotate-key', { key, method: 'POST' }),
  deleteWorkspace: (key: string) => request<void>('/workspaces/me', { key, method: 'DELETE' }),

  // campaigns
  campaigns: (key: string, params: { channel?: Channel | null; status?: string | null } = {}, signal?: AbortSignal) =>
    request<Campaign[]>(`/campaigns${qs({ channel: params.channel ?? null, status: params.status ?? null })}`, { key, signal }),
  campaign: (key: string, id: number | string, signal?: AbortSignal) => request<Campaign>(`/campaigns/${id}`, { key, signal }),
  updateCampaign: (key: string, id: number | string, body: Partial<Pick<Campaign, 'name' | 'status' | 'daily_budget'>>) =>
    request<Campaign>(`/campaigns/${id}`, { key, method: 'PATCH', body }),
  deleteCampaign: (key: string, id: number | string) => request<void>(`/campaigns/${id}`, { key, method: 'DELETE' }),

  // metrics
  metrics: (key: string, params: { campaign_id?: number | string; start?: string; end?: string; limit?: number }, signal?: AbortSignal) =>
    request<DailyMetric[]>(`/metrics${qs({ ...params })}`, { key, signal }),
  bulkMetrics: (key: string, rows: MetricRowIn[], idempotencyKey?: string) =>
    request<BulkResult>('/metrics/bulk', { key, method: 'POST', body: { rows }, headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined }),

  // reports
  summary: (key: string, range: DateRange, signal?: AbortSignal) => request<SummaryReport>(`/reports/summary${qs({ ...range })}`, { key, signal }),
  byChannel: (key: string, range: DateRange, signal?: AbortSignal) => request<ChannelMixReport>(`/reports/by-channel${qs({ ...range })}`, { key, signal }),
  trend: (key: string, range: DateRange, groupBy: 'channel' | 'total' = 'channel', signal?: AbortSignal) =>
    request<TrendReport>(`/reports/trend${qs({ ...range, group_by: groupBy })}`, { key, signal }),
  campaignReport: (key: string, range: DateRange, channel?: Channel | null, signal?: AbortSignal) =>
    request<CampaignPerformanceRow[]>(`/reports/campaigns${qs({ ...range, channel: channel ?? null })}`, { key, signal }),
  recommend: (key: string, params: RecommendationRequest & { end?: string }, signal?: AbortSignal) =>
    request<RecommendationResponse>(`/recommendations${qs({ ...params })}`, { key, signal }),

  // CSV import (dry-run first, then commit)
  importCsv: (key: string, file: File, opts: { dryRun: boolean; format?: ImportFormat | null; channel?: Channel | null }, signal?: AbortSignal) => {
    const fd = new FormData()
    fd.append('file', file, file.name)
    fd.append('dry_run', opts.dryRun ? 'true' : 'false')
    if (opts.format) fd.append('format', opts.format)
    if (opts.channel) fd.append('channel', opts.channel)
    return request<ImportResponse>('/imports/csv', { key, method: 'POST', body: fd, timeoutMs: 120_000, signal })
  },
  imports: (key: string, limit = 20, signal?: AbortSignal) => request<ImportRecord[]>(`/imports${qs({ limit })}`, { key, signal }),

  // sample dataset (real public data; never auto-imported)
  sampleInfo: (signal?: AbortSignal) => request<SampleDatasetInfo>('/datasets/sample/info', { signal }),
  importSample: (key: string) => request<ImportResponse>('/datasets/sample/import', { key, method: 'POST', timeoutMs: 120_000 }),

  // live
  streamUrl: (key: string, lastEventId?: string | null) => `${API_BASE}/stream${qs({ api_key: key, last_event_id: lastEventId ?? null })}`,
  events: (key: string, after: string | number | null, limit = 100, signal?: AbortSignal) =>
    request<StoredEvent[]>(`/events${qs({ after, limit })}`, { key, signal }),
}

/** Copy-paste ingest snippet shown in the Import page; uses the visitor's real key. */
export function curlSnippet(key: string): string {
  const day = new Date().toISOString().slice(0, 10)
  return [
    `curl -s -X POST ${API_BASE}/metrics/bulk \\`,
    `  -H "${KEY_HEADER}: ${key}" \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -H "Idempotency-Key: $(uuidgen)" \\`,
    `  -d '{"rows": [`,
    `    {"channel": "google", "external_id": "brand-search", "campaign_name": "Brand search",`,
    `     "day": "${day}", "impressions": 12000, "clicks": 480, "conversions": 22,`,
    `     "spend": 310.5, "revenue": 1420}`,
    `  ]}'`,
  ].join('\n')
}

export function curlPreviewSnippet(key: string): string {
  return [`curl -s -X POST ${API_BASE}/imports/csv \\`, `  -H "${KEY_HEADER}: ${key}" \\`, `  -F file=@export.csv -F dry_run=true`].join('\n')
}

export function curlStreamSnippet(key: string): string {
  return `curl -N "${API_BASE}/stream?api_key=${key}"`
}
