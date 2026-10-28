<script setup lang="ts">
import { computed } from 'vue'
import type { DateRange } from '../lib/types'
import { isoDaysAgo } from '../lib/format'

const props = defineProps<{ modelValue: DateRange; anchor?: string }>()
const emit = defineEmits<{ 'update:modelValue': [DateRange] }>()

const presets = [
  { label: '7D', days: 7 },
  { label: '14D', days: 14 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
]

const anchorDate = computed(() => (props.anchor ? new Date(props.anchor) : new Date()))

function preset(days: number) {
  const end = anchorDate.value.toISOString().slice(0, 10)
  emit('update:modelValue', { start: isoDaysAgo(days - 1, anchorDate.value), end })
}

function isActive(days: number) {
  const end = anchorDate.value.toISOString().slice(0, 10)
  return props.modelValue.end === end && props.modelValue.start === isoDaysAgo(days - 1, anchorDate.value)
}

function setStart(e: Event) {
  const v = (e.target as HTMLInputElement).value
  if (v && v <= props.modelValue.end) emit('update:modelValue', { ...props.modelValue, start: v })
}
function setEnd(e: Event) {
  const v = (e.target as HTMLInputElement).value
  if (v && v >= props.modelValue.start) emit('update:modelValue', { ...props.modelValue, end: v })
}
</script>

<template>
  <div class="range" data-testid="date-range">
    <div class="presets">
      <button
        v-for="p in presets"
        :key="p.label"
        class="btn"
        :class="{ active: isActive(p.days) }"
        :data-testid="`preset-${p.label}`"
        @click="preset(p.days)"
      >
        {{ p.label }}
      </button>
    </div>
    <div class="inputs">
      <input class="input" type="date" :value="modelValue.start" :max="modelValue.end" aria-label="Start date" @change="setStart" />
      <span class="muted">→</span>
      <input class="input" type="date" :value="modelValue.end" :min="modelValue.start" aria-label="End date" @change="setEnd" />
    </div>
  </div>
</template>

<style scoped>
.range { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.presets { display: inline-flex; gap: 4px; background: #fff; border: 1px solid var(--border); border-radius: 11px; padding: 3px; }
.presets .btn { border: 0; padding: 5px 11px; border-radius: 8px; }
.inputs { display: flex; align-items: center; gap: 8px; }
.inputs .input { padding: 6px 9px; }
</style>
