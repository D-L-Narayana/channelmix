import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isoDaysAgo, previousRange, todayIso } from '../lib/format'
import type { DateRange } from '../lib/types'

export const PRESETS = [7, 14, 30, 90] as const
export type Preset = (typeof PRESETS)[number] | 'custom'

const ISO = /^\d{4}-\d{2}-\d{2}$/

/** Date range kept in the URL (?start&end) so views are shareable; default = last 30 days. */
export function useDateRange(defaultDays = 30) {
  const route = useRoute()
  const router = useRouter()

  const fromUrl = (): DateRange | null => {
    const s = route.query.start
    const e = route.query.end
    if (typeof s === 'string' && typeof e === 'string' && ISO.test(s) && ISO.test(e) && s <= e) return { start: s, end: e }
    return null
  }
  const defaults = (): DateRange => ({ start: isoDaysAgo(defaultDays - 1), end: todayIso() })

  const range = ref<DateRange>(fromUrl() ?? defaults())

  const preset = computed<Preset>(() => {
    if (range.value.end !== todayIso()) return 'custom'
    for (const p of PRESETS) if (range.value.start === isoDaysAgo(p - 1)) return p
    return 'custom'
  })

  const previous = computed(() => previousRange(range.value))

  function setPreset(days: (typeof PRESETS)[number]) {
    set({ start: isoDaysAgo(days - 1), end: todayIso() })
  }
  function set(r: DateRange) {
    if (!ISO.test(r.start) || !ISO.test(r.end)) return
    if (r.start > r.end) r = { start: r.end, end: r.start }
    range.value = r
  }

  watch(
    range,
    (r) => {
      const isDefault = r.start === isoDaysAgo(defaultDays - 1) && r.end === todayIso()
      const q = { ...route.query }
      if (isDefault) {
        delete q.start
        delete q.end
      } else {
        q.start = r.start
        q.end = r.end
      }
      router.replace({ query: q })
    },
    { deep: true },
  )

  return { range, preset, previous, setPreset, set }
}
