<script setup lang="ts">
import { computed } from 'vue'
import { useLiveStore } from '../stores/live'

const live = useLiveStore()
const label = computed(() => {
  switch (live.mode) {
    case 'sse':
      return 'Live'
    case 'polling':
      return 'Polling'
    case 'connecting':
      return 'Connecting'
    case 'error':
      return 'Offline'
    default:
      return 'Paused'
  }
})
const ago = computed(() => {
  const s = live.secondsAgo
  if (s === null) return null
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  return `${Math.floor(m / 60)}h ago`
})
const title = computed(() =>
  live.mode === 'sse'
    ? 'Connected to the event stream (SSE). Views refresh when data changes.'
    : live.mode === 'polling'
      ? 'Event stream unavailable — checking for new events every 10 s.'
      : live.mode === 'connecting'
        ? 'Connecting to the event stream…'
        : 'Not connected.',
)
</script>

<template>
  <span class="live" :class="live.mode" :title="title" role="status" aria-live="off">
    <i class="dot" aria-hidden="true" />
    <span class="txt">{{ label }}<template v-if="ago"><span class="sep" aria-hidden="true"> · </span><span class="ago num">updated {{ ago }}</span></template></span>
  </span>
</template>

<style scoped>
.live { display: inline-flex; align-items: center; gap: 7px; font-size: var(--fs-12); color: var(--muted); white-space: nowrap; height: 24px; padding: 0 8px; border-radius: var(--r-pill); border: 1px solid var(--border); background: var(--surface-2); }
.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--faint); flex-shrink: 0; }
.sse .dot { background: var(--success); box-shadow: 0 0 0 3px var(--success-soft); }
.polling .dot { background: var(--info); box-shadow: 0 0 0 3px var(--info-soft); }
.connecting .dot { background: var(--warning-text); animation: pulse 1.6s ease-in-out infinite; }
.error .dot { background: var(--error); }
.sse .txt, .polling .txt { color: var(--text); }
.ago { color: var(--muted); font-variant-numeric: tabular-nums; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
@media (prefers-reduced-motion: reduce) { .connecting .dot { animation: none; } }
@media (max-width: 640px) { .ago, .sep { display: none; } }
</style>
