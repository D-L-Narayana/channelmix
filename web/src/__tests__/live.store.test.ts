import { api } from '../lib/api'
import { useLiveStore } from '../stores/live'

describe('live store', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('falls back to polling /events when EventSource is unsupported', async () => {
    vi.useFakeTimers()
    const original = (globalThis as { EventSource?: unknown }).EventSource
    ;(globalThis as { EventSource?: unknown }).EventSource = undefined
    const events = vi.spyOn(api, 'events').mockResolvedValueOnce([{ id: 10, type: 'metrics.upserted', created_at: '', payload: {} }]).mockResolvedValueOnce([{ id: 11, type: 'import.completed', created_at: '', payload: { import_id: 3 } }])
    const live = useLiveStore()
    const seen: string[] = []
    live.on(['import.completed'], (e) => seen.push(e.type))
    live.connect('cmx_k')
    expect(live.mode).toBe('polling')
    await vi.advanceTimersByTimeAsync(10)
    expect(live.lastEventId).toBe('10') // learned latest id without replaying
    await vi.advanceTimersByTimeAsync(10_000)
    expect(events).toHaveBeenLastCalledWith('cmx_k', '10', 100)
    expect(seen).toEqual(['import.completed'])
    expect(live.lastEventId).toBe('11')
    live.disconnect()
    expect(live.mode).toBe('off')
    ;(globalThis as { EventSource?: unknown }).EventSource = original
  })

  it('touch() notifies only matching listeners and updates the timestamp', () => {
    const live = useLiveStore()
    const a = vi.fn()
    const b = vi.fn()
    const offA = live.on(['metrics.upserted'], a)
    live.on(['campaign.changed'], b)
    live.touch('metrics.upserted', { rows: 3 })
    expect(a).toHaveBeenCalledOnce()
    expect(b).not.toHaveBeenCalled()
    expect(live.lastEventAt).not.toBeNull()
    offA()
    live.touch('metrics.upserted')
    expect(a).toHaveBeenCalledOnce()
  })
})
