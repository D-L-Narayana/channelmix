<script setup lang="ts">
withDefaults(defineProps<{ tone?: 'neutral' | 'accent' | 'success' | 'warning' | 'error' | 'info'; dot?: boolean; mono?: boolean; size?: 'sm' | 'md' }>(), {
  tone: 'neutral',
  size: 'md',
})
</script>

<template>
  <span class="badge" :class="[tone, size, { mono }]">
    <i v-if="dot" class="dot" aria-hidden="true" />
    <slot />
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex; align-items: center; gap: 6px;
  height: 22px; padding: 0 8px; border-radius: var(--r-pill);
  font-size: var(--fs-12); font-weight: 500; line-height: 1; white-space: nowrap;
  border: 1px solid transparent; letter-spacing: 0.01em;
}
.sm { height: 18px; padding: 0 6px; font-size: var(--fs-12); }
.mono { font-family: var(--font-mono); font-weight: 400; }
.neutral { background: var(--surface-3); color: var(--text); border-color: var(--border); }
.accent { background: var(--accent-soft); color: var(--accent); }
.success { background: var(--success-soft); color: var(--success); }
.warning { background: var(--warning-soft); color: var(--warning-text); }
.error { background: var(--error-soft); color: var(--error); }
.info { background: var(--info-soft); color: var(--info); }
.dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
</style>
