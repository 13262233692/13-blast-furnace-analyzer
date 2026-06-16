<template>
  <div class="chart-panel">
    <div class="chart-title">高炉各层温度分布热力图 (层 × 角度)</div>
    <div ref="heatmapRef" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useECharts } from '../composables/useECharts.js'

const props = defineProps({
  heatmapData: { type: Array, default: () => [] }
})

const heatmapRef = ref(null)
const { setOption, initChart, resize } = useECharts(heatmapRef)

const layerNames = [
  '炉身上部(L0)', '炉身上部(L1)', '炉身中部(L2)', '炉身中部(L3)',
  '炉腰(L4)', '炉腰(L5)', '炉腹(L6)', '炉腹(L7)'
]

const buildOption = (data) => {
  if (!data || data.length === 0) return {}

  const angles = Array.from({ length: 36 }, (_, i) => `${i * 10}°`)
  const seriesData = []
  let minVal = Infinity, maxVal = -Infinity

  for (let layerIdx = 0; layerIdx < data.length; layerIdx++) {
    for (let angleIdx = 0; angleIdx < data[layerIdx].length; angleIdx++) {
      const val = data[layerIdx][angleIdx]
      seriesData.push([angleIdx, layerIdx, val])
      if (val < minVal) minVal = val
      if (val > maxVal) maxVal = val
    }
  }

  return {
    backgroundColor: 'transparent',
    tooltip: {
      position: 'top',
      formatter: (params) => {
        const layerName = layerNames[params.value[1]]
        const angle = angles[params.value[0]]
        return `${layerName} / ${angle}<br/>温度: <b>${params.value[2]}°C</b>`
      }
    },
    grid: {
      top: 30,
      right: 80,
      bottom: 40,
      left: 90,
      containLabel: false
    },
    xAxis: {
      type: 'category',
      data: angles,
      splitArea: { show: false },
      axisLabel: {
        color: '#8892b0',
        fontSize: 10,
        interval: 2
      },
      axisLine: { lineStyle: { color: '#1e2a5a' } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'category',
      data: layerNames,
      splitArea: { show: false },
      axisLabel: {
        color: '#8892b0',
        fontSize: 11
      },
      axisLine: { lineStyle: { color: '#1e2a5a' } },
      axisTick: { show: false }
    },
    visualMap: {
      min: Math.floor(minVal),
      max: Math.ceil(maxVal),
      calculable: true,
      orient: 'vertical',
      right: 5,
      top: 30,
      bottom: 40,
      inRange: {
        color: ['#0d47a1', '#1565c0', '#1e88e5', '#42a5f5', '#81d4fa',
                '#fff176', '#ffb74d', '#ff8a65', '#e57373', '#d32f2f']
      },
      textStyle: { color: '#8892b0', fontSize: 11 },
      text: ['高温', '低温']
    },
    series: [{
      type: 'heatmap',
      data: seriesData,
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      },
      itemStyle: {
        borderColor: '#0a0e27',
        borderWidth: 1
      }
    }]
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
