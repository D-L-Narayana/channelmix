// jsdom has no canvas: replace vue-echarts with a lightweight stub that records the option.
import { defineComponent, h } from 'vue'

export default defineComponent({
  name: 'VChartStub',
  props: { option: { type: Object, default: () => ({}) }, autoresize: Boolean },
  emits: ['click'],
  setup(props) {
    return () =>
      h('div', {
        class: 'v-chart-stub',
        'data-series': String((props.option as { series?: unknown[] }).series?.length ?? 0),
      })
  },
})
