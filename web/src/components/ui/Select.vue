<script setup lang="ts">
import { useId } from 'vue'

export interface SelectOption { value: string | number; label: string; disabled?: boolean }

withDefaults(
  defineProps<{
    modelValue: string | number | null
    options: SelectOption[]
    label?: string
    placeholder?: string
    size?: 'sm' | 'md'
    disabled?: boolean
    ariaLabel?: string
  }>(),
  { size: 'md' },
)
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const id = useId()
</script>

<template>
  <label class="field" :for="id">
    <span v-if="label" class="lbl">{{ label }}</span>
    <span class="control" :class="[`s-${size}`, { disabled }]">
      <select
        :id="id"
        :value="modelValue ?? ''"
        :disabled="disabled"
        :aria-label="ariaLabel ?? label"
        @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
      >
        <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
        <option v-for="o in options" :key="o.value" :value="o.value" :disabled="o.disabled">{{ o.label }}</option>
      </select>
      <svg class="chev" width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </span>
  </label>
</template>

<style scoped>
.field { display: inline-flex; flex-direction: column; gap: 6px; min-width: 0; }
.lbl { font-size: var(--fs-13); font-weight: 500; }
.control {
  position: relative; display: inline-flex; align-items: center;
  height: var(--control-h); background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r-md);
  transition: border-color var(--t-fast) var(--ease), box-shadow var(--t-fast) var(--ease);
}
.control.s-sm { height: var(--control-h-sm); border-radius: var(--r-sm); font-size: var(--fs-13); }
.control:hover { border-color: var(--border-strong); }
.control:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
.control.disabled { opacity: 0.55; }
select {
  appearance: none; -webkit-appearance: none; height: 100%; width: 100%;
  padding: 0 30px 0 12px; border: 0; outline: none; background: transparent; color: var(--text-strong);
  font-size: inherit; cursor: pointer;
}
.s-sm select { padding: 0 26px 0 10px; }
select:focus-visible { box-shadow: none; }
select option { background: var(--surface-2); color: var(--text-strong); }
.chev { position: absolute; right: 9px; pointer-events: none; color: var(--muted); }
</style>
