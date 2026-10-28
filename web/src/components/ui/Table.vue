<script setup lang="ts" generic="Row extends Record<string, any>">
import { computed } from 'vue'
import Skeleton from './Skeleton.vue'

export interface Column {
  key: string
  label: string
  align?: 'left' | 'right' | 'center'
  sortable?: boolean
  width?: string
  mono?: boolean
  hideBelow?: number // px viewport width under which the column is hidden
}
export interface SortState {
  key: string
  dir: 'asc' | 'desc'
}

const props = withDefaults(
  defineProps<{
    columns: Column[]
    rows: Row[]
    rowKey: (r: Row) => string | number
    sort?: SortState | null
    loading?: boolean
    skeletonRows?: number
    caption?: string
    dense?: boolean
    clickable?: boolean
    stickyHeader?: boolean
  }>(),
  { skeletonRows: 6, dense: false, stickyHeader: true },
)
const emit = defineEmits<{ 'update:sort': [s: SortState]; rowClick: [r: Row] }>()

function toggleSort(c: Column) {
  if (!c.sortable) return
  const cur = props.sort
  if (cur?.key === c.key) emit('update:sort', { key: c.key, dir: cur.dir === 'desc' ? 'asc' : 'desc' })
  else emit('update:sort', { key: c.key, dir: c.align === 'right' ? 'desc' : 'asc' })
}
const ariaSort = (c: Column) => (props.sort?.key === c.key ? (props.sort.dir === 'asc' ? 'ascending' : 'descending') : c.sortable ? 'none' : undefined)
const colStyle = (c: Column) => (c.width ? { width: c.width, minWidth: c.width } : undefined)
const hideClass = (c: Column) => (c.hideBelow ? `hide-${c.hideBelow}` : '')
const skeletonRowsArr = computed(() => Array.from({ length: props.skeletonRows }, (_, i) => i))
</script>

<template>
  <div class="wrap" :class="{ dense }">
    <table :class="{ sticky: stickyHeader }">
      <caption v-if="caption" class="sr-only">{{ caption }}</caption>
      <thead>
        <tr>
          <th
            v-for="c in columns"
            :key="c.key"
            :class="[c.align ?? 'left', hideClass(c), { sortable: c.sortable, active: sort?.key === c.key }]"
            :style="colStyle(c)"
            :aria-sort="ariaSort(c)"
            scope="col"
          >
            <button v-if="c.sortable" type="button" class="th-btn" @click="toggleSort(c)">
              <span>{{ c.label }}</span>
              <span class="arrow" aria-hidden="true">{{ sort?.key === c.key ? (sort.dir === 'asc' ? '↑' : '↓') : '↕' }}</span>
            </button>
            <span v-else>{{ c.label }}</span>
          </th>
        </tr>
      </thead>
      <tbody v-if="loading">
        <tr v-for="i in skeletonRowsArr" :key="i" class="sk-row">
          <td v-for="c in columns" :key="c.key" :class="[c.align ?? 'left', hideClass(c)]">
            <Skeleton :width="c.align === 'right' ? '56px' : '70%'" height="12px" :inline="c.align === 'right'" />
          </td>
        </tr>
      </tbody>
      <tbody v-else>
        <tr
          v-for="r in rows"
          :key="rowKey(r)"
          :class="{ clickable }"
          :tabindex="clickable ? 0 : undefined"
          @click="clickable && emit('rowClick', r)"
          @keydown.enter="clickable && emit('rowClick', r)"
        >
          <td v-for="c in columns" :key="c.key" :class="[c.align ?? 'left', hideClass(c), { mono: c.mono, num: c.align === 'right' }]">
            <slot :name="`cell-${c.key}`" :row="r" :value="r[c.key]">{{ r[c.key] }}</slot>
          </td>
        </tr>
        <tr v-if="!rows.length" class="empty-row">
          <td :colspan="columns.length"><slot name="empty"><span class="muted">Nothing to show.</span></slot></td>
        </tr>
      </tbody>
      <tfoot v-if="$slots.foot && !loading && rows.length">
        <slot name="foot" />
      </tfoot>
    </table>
  </div>
</template>

<style scoped>
.wrap { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: var(--fs-14); }
th, td { padding: 10px 14px; text-align: left; vertical-align: middle; border-bottom: 1px solid var(--border); white-space: nowrap; }
.dense th, .dense td { padding: 7px 12px; font-size: var(--fs-13); }
th { font-size: var(--fs-12); font-weight: 500; color: var(--muted); letter-spacing: 0.04em; text-transform: uppercase; background: var(--surface); }
.sticky th { position: sticky; top: 0; z-index: 1; }
td { color: var(--text); }
td.num, th.right { font-variant-numeric: tabular-nums lining-nums; }
.right { text-align: right; }
.center { text-align: center; }
td.mono { font-family: var(--font-mono); font-size: var(--fs-13); }
tbody tr:last-child td { border-bottom: 0; }
tbody tr.clickable { cursor: pointer; }
tbody tr.clickable:hover td { background: var(--surface-2); }
tbody tr.clickable:focus-visible { outline: none; }
tbody tr.clickable:focus-visible td { background: var(--surface-2); box-shadow: inset 2px 0 0 var(--accent); }
.th-btn { display: inline-flex; align-items: center; gap: 4px; background: none; border: 0; padding: 0; color: inherit; font: inherit; letter-spacing: inherit; text-transform: inherit; cursor: pointer; }
.th-btn:hover { color: var(--text-strong); }
th.active .th-btn { color: var(--text-strong); }
.arrow { opacity: 0.5; font-size: 11px; }
th.active .arrow { opacity: 1; color: var(--accent); }
.empty-row td { padding: 28px 14px; text-align: center; }
:deep(tfoot td) { font-weight: 500; color: var(--text-strong); border-top: 1px solid var(--border-strong); border-bottom: 0; background: var(--surface-2); }
@media (max-width: 1100px) { .hide-1100 { display: none; } }
@media (max-width: 900px) { .hide-900 { display: none; } }
@media (max-width: 640px) { .hide-640 { display: none; } th, td { padding: 9px 10px; } }
</style>
