<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CampaignPerformanceRow, Channel } from '../lib/types'
import { CHANNEL_COLORS, CHANNEL_LABELS, money, num, pct, roas } from '../lib/format'

const props = defineProps<{ rows: CampaignPerformanceRow[]; loading?: boolean; selected?: Channel | null }>()
const emit = defineEmits<{ 'update:selected': [Channel | null] }>()

type Key = keyof CampaignPerformanceRow
const sortKey = ref<Key>('spend')
const sortDir = ref<1 | -1>(-1)
const query = ref('')

function sortBy(k: Key) {
  if (sortKey.value === k) sortDir.value = sortDir.value === 1 ? -1 : 1
  else {
    sortKey.value = k
    sortDir.value = k === 'name' || k === 'channel' ? 1 : -1
  }
}

const visible = computed(() => {
  const q = query.value.trim().toLowerCase()
  const filtered = props.rows.filter(
    (r) => (!props.selected || r.channel === props.selected) && (!q || r.name.toLowerCase().includes(q)),
  )
  return [...filtered].sort((a, b) => {
    const x = a[sortKey.value] ?? -Infinity
    const y = b[sortKey.value] ?? -Infinity
    return (x < y ? -1 : x > y ? 1 : 0) * sortDir.value
  })
})

const totals = computed(() => {
  const t = visible.value.reduce(
    (acc, r) => ({ spend: acc.spend + r.spend, revenue: acc.revenue + r.revenue, conversions: acc.conversions + r.conversions, clicks: acc.clicks + r.clicks }),
    { spend: 0, revenue: 0, conversions: 0, clicks: 0 },
  )
  return { ...t, roas: t.spend ? t.revenue / t.spend : null, cpa: t.conversions ? t.spend / t.conversions : null }
})

const arrow = (k: Key) => (sortKey.value === k ? (sortDir.value === 1 ? ' ↑' : ' ↓') : '')
const channels: Channel[] = ['google', 'meta', 'amazon']
</script>

<template>
  <section class="card" data-testid="campaign-table">
    <div class="card-head">
      <div>
        <h2>Campaign drill-down</h2>
        <div class="sub">{{ visible.length }} campaign{{ visible.length === 1 ? '' : 's' }} · rank = ROAS rank within channel</div>
      </div>
      <div class="filters">
        <div class="seg">
          <button class="btn" :class="{ active: !selected }" @click="emit('update:selected', null)">All</button>
          <button v-for="c in channels" :key="c" class="btn" :class="{ active: selected === c }" :data-testid="`filter-${c}`" @click="emit('update:selected', selected === c ? null : c)">
            <i class="sw" :style="{ background: CHANNEL_COLORS[c] }" />{{ CHANNEL_LABELS[c] }}
          </button>
        </div>
        <input v-model="query" class="input" placeholder="Search campaigns…" data-testid="search" />
      </div>
    </div>

    <div v-if="loading" class="skeleton" style="height: 220px" />
    <div v-else class="scroll">
      <table class="table">
        <thead>
          <tr>
            <th class="left" @click="sortBy('name')">Campaign{{ arrow('name') }}</th>
            <th class="left" @click="sortBy('channel')">Channel{{ arrow('channel') }}</th>
            <th @click="sortBy('status')">Status</th>
            <th @click="sortBy('spend')">Spend{{ arrow('spend') }}</th>
            <th @click="sortBy('revenue')">Revenue{{ arrow('revenue') }}</th>
            <th @click="sortBy('roas')">ROAS{{ arrow('roas') }}</th>
            <th @click="sortBy('conversions')">Conv.{{ arrow('conversions') }}</th>
            <th @click="sortBy('cpa')">CPA{{ arrow('cpa') }}</th>
            <th @click="sortBy('clicks')">Clicks{{ arrow('clicks') }}</th>
            <th @click="sortBy('spend_share_in_channel')">Share in ch.{{ arrow('spend_share_in_channel') }}</th>
            <th @click="sortBy('roas_rank_in_channel')">Rank{{ arrow('roas_rank_in_channel') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in visible" :key="r.campaign_id" data-testid="campaign-row">
            <td class="left name">{{ r.name }}</td>
            <td class="left"><span class="chip"><i class="sw" :style="{ background: CHANNEL_COLORS[r.channel] }" />{{ CHANNEL_LABELS[r.channel] }}</span></td>
            <td><span class="badge" :class="r.status === 'active' ? 'good' : 'neutral'">{{ r.status }}</span></td>
            <td>{{ money(r.spend) }}</td>
            <td>{{ money(r.revenue) }}</td>
            <td :class="(r.roas ?? 0) >= 3 ? 'good' : (r.roas ?? 0) < 1.5 ? 'bad' : ''">{{ roas(r.roas) }}</td>
            <td>{{ num(r.conversions) }}</td>
            <td>{{ money(r.cpa, 2) }}</td>
            <td>{{ num(r.clicks) }}</td>
            <td>
              <div class="share"><div class="share-bar" :style="{ width: `${Math.round(r.spend_share_in_channel * 100)}%`, background: CHANNEL_COLORS[r.channel] }" /><span>{{ pct(r.spend_share_in_channel, 0) }}</span></div>
            </td>
            <td><span class="rank" :class="{ top: r.roas_rank_in_channel === 1 }">#{{ r.roas_rank_in_channel }}</span></td>
          </tr>
          <tr v-if="!visible.length"><td colspan="11" class="left muted" style="text-align: center; padding: 28px">No campaigns match.</td></tr>
        </tbody>
        <tfoot v-if="visible.length">
          <tr>
            <td class="left" colspan="3"><b>Total</b></td>
            <td><b>{{ money(totals.spend) }}</b></td>
            <td><b>{{ money(totals.revenue) }}</b></td>
            <td><b>{{ roas(totals.roas) }}</b></td>
            <td><b>{{ num(totals.conversions) }}</b></td>
            <td><b>{{ money(totals.cpa, 2) }}</b></td>
            <td><b>{{ num(totals.clicks) }}</b></td>
            <td colspan="2"></td>
          </tr>
        </tfoot>
      </table>
    </div>
  </section>
</template>

<style scoped>
.filters { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.seg { display: inline-flex; gap: 2px; border: 1px solid var(--border); border-radius: 10px; padding: 2px; }
.seg .btn { border: 0; padding: 4px 10px; font-size: 12.5px; border-radius: 8px; display: inline-flex; align-items: center; gap: 6px; }
.seg .btn.active .sw { outline: 2px solid #fff; }
.sw { width: 9px; height: 9px; border-radius: 3px; display: inline-block; }
.scroll { overflow-x: auto; }
.name { font-weight: 500; }
.share { display: inline-flex; align-items: center; gap: 8px; min-width: 110px; justify-content: flex-end; }
.share-bar { height: 6px; border-radius: 3px; max-width: 70px; min-width: 2px; }
.rank { font-weight: 600; color: var(--muted); }
.rank.top { color: var(--good); }
tfoot td { border-top: 2px solid var(--border); border-bottom: 0; }
</style>
