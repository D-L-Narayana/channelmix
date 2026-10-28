<script setup lang="ts">
/** Dry-run result: detected format + confidence, column mapping, first rows, warnings, then commit. */
import { computed } from 'vue'
import type { Channel, ImportFormat, ImportResponse, MappingField } from '../lib/types'
import { CHANNELS } from '../lib/types'
import { channelLabel, money, num, pct } from '../lib/format'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Select from './ui/Select.vue'

const props = defineProps<{ preview: ImportResponse; fileName: string; committing?: boolean; format: ImportFormat | null; channel: Channel | null; currency: string }>()
const emit = defineEmits<{ commit: []; cancel: []; 'update:format': [f: ImportFormat | null]; 'update:channel': [c: Channel | null] }>()

const FORMAT_LABEL: Record<string, string> = { google_ads: 'Google Ads export', meta_ads: 'Meta Ads Manager export', generic: 'Generic template' }
const FIELDS: { key: MappingField; label: string; required?: boolean }[] = [
  { key: 'day', label: 'Day', required: true },
  { key: 'campaign_name', label: 'Campaign', required: true },
  { key: 'external_id', label: 'Campaign ID' },
  { key: 'channel', label: 'Channel' },
  { key: 'spend', label: 'Spend', required: true },
  { key: 'impressions', label: 'Impressions' },
  { key: 'clicks', label: 'Clicks' },
  { key: 'conversions', label: 'Conversions' },
  { key: 'revenue', label: 'Revenue' },
]
const PREVIEW_COLS: { key: keyof ImportResponse['preview'][number]; label: string; num?: boolean }[] = [
  { key: 'day', label: 'Day' },
  { key: 'channel', label: 'Channel' },
  { key: 'campaign_name', label: 'Campaign' },
  { key: 'external_id', label: 'ID' },
  { key: 'impressions', label: 'Impr.', num: true },
  { key: 'clicks', label: 'Clicks', num: true },
  { key: 'conversions', label: 'Conv.', num: true },
  { key: 'spend', label: 'Spend', num: true },
  { key: 'revenue', label: 'Revenue', num: true },
]

const p = computed(() => props.preview)
const blocking = computed(() => p.value.row_count === 0 || p.value.status === 'failed')
const confidenceTone = computed(() => (p.value.confidence >= 0.8 ? 'success' : p.value.confidence >= 0.5 ? 'warning' : 'error'))
const missingRequired = computed(() => FIELDS.filter((f) => f.required && !p.value.mapping[f.key]).map((f) => f.label))
const needsChannel = computed(() => !p.value.mapping.channel && !p.value.channel && !props.channel)
const totals = computed(() => {
  const t = { spend: 0, revenue: 0, impressions: 0, clicks: 0, conversions: 0 }
  for (const r of p.value.preview) {
    t.spend += r.spend
    t.revenue += r.revenue
    t.impressions += r.impressions
    t.clicks += r.clicks
    t.conversions += r.conversions
  }
  return t
})
const formatOptions = [{ value: '', label: `Auto (${FORMAT_LABEL[p.value.detected_format] ?? p.value.detected_format})` }, ...Object.entries(FORMAT_LABEL).map(([value, label]) => ({ value, label }))]
const channelOptions = computed(() => [{ value: '', label: p.value.channel ? `Detected: ${channelLabel(p.value.channel)}` : 'Choose…' }, ...CHANNELS.map((c) => ({ value: c, label: channelLabel(c) }))])
</script>

