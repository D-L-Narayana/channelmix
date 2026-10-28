import { api, ApiError, API_URL, curlSnippet, request, setUnauthorizedHandler } from '../lib/api'

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

describe('api client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    setUnauthorizedHandler(null)
  })

  it('sends the X-Api-Key header and JSON bodies to /api/v1', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ ok: true }))
    await request('/campaigns', { key: 'cmx_abc', method: 'POST', body: { a: 1 } })
    const [url, init] = spy.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(`${API_URL}/api/v1/campaigns`)
    expect((init.headers as Headers).get('X-Api-Key')).toBe('cmx_abc')
    expect((init.headers as Headers).get('Content-Type')).toBe('application/json')
    expect(init.body).toBe('{"a":1}')
  })

  it('maps 401 to an unauthorized ApiError and notifies the handler', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ detail: 'missing or invalid API key' }, 401))
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    const err = await api.me('bad').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.kind).toBe('unauthorized')
    expect(err.isAuth).toBe(true)
    expect(err.message).toBe('missing or invalid API key')
    expect(handler).toHaveBeenCalledOnce()
  })

  it('maps 404 and 422 (FastAPI validation list) to readable errors', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse({ detail: 'campaign not found' }, 404))
    await expect(api.campaign('k', 9)).rejects.toMatchObject({ kind: 'not_found', message: 'campaign not found' })
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse({ detail: [{ loc: ['body', 'email'], msg: 'value is not a valid email address', type: 'value_error' }] }, 422))
    await expect(api.createWorkspace({ name: 'x', email: 'nope' })).rejects.toMatchObject({ kind: 'validation', message: 'email: value is not a valid email address' })
  })

  it('turns a network failure into an unreachable error (no mock fallback)', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    const err = await api.summary('k', { start: '2025-01-01', end: '2025-01-07' }).catch((e) => e)
    expect(err.kind).toBe('unreachable')
    expect(err.message).toContain(API_URL)
  })

  it('builds multipart dry-run imports and the SSE url', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ status: 'dry_run' }))
    const file = new File(['day,campaign,spend\n'], 'x.csv', { type: 'text/csv' })
    await api.importCsv('k', file, { dryRun: true, channel: 'meta' })
    const init = spy.mock.calls[0][1] as RequestInit
    const fd = init.body as FormData
    expect(fd.get('dry_run')).toBe('true')
    expect(fd.get('channel')).toBe('meta')
    expect((fd.get('file') as File).name).toBe('x.csv')
    expect((init.headers as Headers).has('Content-Type')).toBe(false)
    expect(api.streamUrl('cmx_1', '42')).toBe(`${API_URL}/api/v1/stream?api_key=cmx_1&last_event_id=42`)
  })

  it('curl snippet uses the real key and the bulk endpoint', () => {
    const s = curlSnippet('cmx_realkey')
    expect(s).toContain('X-Api-Key: cmx_realkey')
    expect(s).toContain('/api/v1/metrics/bulk')
  })
})
