<script setup lang="ts">
import { ref } from 'vue'
import Button from './ui/Button.vue'

const props = withDefaults(defineProps<{ busy?: boolean; maxMb?: number; file?: File | null }>(), { maxMb: 25 })
const emit = defineEmits<{ file: [f: File]; clear: [] }>()
const over = ref(false)
const error = ref<string | null>(null)
const input = ref<HTMLInputElement | null>(null)

function accept(f: File | undefined | null) {
  error.value = null
  if (!f) return
  const ok = /\.(csv|tsv|txt)$/i.test(f.name) || f.type.includes('csv') || f.type.includes('text')
  if (!ok) {
    error.value = `"${f.name}" doesn't look like a CSV export (.csv / .tsv).`
    return
  }
  if (f.size > props.maxMb * 1024 * 1024) {
    error.value = `File is ${(f.size / 1048576).toFixed(1)} MB; the limit is ${props.maxMb} MB. Split the export by month.`
    return
  }
  emit('file', f)
}
function onDrop(e: DragEvent) {
  over.value = false
  accept(e.dataTransfer?.files?.[0])
}
function onPick(e: Event) {
  accept((e.target as HTMLInputElement).files?.[0])
  ;(e.target as HTMLInputElement).value = ''
}
const kb = (n: number) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`)
</script>

<template>
  <div>
    <div
      class="dz"
      :class="{ over, busy, has: !!file }"
      role="button"
      tabindex="0"
      aria-label="Drop a CSV file here or press Enter to choose one"
      @dragover.prevent="over = true"
      @dragleave="over = false"
      @drop.prevent="onDrop"
      @click="input?.click()"
      @keydown.enter.prevent="input?.click()"
      @keydown.space.prevent="input?.click()"
    >
      <input ref="input" class="sr-only" type="file" accept=".csv,.tsv,.txt,text/csv" tabindex="-1" @change="onPick" />
      <template v-if="file">
        <div class="fname"><span class="mono strong">{{ file.name }}</span><span class="muted"> · {{ kb(file.size) }}</span></div>
        <p class="muted hint">{{ busy ? 'Analysing…' : 'Drop another file to replace it' }}</p>
      </template>
      <template v-else>
        <div class="lead">Drop a CSV export here</div>
        <p class="muted hint">Google Ads · Meta Ads Manager · generic template. Nothing is written until you confirm the preview.</p>
        <Button size="sm" variant="secondary" tabindex="-1" @click.stop="input?.click()">Choose file</Button>
      </template>
    </div>
    <p v-if="error" class="err" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.dz {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; text-align: center;
  min-height: 168px; padding: 24px; border: 1.5px dashed var(--border-strong); border-radius: var(--r-lg);
  background: var(--surface-2); cursor: pointer; transition: border-color var(--t-fast) var(--ease), background var(--t-fast) var(--ease);
}
.dz:hover, .dz.over { border-color: var(--accent); background: var(--accent-soft); }
.dz:focus-visible { box-shadow: var(--ring); border-radius: var(--r-lg); }
.dz.has { border-style: solid; border-color: var(--border); }
.dz.busy { cursor: progress; }
.lead { font-size: var(--fs-16); font-weight: 500; color: var(--text-strong); }
.hint { font-size: var(--fs-13); max-width: 46ch; line-height: 1.5; }
.fname { font-size: var(--fs-14); overflow-wrap: anywhere; }
.err { margin-top: 8px; color: var(--error); font-size: var(--fs-13); }
</style>