<template>
  <div class="pv" data-testid="import-preview">
    <div class="summary">
      <div class="facts">
        <div class="fact">
          <span class="k">Detected format</span>
          <span class="v"><Badge tone="accent">{{ FORMAT_LABEL[p.detected_format] ?? p.detected_format }}</Badge> <Badge :tone="confidenceTone" size="sm" class="num">{{ pct(p.confidence, 0) }} confidence</Badge></span>
        </div>
        <div class="fact"><span class="k">Rows</span><span class="v num"><b>{{ num(p.row_count) }}</b> parsed<template v-if="p.skipped_rows"> · {{ num(p.skipped_rows) }} skipped</template></span></div>
        <div class="fact"><span class="k">Channel</span><span class="v">{{ p.mapping.channel ? 'from column' : p.channel ? channelLabel(p.channel) : channel ? channelLabel(channel) : '–' }}</span></div>
        <div class="fact"><span class="k">Currency</span><span class="v mono">{{ p.currency ?? 'not in file' }}</span></div>
        <div class="fact"><span class="k">Delimiter</span><span class="v mono">{{ p.delimiter === '\t' ? 'tab' : p.delimiter }}</span></div>
      </div>
      <div class="overrides">
        <Select :model-value="format ?? ''" size="sm" label="Format override" :options="formatOptions" @update:model-value="(v) => emit('update:format', (v || null) as ImportFormat | null)" />
        <Select v-if="!p.mapping.channel" :model-value="channel ?? ''" size="sm" label="Channel for all rows" :options="channelOptions" @update:model-value="(v) => emit('update:channel', (v || null) as Channel | null)" />
      </div>
    </div>

    <div v-if="p.warnings.length || missingRequired.length" class="warnings" role="status">
      <div class="wt">{{ p.warnings.length + missingRequired.length }} thing{{ p.warnings.length + missingRequired.length === 1 ? '' : 's' }} to check</div>
      <ul>
        <li v-for="m in missingRequired" :key="m" class="block">Required field <b>{{ m }}</b> was not found in the file.</li>
        <li v-for="(w, i) in p.warnings" :key="i">{{ w }}</li>
      </ul>
    </div>

    <div class="grid">
      <section class="mapping" aria-labelledby="map-h">
        <h3 id="map-h">Column mapping</h3>
        <table class="dt">
          <thead><tr><th scope="col">ChannelMix field</th><th scope="col">Source column</th></tr></thead>
          <tbody>
            <tr v-for="f in FIELDS" :key="f.key" :class="{ missing: f.required && !p.mapping[f.key] }">
              <td>{{ f.label }}<span v-if="f.required" class="req" title="required"> *</span></td>
              <td class="mono">{{ p.mapping[f.key] ?? '—' }}<span v-if="!p.mapping[f.key] && !f.required" class="muted"> (defaults to {{ f.key === 'channel' ? (p.channel ?? channel ?? 'other') : f.key === 'external_id' ? 'campaign name' : '0' }})</span></td>
            </tr>
          </tbody>
        </table>
        <p v-if="p.unmapped_columns.length" class="unmapped muted">Ignored columns: <span class="mono">{{ p.unmapped_columns.join(', ') }}</span></p>
      </section>

      <section class="rows" aria-labelledby="rows-h">
        <h3 id="rows-h">First {{ p.preview.length }} rows <span class="muted">as they will be stored</span></h3>
        <div class="scroll">
          <table class="dt">
            <thead><tr><th v-for="c in PREVIEW_COLS" :key="c.key" scope="col" :class="{ num: c.num }">{{ c.label }}</th></tr></thead>
            <tbody>
              <tr v-for="(r, i) in p.preview" :key="i" data-testid="preview-row">
                <td v-for="c in PREVIEW_COLS" :key="c.key" :class="{ num: c.num, mono: c.key === 'day' || c.key === 'external_id' }">
                  <template v-if="c.key === 'spend' || c.key === 'revenue'">{{ money(r[c.key], p.currency ?? currency, 2) }}</template>
                  <template v-else-if="c.num">{{ num(r[c.key] as number) }}</template>
                  <template v-else-if="c.key === 'channel'">{{ channelLabel(String(r.channel)) }}</template>
                  <template v-else>{{ r[c.key] }}</template>
                </td>
              </tr>
            </tbody>
            <tfoot><tr><td colspan="4">Preview total</td><td class="num">{{ num(totals.impressions) }}</td><td class="num">{{ num(totals.clicks) }}</td><td class="num">{{ num(totals.conversions) }}</td><td class="num">{{ money(totals.spend, p.currency ?? currency, 2) }}</td><td class="num">{{ money(totals.revenue, p.currency ?? currency, 2) }}</td></tr></tfoot>
          </table>
        </div>
      </section>
    </div>

    <div class="actions">
      <p class="muted note">Rows upsert on (channel, campaign, day) — re-importing the same export is safe and never duplicates data.</p>
      <div class="btns">
        <Button variant="ghost" :disabled="committing" @click="emit('cancel')">Choose another file</Button>
        <Button variant="primary" :loading="committing" :disabled="blocking || missingRequired.length > 0 || needsChannel" data-testid="commit" @click="emit('commit')">
          Import {{ num(p.row_count) }} rows
        </Button>
      </div>
      <p v-if="needsChannel" class="muted note">Pick a channel for the rows before importing — the file has no channel column.</p>
    </div>
  </div>
</template>

<style scoped>
.pv { display: flex; flex-direction: column; gap: 20px; }
.summary { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; align-items: flex-start; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, max-content)); gap: 10px 28px; }
.fact { display: flex; flex-direction: column; gap: 4px; }
.k { font-size: var(--fs-12); text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); font-weight: 500; }
.v { font-size: var(--fs-14); color: var(--text); display: inline-flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.v b { color: var(--text-strong); font-weight: 500; }
.overrides { display: flex; gap: 12px; flex-wrap: wrap; }
.warnings { padding: 12px 14px; border: 1px solid var(--warning); border-radius: var(--r-md); background: var(--warning-soft); }
.wt { font-weight: 500; color: var(--warning-text); font-size: var(--fs-13); margin-bottom: 6px; }
.warnings ul { display: flex; flex-direction: column; gap: 3px; font-size: var(--fs-13); color: var(--text); padding-left: 16px; list-style: disc; }
.warnings li.block { color: var(--error); }
.grid { display: grid; grid-template-columns: minmax(260px, 1fr) minmax(0, 2fr); gap: 20px; }
h3 { font-size: var(--fs-14); font-weight: 500; margin-bottom: 8px; }
h3 .muted { font-weight: 400; }
.dt { width: 100%; border-collapse: collapse; font-size: var(--fs-13); }
.dt th, .dt td { padding: 7px 10px; border-bottom: 1px solid var(--border); text-align: left; white-space: nowrap; }
.dt th { font-size: var(--fs-12); color: var(--muted); font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em; background: var(--surface-2); position: sticky; top: 0; }
.dt .num { text-align: right; font-variant-numeric: tabular-nums; }
.dt tr.missing td { color: var(--error); }
.dt tfoot td { font-weight: 500; color: var(--text-strong); border-bottom: 0; background: var(--surface-2); }
.req { color: var(--accent); }
.unmapped { font-size: var(--fs-12); margin-top: 8px; overflow-wrap: anywhere; }
.scroll { overflow: auto; border: 1px solid var(--border); border-radius: var(--r-md); max-height: 360px; }
.mapping .dt { border: 1px solid var(--border); border-radius: var(--r-md); overflow: hidden; }
.actions { display: flex; flex-direction: column; gap: 10px; border-top: 1px solid var(--border); padding-top: 16px; }
.btns { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }
.note { font-size: var(--fs-13); }
@media (max-width: 1000px) { .grid { grid-template-columns: 1fr; } }
</style>
