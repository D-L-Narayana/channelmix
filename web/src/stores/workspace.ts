import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, ApiError, setUnauthorizedHandler } from '../lib/api'
import type { Workspace } from '../lib/types'

const KEY_PREFIX = 'channelmix.key.'
const LAST_SLUG = 'channelmix.lastSlug'

export type AuthState = 'idle' | 'loading' | 'ready' | 'no-key' | 'invalid' | 'unreachable'

export function storedKey(slug: string): string | null {
  try {
    return localStorage.getItem(KEY_PREFIX + slug)
  } catch {
    return null
  }
}
export function storeKey(slug: string, key: string) {
  try {
    localStorage.setItem(KEY_PREFIX + slug, key)
    localStorage.setItem(LAST_SLUG, slug)
  } catch {
    /* private mode */
  }
}
export function forgetKey(slug: string) {
  try {
    localStorage.removeItem(KEY_PREFIX + slug)
    if (localStorage.getItem(LAST_SLUG) === slug) localStorage.removeItem(LAST_SLUG)
  } catch {
    /* noop */
  }
}
export function lastSlug(): string | null {
  try {
    return localStorage.getItem(LAST_SLUG)
  } catch {
    return null
  }
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const slug = ref<string | null>(null)
  const key = ref<string | null>(null)
  const workspace = ref<Workspace | null>(null)
  const state = ref<AuthState>('idle')
  const error = ref<string | null>(null)
  /** full key shown exactly once right after creation / rotation */
  const freshKey = ref<string | null>(null)

    const ready = computed(() => state.value === 'ready' && !!key.value)

  setUnauthorizedHandler(() => {
    if (state.value === 'ready' || state.value === 'loading') {
      state.value = 'invalid'
      error.value = 'This workspace key was rejected by the API.'
    }
  })

  /** Called by the router guard for every /w/:slug route. `urlKey` comes from the magic link `?key=`. */
  async function open(nextSlug: string, urlKey?: string | null) {
    if (urlKey) storeKey(nextSlug, urlKey)
    const k = urlKey ?? storedKey(nextSlug)
    const slugChanged = slug.value !== nextSlug
    slug.value = nextSlug
    if (!k) {
      key.value = null
      workspace.value = null
      state.value = 'no-key'
      return
    }
    if (!slugChanged && key.value === k && state.value === 'ready') return
    key.value = k
    state.value = 'loading'
    error.value = null
    try {
      const ws = await api.me(k)
      if (ws.slug && ws.slug !== nextSlug) {
        // key belongs to a different workspace -> treat as cross-tenant miss
        workspace.value = null
        state.value = 'invalid'
        error.value = 'This key belongs to a different workspace.'
        return
      }
      workspace.value = ws
      state.value = 'ready'
      try {
        localStorage.setItem(LAST_SLUG, nextSlug)
      } catch {
        /* noop */
      }
    } catch (e) {
      workspace.value = null
      if (e instanceof ApiError && (e.isAuth || e.kind === 'not_found')) {
        state.value = 'invalid'
        error.value = e.message
      } else if (e instanceof ApiError && e.kind === 'unreachable') {
        state.value = 'unreachable'
        error.value = e.message
      } else {
        state.value = 'unreachable'
        error.value = (e as Error).message
      }
    }
  }

  async function retry() {
    if (!slug.value) return
    const k = key.value ?? storedKey(slug.value)
    key.value = null
    await open(slug.value, k)
  }

  /** User pasted a key for an existing workspace. */
  async function useKey(nextSlug: string, pasted: string) {
    const k = pasted.trim()
    if (!k) return
    key.value = null
    await open(nextSlug, k)
    if (state.value !== 'ready') forgetKey(nextSlug)
  }

  async function create(name: string, email: string) {
    const created = await api.createWorkspace({ name, email })
    storeKey(created.slug, created.api_key)
    freshKey.value = created.api_key
    slug.value = created.slug
    key.value = created.api_key
    workspace.value = created
    state.value = 'ready'
    return created
  }

  async function rotate() {
    if (!key.value || !slug.value) throw new Error('No workspace open')
    const r = await api.rotateKey(key.value)
    storeKey(slug.value, r.api_key)
    key.value = r.api_key
    freshKey.value = r.api_key
    return r.api_key
  }

  async function refresh() {
    if (!key.value) return
    try {
      workspace.value = await api.me(key.value)
    } catch {
      /* handled by unauthorized handler or next load */
    }
  }

  function signOut() {
    if (slug.value) forgetKey(slug.value)
    key.value = null
    workspace.value = null
    state.value = 'no-key'
  }

  async function destroy() {
    if (!key.value) return
    await api.deleteWorkspace(key.value)
    signOut()
  }

  function dismissFreshKey() {
    freshKey.value = null
  }

  return {
    slug,
    key,
    workspace,
    state,
    error,
    freshKey,
    ready,
    open,
    retry,
    useKey,
    create,
    rotate,
    refresh,
    signOut,
    destroy,
    dismissFreshKey,
  }
})
