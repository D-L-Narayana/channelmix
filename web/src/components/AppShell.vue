<script setup lang="ts">
/**
 * The application shell for /w/:slug/*. Also rendered (read-only) inside the landing page
 * as the "live product preview" so the product page shows the real UI, not a mockup.
 */
import { computed, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useWorkspaceStore } from '../stores/workspace'
import { useLiveStore } from '../stores/live'
import Wordmark from './Wordmark.vue'
import LiveIndicator from './LiveIndicator.vue'
import KeyGate from './KeyGate.vue'
import Skeleton from './ui/Skeleton.vue'
import FreshKeyDialog from './FreshKeyDialog.vue'

const props = defineProps<{ slug: string }>()
const ws = useWorkspaceStore()
const live = useLiveStore()
const route = useRoute()

const nav = computed(() => [
  { to: `/w/${props.slug}`, label: 'Dashboard', name: 'dashboard', exact: true },
  { to: `/w/${props.slug}/import`, label: 'Import', name: 'import' },
  { to: `/w/${props.slug}/settings`, label: 'Settings', name: 'settings' },
])
const isActive = (n: { name: string }) => route.name === n.name || (n.name === 'dashboard' && route.name === 'campaign')

watch(
  () => [ws.ready, ws.key] as const,
  ([ready, key]) => {
    if (ready && key) live.connect(key)
    else live.disconnect()
  },
  { immediate: true },
)
// workspace stats (campaign counts etc.) change with imports
const offLive = live.on(['import.completed', 'campaign.changed'], () => void ws.refresh())
onBeforeUnmount(() => {
  offLive()
  live.disconnect()
})
</script>

<template>
  <div class="shell">
    <header class="top" role="banner">
      <div class="inner">
        <div class="left">
          <Wordmark size="sm" />
          <span class="sep" aria-hidden="true">/</span>
          <span v-if="ws.workspace" class="wsname truncate" :title="ws.workspace.name">{{ ws.workspace.name }}</span>
          <Skeleton v-else-if="ws.state === 'loading'" width="120px" height="14px" inline />
          <span v-else class="wsname mono muted">{{ slug }}</span>
        </div>
        <nav class="nav" aria-label="Workspace">
          <router-link v-for="n in nav" :key="n.name" :to="n.to" class="navlink" :class="{ active: isActive(n) }" :aria-current="isActive(n) ? 'page' : undefined">
            {{ n.label }}
          </router-link>
        </nav>
        <div class="right">
          <LiveIndicator v-if="ws.ready" />
        </div>
      </div>
    </header>

    <main id="main" class="main" tabindex="-1">
      <template v-if="ws.state === 'ready'">
        <router-view v-slot="{ Component }">
          <component :is="Component" :key="route.path" />
        </router-view>
      </template>
      <div v-else-if="ws.state === 'loading' || ws.state === 'idle'" class="page loading" aria-busy="true" aria-label="Loading workspace">
        <div class="row" style="justify-content: space-between">
          <Skeleton width="220px" height="26px" />
          <Skeleton width="280px" height="36px" radius="10px" />
        </div>
        <div class="skgrid">
          <Skeleton v-for="i in 6" :key="i" height="96px" radius="14px" />
        </div>
        <div class="skgrid2">
          <Skeleton height="320px" radius="14px" />
          <Skeleton height="320px" radius="14px" />
        </div>
      </div>
      <KeyGate v-else :slug="slug" />
    </main>

    <FreshKeyDialog />
  </div>
</template>

<style scoped>
.shell { min-height: 100dvh; display: flex; flex-direction: column; }
.top { position: sticky; top: 0; z-index: 20; background: rgba(23, 22, 20, 0.92); backdrop-filter: saturate(140%) blur(6px); border-bottom: 1px solid var(--border); }
.inner { height: var(--header-h); max-width: var(--content-max); margin: 0 auto; padding: 0 24px; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 16px; }
.left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.sep { color: var(--faint); }
.wsname { font-size: var(--fs-14); color: var(--text-strong); font-weight: 500; max-width: 240px; }
.nav { display: flex; gap: 2px; justify-self: center; }
.navlink { position: relative; height: var(--header-h); display: inline-flex; align-items: center; padding: 0 12px; font-size: var(--fs-14); color: var(--muted); border-radius: 0; }
.navlink:hover { color: var(--text-strong); }
.navlink.active { color: var(--text-strong); }
.navlink.active::after { content: ''; position: absolute; left: 12px; right: 12px; bottom: -1px; height: 2px; background: var(--accent); border-radius: 2px 2px 0 0; }
.navlink:focus-visible { box-shadow: inset var(--ring); }
.right { display: flex; justify-content: flex-end; align-items: center; gap: 10px; }
.main { flex: 1; width: 100%; max-width: var(--content-max); margin: 0 auto; padding: 24px 24px 64px; outline: none; }
.page.loading { display: flex; flex-direction: column; gap: 20px; }
.skgrid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
.skgrid2 { display: grid; grid-template-columns: 3fr 2fr; gap: 16px; }
@media (max-width: 900px) {
  .inner { grid-template-columns: 1fr auto; grid-template-rows: auto; height: auto; padding: 0 16px; row-gap: 0; }
  .left { height: 48px; }
  .right { height: 48px; }
  .nav { grid-column: 1 / -1; justify-self: stretch; height: 40px; overflow-x: auto; }
  .navlink { height: 40px; padding: 0 10px; }
  .main { padding: 16px 16px 48px; }
  .skgrid { grid-template-columns: repeat(2, 1fr); }
  .skgrid2 { grid-template-columns: 1fr; }
}
</style>
