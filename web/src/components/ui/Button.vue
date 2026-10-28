<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
    size?: 'sm' | 'md' | 'lg'
    type?: 'button' | 'submit' | 'reset'
    loading?: boolean
    disabled?: boolean
    block?: boolean
    to?: string | Record<string, unknown>
    href?: string
    ariaLabel?: string
  }>(),
  { variant: 'secondary', size: 'md', type: 'button' },
)

const tag = computed(() => (props.to ? 'router-link' : props.href ? 'a' : 'button'))
const isDisabled = computed(() => props.disabled || props.loading)
</script>

<template>
  <component
    :is="tag"
    class="btn"
    :class="[`v-${variant}`, `s-${size}`, { block, loading }]"
    :type="tag === 'button' ? type : undefined"
    :disabled="tag === 'button' ? isDisabled : undefined"
    :aria-disabled="tag !== 'button' && isDisabled ? 'true' : undefined"
    :aria-busy="loading ? 'true' : undefined"
    :aria-label="ariaLabel"
    :to="to"
    :href="href"
    :tabindex="tag !== 'button' && isDisabled ? -1 : undefined"
  >
    <span v-if="loading" class="spinner" aria-hidden="true" />
    <span class="label"><slot /></span>
  </component>
</template>

<style scoped>
.btn {
  --h: var(--control-h);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: var(--h);
  padding: 0 14px;
  border-radius: var(--r-md);
  border: 1px solid transparent;
  font-weight: 500;
  font-size: var(--fs-14);
  line-height: 1;
  white-space: nowrap;
  text-decoration: none;
  color: var(--text-strong);
  background: transparent;
  transition: background var(--t-fast) var(--ease), border-color var(--t-fast) var(--ease), color var(--t-fast) var(--ease), transform var(--t-fast) var(--ease);
  user-select: none;
}
.btn:active:not(:disabled) { transform: translateY(0.5px); }
.btn:disabled, .btn[aria-disabled='true'] { opacity: 0.5; cursor: not-allowed; }
.btn.block { width: 100%; }
.s-sm { --h: var(--control-h-sm); padding: 0 10px; font-size: var(--fs-13); border-radius: var(--r-sm); }
.s-lg { --h: 44px; padding: 0 20px; font-size: var(--fs-16); }

.v-primary { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
.v-primary:hover:not(:disabled) { background: #ffbd66; border-color: #ffbd66; color: var(--accent-ink); }
.v-secondary { background: var(--surface-2); border-color: var(--border); color: var(--text-strong); }
.v-secondary:hover:not(:disabled) { background: var(--surface-3); border-color: var(--border-strong); }
.v-ghost { color: var(--text); }
.v-ghost:hover:not(:disabled) { background: var(--surface-2); color: var(--text-strong); }
.v-danger { background: transparent; border-color: var(--error); color: var(--error); }
.v-danger:hover:not(:disabled) { background: var(--error-soft); }

.spinner {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid currentColor; border-right-color: transparent;
  animation: spin 0.8s linear infinite;
}
.loading .label { opacity: 0.8; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
