<template>
  <div class="chart-panel">
    <div class="chart-title">各层温度环形对比</div>
    <div ref="gaugeRef" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import * as echarts from 'echarts'
import { useECharts } from '../composables/useECharts.js'

const props = defineProps({
  heatmapData: { type: Array, default: () => [] }
})

const gaugeRef = ref(null)
const { setOption, initChart } = useECharts(gaugeRef)

const layerNames = ['L0', 'L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7']

const buildOption = (heatmapData) => {
  if (!heatmapData || heatmapData.length === 0) return {}

  const avgTemps = heatmapData.map(layer => {
    const sum = layer.reduce((a, b) => a + b, 0)
    return Math.round(sum / layer.length)
  })

  const maxTemps = heatmapData.map(layer => Math.round(Math.max(...layer)))

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(22, 27, 64, 0.95)',
      borderColor: '#1e2a5a',
      textStyle: { color: '#e8ecf4', fontSize: 12 }
    },
    legend: {
      data: ['平均温度', '最高温度'],
      top: 5,
      textStyle: { color: '#8892b0', fontSize: 11 },
      itemWidth: 16,
      itemHeight: 8
    },
    grid: {
      top: 50,
      right: 20,
      bottom: 30,
      left: 60
    },
    xAxis: {
      type: 'category',
      data: layerNames,
      axisLabel: { color: '#8892b0', fontSize: 12 },
      axisLine: { lineStyle: { color: '#1e2a5a' } },
      axisTick: { show: false },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '温度 (°C)',
      nameTextStyle: { color: '#8892b0', fontSize: 11 },
      axisLabel: { color: '#8892b0', fontSize: 11 },
      axisLine: { lineStyle: { color: '#1e2a5a' } },
      splitLine: { lineStyle: { color: '#1e2a5a', type: 'dashed' } }
    },
    series: [
      {
        name: '平均温度',
        type: 'bar',
        barWidth: 20,
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#4fc3f7' },
            { offset: 1, color: '#0d47a1' }
          ])
        },
        data: avgTemps
      },
      {
        name: '最高温度',
        type: 'bar',
        barWidth: 20,
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#ff8a65' },
            { offset: 1, color: '#d32f2f' }
          ])
        },
        data: maxTemps
      }
    ]
  }
}

watch(() => props.heatmapData, (newData) => {
  if (newData && newData.length > 0) {
    setOption(buildOption(newData))
  }
}, { deep: true })

onMounted(() => {
  initChart()
  if (props.heatmapData && props.heatmapData.length > 0) {
    setOption(buildOption(props.heatmapData))
  }
})
</script>
