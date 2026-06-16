import { computed, shallowRef, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'

export function useECharts(chartRef) {
  const chartInstance = shallowRef(null)

  const initChart = () => {
    if (chartRef.value && !chartInstance.value) {
      chartInstance.value = echarts.init(chartRef.value, 'dark')
    }
  }

  const setOption = (option) => {
    if (!chartInstance.value) initChart()
    if (chartInstance.value) {
      chartInstance.value.setOption(option, true)
    }
  }

  const resize = () => {
    if (chartInstance.value) {
      chartInstance.value.resize()
    }
  }

  onMounted(() => {
    window.addEventListener('resize', resize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', resize)
    if (chartInstance.value) {
      chartInstance.value.dispose()
      chartInstance.value = null
    }
  })

  return { chartInstance, initChart, setOption, resize }
}
