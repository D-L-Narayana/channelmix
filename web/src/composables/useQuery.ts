import { onScopeDispose, ref, shallowRef, watch, type Ref, type WatchSource } from 'vue'
import { ApiError } from '../lib/api'
import { useLiveStore } from '../stores/live'
import type { LiveEventType } from '../lib/types'

export interface QueryOptions<T> {
  /** Reactive dependencies; the query re-runs when they change. */
  deps?: WatchSource[]
  /** Live event types that should trigger a silent refetch. */
  refetchOn?: LiveEventType[]
  enabled?: Ref<boolean> | (() => boolean)
  initial?: T | null
  immediate?: boolean
}

export interface QueryState<T> {
  data: Ref<T | null>
  error: Ref<ApiError | null>
  loading: Ref<boolean> // first load (skeletons)
  refreshing: Ref<boolean> // background refetch (no layout change)
  updatedAt: Ref<number | null>
  run: () => Promise<void>
  refetch: () => Promise<void>
  reset: () => void
}

/**
 * Tiny fetch-state primitive: skeleton on first load, silent refresh afterwards,
 * cancels stale responses, and refetches on live events. No cache layer — the API
 * already caches reports server-side.
 */
export function useQuery<T>(fetcher: (signal: AbortSignal) => Promise<T>, opts: QueryOptions<T> = {}): QueryState<T> {
  const data = shallowRef<T | null>(opts.initial ?? null) as Ref<T | null>
  const error = ref<ApiError | null>(null)
  const loading = ref(false)
  const refreshing = ref(false)
  const updatedAt = ref<number | null>(null)
  let ctrl: AbortController | null = null
  let seq = 0

  const enabled = () => {
    const e = opts.enabled
    if (!e) return true
    return typeof e === 'function' ? e() : e.value
  }

  async function exec(silent: boolean) {
    if (!enabled()) return
    ctrl?.abort()
    ctrl = new AbortController()
    const my = ++seq
    if (silent && data.value !== null) refreshing.value = true
    else loading.value = true
    try {
      const result = await fetcher(ctrl.signal)
      if (my !== seq) return
      data.value = result
      error.value = null
      updatedAt.value = Date.now()
    } catch (e) {
      if (my !== seq) return
      if (e instanceof ApiError && e.kind === 'aborted') return
      error.value = e instanceof ApiError ? e : new ApiError('server', 0, (e as Error).message ?? 'Unknown error', e)
    } finally {
      if (my === seq) {
        loading.value = false
        refreshing.value = false
      }
    }
  }

  const run = () => exec(false)
  const refetch = () => exec(true)
  const reset = () => {
    ctrl?.abort()
    data.value = opts.initial ?? null
    error.value = null
    loading.value = false
    refreshing.value = false
  }

  if (opts.deps?.length) watch(opts.deps, () => exec(false), { deep: true })
  if (opts.immediate !== false) exec(false)

  if (opts.refetchOn?.length) {
    const live = useLiveStore()
    const off = live.on(opts.refetchOn, () => exec(true))
    onScopeDispose(off)
  }
  onScopeDispose(() => ctrl?.abort())

  return { data, error, loading, refreshing, updatedAt, run, refetch, reset }
}
