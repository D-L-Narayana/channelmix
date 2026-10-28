import { api } from '../lib/api'
import { ApiError } from '../lib/api'
import { storedKey, useWorkspaceStore } from '../stores/workspace'

const me = { id: 1, slug: 'acme-k3f9', name: 'Acme', email: 'a@b.co', created_at: '2025-01-01T00:00:00Z', stats: { campaigns: 0, metric_rows: 0, imports: 0, first_day: null, last_day: null } }

describe('workspace store', () => {
  afterEach(() => vi.restoreAllMocks())

  it('is in no-key state when nothing is stored', async () => {
    const ws = useWorkspaceStore()
    await ws.open('acme-k3f9')
    expect(ws.state).toBe('no-key')
    expect(ws.ready).toBe(false)
  })

  it('stores the magic-link key and loads the workspace', async () => {
    vi.spyOn(api, 'me').mockResolvedValue(me)
    const ws = useWorkspaceStore()
    await ws.open('acme-k3f9', 'cmx_fromurl')
    expect(storedKey('acme-k3f9')).toBe('cmx_fromurl')
    expect(ws.state).toBe('ready')
    expect(ws.workspace?.name).toBe('Acme')
  })

  it('flags a rejected key as invalid and forgets a pasted bad key', async () => {
    vi.spyOn(api, 'me').mockRejectedValue(new ApiError('unauthorized', 401, 'missing or invalid API key'))
    const ws = useWorkspaceStore()
    await ws.useKey('acme-k3f9', 'cmx_bad')
    expect(ws.state).toBe('invalid')
    expect(storedKey('acme-k3f9')).toBeNull()
  })

  it('rejects a key that belongs to another workspace (cross-tenant)', async () => {
    vi.spyOn(api, 'me').mockResolvedValue({ ...me, slug: 'other-1111' })
    const ws = useWorkspaceStore()
    await ws.open('acme-k3f9', 'cmx_other')
    expect(ws.state).toBe('invalid')
  })

  it('reports unreachable API distinctly from invalid key', async () => {
    vi.spyOn(api, 'me').mockRejectedValue(new ApiError('unreachable', 0, 'Cannot reach the API'))
    const ws = useWorkspaceStore()
    await ws.open('acme-k3f9', 'cmx_x')
    expect(ws.state).toBe('unreachable')
  })

  it('create() stores the key, exposes it once and marks the store ready', async () => {
    vi.spyOn(api, 'createWorkspace').mockResolvedValue({ ...me, api_key: 'cmx_new' })
    const ws = useWorkspaceStore()
    await ws.create('Acme', 'a@b.co')
    expect(ws.freshKey).toBe('cmx_new')
    expect(ws.key).toBe('cmx_new')
    expect(ws.ready).toBe(true)
    ws.dismissFreshKey()
    expect(ws.freshKey).toBeNull()
    ws.signOut()
    expect(storedKey('acme-k3f9')).toBeNull()
    expect(ws.state).toBe('no-key')
  })
})
