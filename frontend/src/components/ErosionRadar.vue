<template>
  <div class="chart-panel">
    <div class="chart-title">侵蚀预警雷达图</div>
    <div ref="radarRef" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import * as echarts from 'echarts'
import { useECharts } from '../composables/useECharts.js'

const props = defineProps({
  thicknessMap: { type: Array, default: () => [] }
})

const radarRef = ref(null)
const { setOption, initChart } = useECharts(radarRef)

const layerLabels = ['炉身上部', '炉身上部', '炉身中部', '炉身中部', '炉腰', '炉腰', '炉腹', '炉腹']

const buildOption = (thicknessMap) => {
  if (!thicknessMap || thicknessMap.length === 0) return {}

  const originalThickness = 450.0
  const erosionRatios = thicknessMap.map(layer => {
    const minThickness = Math.min(...layer)
    return Math.round(((originalThickness - minThickness) / originalThickness) * 100)
  })

  return {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: 'rgba(22, 27, 64, 0.95)',
      borderColor: '#1e2a5a',
      textStyle: { color: '#e8ecf4', fontSize: 12 }
    },
    radar: {
      indicator: layerLabels.map((name, i) => ({
        name: `${name} L${i}`,
        max: 80
      })),
      shape: 'polygon',
      splitNumber: 4,
      axisName: {
        color: '#8892b0',
        fontSize: 11
      },
      splitLine: {
        lineStyle: { color: '#1e2a5a' }
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(30, 42, 90, 0.3)', 'rgba(30, 42, 90, 0.1)']
        }
      },
      axisLine: {
        lineStyle: { color: '#1e2a5a' }
      }
    },
    series: [{
      type: 'radar',
      data: [
        {
          value: erosionRatios,
          name: '侵蚀率 %',
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: {
            width: 2,
            color: '#f44336'
          },
          itemStyle: {
            color: '#f44336'
          },
          areaStyle: {
            color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
              { offset: 0, color: 'rgba(244, 67, 54, 0.4)' },
              { offset: 1, color: 'rgba(244, 67, 54, 0.05)' }
            ])
          }
        }
      ]
    }]
  }
}

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
