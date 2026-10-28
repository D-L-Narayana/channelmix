<script setup lang="ts">
import { computed, useId } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue?: string | number | null
    type?: string
    label?: string
    hint?: string
    error?: string | null
    placeholder?: string
    mono?: boolean
    required?: boolean
    disabled?: boolean
    readonly?: boolean
    size?: 'sm' | 'md'
    autocomplete?: string
    min?: string | number
    max?: string | number
    step?: string | number
    name?: string
    inputmode?: 'text' | 'numeric' | 'decimal' | 'email' | 'search' | 'url' | 'none'
    ariaLabel?: string
  }>(),
  { type: 'text', size: 'md' },
)
const emit = defineEmits<{ 'update:modelValue': [value: string]; enter: [] }>()
const id = useId()
const describedBy = computed(() => (props.error ? `${id}-err` : props.hint ? `${id}-hint` : undefined))
</script>

<template>
  <label class="field" :class="{ invalid: !!error, disabled }" :for="id">
    <span v-if="label" class="lbl">{{ label }}<span v-if="required" class="req" aria-hidden="true"> *</span></span>
    <span class="control" :class="[`s-${size}`]">
      <slot name="prefix" />
      <input
        :id="id"
        :type="type"
        :value="modelValue ?? ''"
        :placeholder="placeholder"
        :required="required"
        :disabled="disabled"
        :readonly="readonly"
        :autocomplete="autocomplete"
        :min="min"
        :max="max"
        :step="step"
        :name="name"
        :inputmode="inputmode"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="describedBy"
        :aria-label="ariaLabel"
        :class="{ mono }"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        @keydown.enter="emit('enter')"
      />
      <slot name="suffix" />
    </span>
    <span v-if="error" :id="`${id}-err`" class="msg err" role="alert">{{ error }}</span>
    <span v-else-if="hint" :id="`${id}-hint`" class="msg hint">{{ hint }}</span>
  </label>
</template>

<style scoped>
.field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.lbl { font-size: var(--fs-13); font-weight: 500; color: var(--text); }
.req { color: var(--accent); }
.control {
  display: flex; align-items: center; gap: 8px;
  height: var(--control-h); padding: 0 12px;
  background: var(--bg); border: 1px solid var(--border); border-radius: var(--r-md);
  transition: border-color var(--t-fast) var(--ease), box-shadow var(--t-fast) var(--ease);
}
.control.s-sm { height: var(--control-h-sm); padding: 0 10px; border-radius: var(--r-sm); font-size: var(--fs-13); }
.control:hover { border-color: var(--border-strong); }
.control:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
.invalid .control { border-color: var(--error); }
.invalid .control:focus-within { box-shadow: 0 0 0 3px var(--error-soft); }
.disabled { opacity: 0.55; }
input {
  flex: 1; min-width: 0; height: 100%; border: 0; outline: none; background: transparent;
  color: var(--text-strong); font-size: inherit; font-variant-numeric: tabular-nums;
}
input:focus-visible { box-shadow: none; }
input.mono { font-family: var(--font-mono); font-size: 0.92em; }
input[type='date']::-webkit-calendar-picker-indicator { filter: invert(0.7); cursor: pointer; }
.msg { font-size: var(--fs-12); line-height: 1.4; }
.hint { color: var(--muted); }
.err { color: var(--error); }
</style>
