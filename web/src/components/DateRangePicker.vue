<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { PRESETS, type Preset } from '../composables/useDateRange'
import type { DateRange } from '../lib/types'
import { daysBetween, shortDate, todayIso } from '../lib/format'
import Input from './ui/Input.vue'
import Button from './ui/Button.vue'

const props = defineProps<{ modelValue: DateRange; preset: Preset }>()
const emit = defineEmits<{ 'update:modelValue': [r: DateRange]; preset: [days: (typeof PRESETS)[number]] }>()

const customOpen = ref(false)
const start = ref(props.modelValue.start)
const end = ref(props.modelValue.end)
watch(
  () => props.modelValue,
  (r) => {
    start.value = r.start
    end.value = r.end
  },
  { deep: true },
)
const label = computed(() => `${shortDate(props.modelValue.start)} – ${shortDate(props.modelValue.end)} · ${daysBetween(props.modelValue.start, props.modelValue.end)}d`)
const invalid = computed(() => !start.value || !end.value || start.value > end.value || end.value > todayIso())

function apply() {
  if (invalid.value) return
  emit('update:modelValue', { start: start.value, end: end.value })
  customOpen.value = false
}
</script>

<template>
  <div class="picker">
    <div class="presets" role="group" aria-label="Date range">
      <button v-for="p in PRESETS" :key="p" type="button" class="p" :class="{ on: preset === p }" :aria-pressed="preset === p" @click="emit('preset', p); customOpen = false">
        {{ p }}d
      </button>
      <button type="button" class="p" :class="{ on: preset === 'custom' || customOpen }" :aria-pressed="preset === 'custom'" :aria-expanded="customOpen" @click="customOpen = !customOpen">
        Custom
      </button>
    </div>
    <span class="lbl num" aria-live="polite">{{ label }}</span>
    <form v-if="customOpen" class="custom" @submit.prevent="apply">
      <Input v-model="start" type="date" size="sm" aria-label="Start date" :max="end || todayIso()" />
      <span class="muted" aria-hidden="true">–</span>
      <Input v-model="end" type="date" size="sm" aria-label="End date" :min="start" :max="todayIso()" />
      <Button type="submit" size="sm" variant="primary" :disabled="invalid">Apply</Button>
    </form>
  </div>
</template>

<style scoped>
.picker { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.presets { display: inline-flex; border: 1px solid var(--border); border-radius: var(--r-md); overflow: hidden; background: var(--surface-2); }
.p { height: 34px; padding: 0 12px; border: 0; background: transparent; color: var(--muted); font-size: var(--fs-13); font-weight: 500; font-variant-numeric: tabular-nums; }
.p + .p { border-left: 1px solid var(--border); }
.p:hover { color: var(--text-strong); }
.p.on { background: var(--surface-3); color: var(--text-strong); box-shadow: inset 0 -2px 0 var(--accent); }
.p:focus-visible { box-shadow: inset var(--ring); border-radius: 0; }
.lbl { font-size: var(--fs-13); color: var(--muted); white-space: nowrap; }
.custom { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
@media (max-width: 640px) { .p { padding: 0 10px; } .lbl { width: 100%; } }
</style>
