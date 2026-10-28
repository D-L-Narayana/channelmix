<script setup lang="ts">
import { useToastStore } from '../../stores/toast'
import Button from './Button.vue'

const toasts = useToastStore()
</script>

<template>
  <div class="host" aria-live="polite" aria-atomic="false">
    <TransitionGroup name="toast">
      <div v-for="t in toasts.items" :key="t.id" class="toast" :class="t.tone" role="status">
        <i class="bar" aria-hidden="true" />
        <div class="txt">
          <div class="title">{{ t.title }}</div>
          <div v-if="t.body" class="body">{{ t.body }}</div>
        </div>
        <Button v-if="t.action" size="sm" variant="ghost" @click="t.action.onClick(); toasts.dismiss(t.id)">{{ t.action.label }}</Button>
        <button class="x" aria-label="Dismiss notification" @click="toasts.dismiss(t.id)">×</button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.host {
  position: fixed; right: 16px; bottom: 16px; z-index: 60;
  display: flex; flex-direction: column; gap: 8px; max-width: min(380px, calc(100vw - 32px));
}
.toast {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 10px 10px 10px 14px; background: var(--surface-2); border: 1px solid var(--border);
  border-radius: var(--r-md); box-shadow: var(--shadow-2); position: relative; overflow: hidden;
}
.bar { position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--border-strong); }
.success .bar { background: var(--success); }
.error .bar { background: var(--error); }
.warning .bar { background: var(--warning-text); }
.txt { flex: 1; min-width: 0; }
.title { font-weight: 500; color: var(--text-strong); font-size: var(--fs-14); }
.body { color: var(--muted); font-size: var(--fs-13); margin-top: 2px; overflow-wrap: anywhere; }
.x { background: none; border: 0; color: var(--muted); font-size: 18px; line-height: 1; padding: 2px 6px; border-radius: 4px; }
.x:hover { color: var(--text-strong); background: var(--surface-3); }
.toast-enter-active, .toast-leave-active { transition: all var(--t-med) var(--ease); }
.toast-enter-from { opacity: 0; transform: translateY(8px); }
.toast-leave-to { opacity: 0; transform: translateY(4px); }
</style>
