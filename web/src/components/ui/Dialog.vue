<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = withDefaults(defineProps<{ open: boolean; title: string; description?: string; size?: 'sm' | 'md' | 'lg'; closable?: boolean }>(), {
  size: 'sm',
  closable: true,
})
const emit = defineEmits<{ close: [] }>()
const panel = ref<HTMLElement | null>(null)
let lastActive: Element | null = null

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.closable) {
    e.stopPropagation()
    emit('close')
  }
  if (e.key === 'Tab' && panel.value) {
    const f = panel.value.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
    if (!f.length) return
    const first = f[0]
    const last = f[f.length - 1]
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
  }
}

watch(
  () => props.open,
  async (o) => {
    if (o) {
      lastActive = document.activeElement
      document.addEventListener('keydown', onKey)
      document.body.style.overflow = 'hidden'
      await nextTick()
      const first = panel.value?.querySelector<HTMLElement>('[data-autofocus], input, button:not(.x)')
      first?.focus()
    } else {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      ;(lastActive as HTMLElement | null)?.focus?.()
    }
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="dlg">
      <div v-if="open" class="backdrop" @mousedown.self="closable && emit('close')">
        <div ref="panel" class="panel" :class="size" role="dialog" aria-modal="true" :aria-label="title">
          <header class="head">
            <div>
              <h2 class="title">{{ title }}</h2>
              <p v-if="description" class="desc">{{ description }}</p>
            </div>
            <button v-if="closable" class="x" aria-label="Close dialog" @click="emit('close')">×</button>
          </header>
          <div class="body"><slot /></div>
          <footer v-if="$slots.footer" class="foot"><slot name="footer" /></footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.backdrop {
  position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 16px;
  background: rgba(10, 9, 8, 0.7); backdrop-filter: none;
}
.panel {
  width: 100%; max-width: 420px; background: var(--surface-2); border: 1px solid var(--border);
  border-radius: var(--r-lg); box-shadow: var(--shadow-2); display: flex; flex-direction: column; max-height: calc(100dvh - 32px);
}
.panel.md { max-width: 560px; }
.panel.lg { max-width: 760px; }
.head { display: flex; justify-content: space-between; gap: 12px; padding: 18px 20px 0; }
.title { font-size: var(--fs-18); }
.desc { margin-top: 4px; color: var(--muted); font-size: var(--fs-13); }
.x { background: none; border: 0; color: var(--muted); font-size: 20px; line-height: 1; padding: 2px 6px; border-radius: 4px; height: 28px; }
.x:hover { color: var(--text-strong); background: var(--surface-3); }
.body { padding: 16px 20px; overflow: auto; }
.foot { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 20px 18px; }
.dlg-enter-active, .dlg-leave-active { transition: opacity var(--t-med) var(--ease); }
.dlg-enter-active .panel, .dlg-leave-active .panel { transition: transform var(--t-med) var(--ease); }
.dlg-enter-from, .dlg-leave-to { opacity: 0; }
.dlg-enter-from .panel { transform: translateY(6px) scale(0.99); }
</style>
