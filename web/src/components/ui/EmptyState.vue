<script setup lang="ts">
withDefaults(defineProps<{ title: string; body?: string; tone?: 'neutral' | 'error' | 'warning'; compact?: boolean }>(), { tone: 'neutral' })
</script>

<template>
  <div class="empty" :class="[tone, { compact }]" role="status">
    <div class="mark" aria-hidden="true"><slot name="mark"><span class="glyph">{{ tone === 'error' ? '!' : tone === 'warning' ? '?' : '·' }}</span></slot></div>
    <h3 class="t">{{ title }}</h3>
    <p v-if="body" class="b">{{ body }}</p>
    <slot />
    <div v-if="$slots.actions" class="actions"><slot name="actions" /></div>
  </div>
</template>

<style scoped>
.empty {
  display: flex; flex-direction: column; align-items: center; text-align: center;
  padding: 40px 24px; gap: 6px; max-width: 460px; margin: 0 auto;
}
.compact { padding: 24px 16px; }
.mark {
  width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center;
  border: 1px dashed var(--border-strong); color: var(--muted); margin-bottom: 8px;
  font-family: var(--font-mono); font-size: var(--fs-16);
}
.error .mark { border-color: var(--error); color: var(--error); border-style: solid; }
.warning .mark { border-color: var(--warning-text); color: var(--warning-text); border-style: solid; }
.t { font-size: var(--fs-16); font-weight: 500; }
.b { color: var(--muted); font-size: var(--fs-14); max-width: 40ch; line-height: 1.5; }
.actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; justify-content: center; }
</style>
