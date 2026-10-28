<script setup lang="ts">
/** Inline designed error for a failed query (unreachable / server). Auth errors are handled by the shell. */
import { computed } from 'vue'
import { ApiError, API_URL } from '../lib/api'
import EmptyState from './ui/EmptyState.vue'
import Button from './ui/Button.vue'

const props = defineProps<{ error: ApiError | Error | null; retry?: () => void; compact?: boolean; title?: string }>()
const unreachable = computed(() => props.error instanceof ApiError && props.error.kind === 'unreachable')
const heading = computed(() => props.title ?? (unreachable.value ? 'API unreachable' : 'Couldn’t load this'))
const body = computed(() =>
  unreachable.value
    ? `No answer from ${API_URL}. Nothing is shown rather than stale or placeholder data.`
    : (props.error?.message ?? 'Unknown error'),
)
</script>

<template>
  <EmptyState tone="error" :title="heading" :body="body" :compact="compact">
    <template v-if="retry" #actions>
      <Button variant="primary" size="sm" @click="retry">Retry</Button>
    </template>
  </EmptyState>
</template>
