/** Register only the ECharts pieces we use (tree-shaken bundle) + shared dark defaults. */
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, MarkLineComponent])

export const reducedMotion = () => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches

export const chartText = {
  fontFamily: "'General Sans', ui-sans-serif, system-ui, sans-serif",
  color: '#8f8e8b',
  fontSize: 12,
}

export const axisBase = {
  axisLine: { show: false },
  axisTick: { show: false },
  axisLabel: { ...chartText, hideOverlap: true },
  splitLine: { lineStyle: { color: '#2a2927', type: 'dashed' as const } },
}

export const tooltipBase = {
  trigger: 'axis' as const,
  backgroundColor: '#201f1d',
  borderColor: '#393836',
  borderWidth: 1,
  padding: [8, 10],
  textStyle: { color: '#efeeec', fontSize: 12, fontFamily: chartText.fontFamily },
  extraCssText: 'box-shadow: 0 8px 28px rgba(0,0,0,.45); border-radius: 8px; font-variant-numeric: tabular-nums;',
  axisPointer: { type: 'line' as const, lineStyle: { color: '#4a4947' } },
}

export const animation = () => ({ animation: !reducedMotion(), animationDuration: 600, animationEasing: 'cubicOut' as const, animationDurationUpdate: 300 })
