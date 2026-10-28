<script setup lang="ts">
/**
 * Accessible chart container: insight title, aria description, a "Table" toggle
 * that swaps the canvas for a real data table, and a sized skeleton so the layout never shifts.
 */
import { ref } from 'vue'
import Card from './ui/Card.vue'
import Skeleton from './ui/Skeleton.vue'

withDefaults(defineProps<{ title: string; subtitle?: string; loading?: boolean; height?: number; desc: string; empty?: boolean; emptyText?: string }>(), {
  height: 280,
  emptyText: 'No data in this range.',
})
const showTable = ref(false)
</script>

<template>
  <Card :title="title" :subtitle="subtitle">
    <template #actions>
      <slot name="actions" />
      <div class="seg" role="group" aria-label="View as">
        <button type="button" :class="{ on: !showTable }" :aria-pressed="!showTable" @click="showTable = false">Chart</button>
        <button type="button" :class="{ on: showTable }" :aria-pressed="showTable" @click="showTable = true">Table</button>
      </div>
    </template>
    <div class="frame" :style="{ minHeight: height + 'px' }">
      <div v-if="loading" class="sk" :style="{ height: height + 'px' }" aria-busy="true">
        <Skeleton v-for="(h, i) in [60, 85, 45, 70, 95, 55, 80, 65, 90, 50, 75, 60]" :key="i" :height="h + '%'" width="100%" radius="3px" />
      </div>
      <div v-else-if="empty" class="empty" :style="{ height: height + 'px' }" role="status">
        <span class="muted">{{ emptyText }}</span>
      </div>
      <div v-else-if="showTable" class="table" :style="{ maxHeight: height + 'px' }">
        <slot name="table" />
      </div>
      <figure v-else class="fig" :style="{ height: height + 'px' }" role="img" :aria-label="desc">
        <slot />
      </figure>
    </div>
  </Card>
</template>

<style scoped>
.frame { position: relative; }
.fig { margin: 0; width: 100%; }
.sk { display: flex; align-items: flex-end; gap: 6px; padding: 12px 0 24px; }
.empty { display: grid; place-items: center; border: 1px dashed var(--border); border-radius: var(--r-md); font-size: var(--fs-13); }
.table { overflow: auto; border: 1px solid var(--border); border-radius: var(--r-md); }
.seg { display: inline-flex; border: 1px solid var(--border); border-radius: var(--r-sm); overflow: hidden; }
.seg button { height: 26px; padding: 0 10px; background: var(--surface-2); border: 0; color: var(--muted); font-size: var(--fs-12); font-weight: 500; }
.seg button + button { border-left: 1px solid var(--border); }
.seg button.on { background: var(--surface-3); color: var(--text-strong); }
.seg button:focus-visible { box-shadow: inset var(--ring); border-radius: 0; }
</style>
