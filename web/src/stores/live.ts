/**
 * Live updates (api/CONTRACT.md § Events / SSE).
 * Primary: EventSource on GET /api/v1/stream?api_key=... — the server closes the
 * stream every ~25 s on Vercel and EventSource reconnects with Last-Event-ID, so
 * nothing is lost. Fallback: poll GET /events?after=<id> every 10 s (ETag-aware
 * server side) when EventSource is unsupported or keeps failing.
 * Consumers subscribe to event types and refetch their own queries.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../lib/api'
import type { LiveEvent, LiveEventType, StoredEvent } from '../lib/types'

export type LiveMode = 'off' | 'connecting' | 'sse' | 'polling' | 'error'
export type Listener = (e: LiveEvent) => void

export const SERVER_EVENTS: LiveEventType[] = ['ready', 'metrics.upserted', 'campaign.changed', 'import.completed']
/** Which server events invalidate which views. */
export const DATA_EVENTS: LiveEventType[] = ['metrics.upserted', 'campaign.changed', 'import.completed']
const POLL_MS = 10_000
const MAX_SSE_FAILURES = 3
const SSE_RETRY_MS = 60_000

export const useLiveStore = defineStore('live', () => {
  const mode = ref<LiveMode>('off')
  const lastEventAt = ref<number | null>(null) // last data event or successful heartbeat/poll
  const lastEventId = ref<string | null>(null)
  const lastType = ref<LiveEventType | null>(null)
  const now = ref(Date.now())
  const failures = ref(0)

  let es: EventSource | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let sseRetryTimer: ReturnType<typeof setTimeout> | null = null
  let clock: ReturnType<typeof setInterval> | null = null
  let currentKey: string | null = null
  const listeners = new Set<{ types: LiveEventType[] | null; fn: Listener }>()

  const secondsAgo = computed(() => (lastEventAt.value ? Math.max(0, Math.round((now.value - lastEventAt.value) / 1000)) : null))
  const isLive = computed(() => mode.value === 'sse' || mode.value === 'polling')

  function emit(e: LiveEvent) {
    lastEventAt.value = e.at
    if (e.id) lastEventId.value = e.id
    if (e.type !== 'ready') lastType.value = e.type
    for (const l of listeners) if (!l.types || l.types.includes(e.type) || l.types.includes('*')) l.fn(e)
  }

  /** Subscribe; returns an unsubscribe fn. `types=null` means every event. */
  function on(types: LiveEventType[] | null, fn: Listener) {
    const entry = { types, fn }
    listeners.add(entry)
    return () => listeners.delete(entry)
  }

  function startClock() {
    if (clock) return
    clock = setInterval(() => (now.value = Date.now()), 1000)
  }

  /* ---------- polling fallback ---------- */
  async function pollOnce() {
    if (!currentKey) return
    try {
      if (lastEventId.value === null) {
        // first poll: learn the latest id without replaying history
        const latest = await api.events(currentKey, null, 1)
        lastEventId.value = latest[0] ? String(latest[0].id) : '0'
        lastEventAt.value = Date.now()
        return
      }
      const evs: StoredEvent[] = await api.events(currentKey, lastEventId.value, 100)
      lastEventAt.value = Date.now()
      for (const ev of evs) emit({ id: String(ev.id), type: ev.type, data: { ...ev } as Record<string, unknown>, at: Date.now() })
    } catch {
      // /events unavailable -> blind refresh tick so views still update
      emit({ id: null, type: 'metrics.upserted', data: { source: 'poll' }, at: Date.now() })
    }
  }
  function startPolling() {
    stopPolling()
    mode.value = 'polling'
    void pollOnce()
    pollTimer = setInterval(() => void pollOnce(), POLL_MS)
  }
  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = null
  }

  /* ---------- SSE ---------- */
  function closeSse() {
    if (es) {
      es.onopen = null
      es.onerror = null
      es.onmessage = null
      es.close()
    }
    es = null
  }

  function connectSse(key: string) {
    closeSse()
    mode.value = 'connecting'
    const source = new EventSource(api.streamUrl(key, lastEventId.value))
    es = source
    source.onopen = () => {
      failures.value = 0
      mode.value = 'sse'
      stopPolling()
      lastEventAt.value = Date.now()
    }
    const handle = (type: LiveEventType) => (ev: MessageEvent) => {
      let data: Record<string, unknown> = {}
      try {
        data = ev.data ? JSON.parse(ev.data) : {}
      } catch {
        data = { raw: ev.data }
      }
      const t = (type === 'message' && typeof data.type === 'string' ? data.type : type) as LiveEventType
      emit({ id: ev.lastEventId || (data.id != null ? String(data.id) : null), type: t, data, at: Date.now() })
    }
    for (const t of SERVER_EVENTS) source.addEventListener(t, handle(t) as EventListener)
    source.onmessage = handle('message')
    source.onerror = () => {
      // Fires on the planned ~25 s close too; EventSource then reconnects itself with
      // Last-Event-ID and `onopen` resets the counter. Only *consecutive* failures
      // without an open in between count, after which we switch to polling.
      failures.value += 1
      if (failures.value >= MAX_SSE_FAILURES) {
        closeSse()
        startPolling()
        if (sseRetryTimer) clearTimeout(sseRetryTimer)
        sseRetryTimer = setTimeout(() => {
          failures.value = 0
          if (currentKey) connectSse(currentKey)
        }, SSE_RETRY_MS)
      } else if (mode.value !== 'polling') {
        mode.value = 'connecting'
      }
    }
  }

  function connect(key: string) {
    if (currentKey === key && mode.value !== 'off' && mode.value !== 'error') return
    disconnect()
    currentKey = key
    startClock()
    if (typeof EventSource === 'undefined') {
      startPolling()
      return
    }
    connectSse(key)
  }

  function disconnect() {
    closeSse()
    stopPolling()
    if (sseRetryTimer) clearTimeout(sseRetryTimer)
    sseRetryTimer = null
    currentKey = null
    mode.value = 'off'
    failures.value = 0
  }

  /** Local actions (import commit etc.) call this so dependent views refresh even if the stream lags. */
  function touch(type: LiveEventType = 'metrics.upserted', data: Record<string, unknown> = {}) {
    emit({ id: null, type, data: { ...data, source: 'local' }, at: Date.now() })
  }

  return { mode, lastEventAt, lastEventId, lastType, secondsAgo, isLive, failures, connect, disconnect, on, touch }
})
