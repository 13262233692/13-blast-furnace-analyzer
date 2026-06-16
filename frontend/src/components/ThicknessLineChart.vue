<template>
  <div class="chart-panel">
    <div class="chart-title">各层残损厚度对比 (mm)</div>
    <div ref="lineRef" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useECharts } from '../composables/useECharts.js'

const props = defineProps({
  thicknessMap: { type: Array, default: () => [] }
})

const lineRef = ref(null)
const { setOption, initChart } = useECharts(lineRef)

const layerNames = [
  '炉身上部 L0', '炉身上部 L1', '炉身中部 L2', '炉身中部 L3',
  '炉腰 L4', '炉腰 L5', '炉腹 L6', '炉腹 L7'
]

const layerColors = [
  '#4fc3f7', '#29b6f6', '#03a9f4', '#039be5',
  '#ff9800', '#f57c00', '#f44336', '#d32f2f'
]

const buildOption = (thicknessMap) => {
  if (!thicknessMap || thicknessMap.length === 0) return {}

  const angles = Array.from({ length: 36 }, (_, i) => i * 10)

  const series = thicknessMap.map((layerData, idx) => ({
    name: layerNames[idx],
    type: 'line',
    smooth: true,
    symbol: 'none',
    lineStyle: {
      width: 2,
      color: layerColors[idx]
    },
    itemStyle: {
      color: layerColors[idx]
    },
    areaStyle: idx >= 5 ? {
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: layerColors[idx] + '30' },
        { offset: 1, color: layerColors[idx] + '05' }
      ])
    } : undefined,
    data: layerData,
    markLine: idx === 0 ? {
      silent: true,
      lineStyle: {
        color: '#f44336',
        type: 'dashed',
        width: 2
      },
      data: [
        {
          yAxis: 150,
          label: {
            formatter: '警戒线 150mm',
            color: '#f44336',
            fontSize: 11
          }
        }
      ]
    } : undefined
  }))

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(22, 27, 64, 0.95)',
      borderColor: '#1e2a5a',
      textStyle: { color: '#e8ecf4', fontSize: 12 },
      formatter: (params) => {
        let tip = `<b>角度: ${params[0].axisValue}°</b><br/>`
        params.forEach(p => {
          tip += `${p.marker} ${p.seriesName}: <b>${p.value.toFixed(1)} mm</b><br/>`
        })
        return tip
      }
    },
    legend: {
      data: layerNames,
      top: 5,
      textStyle: { color: '#8892b0', fontSize: 11 },
      itemWidth: 16,
      itemHeight: 8,
      itemGap: 12
    },
    grid: {
      top: 50,
      right: 20,
      bottom: 30,
      left: 60
    },
    xAxis: {
      type: 'category',
      data: angles,
      name: '角度 (°)',
      nameTextStyle: { color: '#8892b0', fontSize: 11 },
      axisLabel: { color: '#8892b0', fontSize: 10, interval: 2 },
      axisLine: { lineStyle: { color: '#1e2a5a' } },
      axisTick: { show: false },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '残厚 (mm)',
      nameTextStyle: { color: '#8892b0', fontSize: 11 },
      min: 100,
      max: 500,
      axisLabel: { color: '#8892b0', fontSize: 11 },
      axisLine: { lineStyle: { color: '#1e2a5a' } },
      splitLine: { lineStyle: { color: '#1e2a5a', type: 'dashed' } }
    },
    series,
    dataZoom: [{
      type: 'inside',
      xAxisIndex: 0,
      start: 0,
      end: 100
    }]
  }
}

import * as echarts from 'echarts'

watch(() => props.thicknessMap, (newData) => {
  if (newData && newData.length > 0) {
    setOption(buildOption(newData))
  }
}, { deep: true })

onMounted(() => {
  initChart()
  if (props.thicknessMap && props.thicknessMap.length > 0) {
    setOption(buildOption(props.thicknessMap))
  }
})
</script>
