<template>
  <div class="dashboard" v-if="!loading">
    <header class="header">
      <div class="header-title">
        <div class="header-icon">🔥</div>
        <h1>高炉内部侵蚀状况监测平台</h1>
      </div>
      <div class="status-badges">
        <span class="status-badge info">
          <span class="status-dot" style="background: #4fc3f7"></span>
          传感器: {{ status.active_sensors || 0 }} / {{ status.total_sensors || 0 }}
        </span>
        <span :class="['status-badge', alertClass]">
          <span class="status-dot" :style="{ background: alertColor }"></span>
          告警等级: {{ status.alert_level || '未知' }}
        </span>
        <span class="status-badge normal">
          <span class="status-dot" style="background: #4caf50"></span>
          实时在线
        </span>
      </div>
    </header>

    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-label">最小残厚</span>
        <span class="stat-value red">
          {{ status.min_thickness_mm || '-' }}
          <span class="stat-unit">mm</span>
        </span>
      </div>
      <div class="stat-card">
        <span class="stat-label">最大侵蚀率</span>
        <span class="stat-value orange">
          {{ ((status.max_erosion_ratio || 0) * 100).toFixed(1) }}
          <span class="stat-unit">%</span>
        </span>
      </div>
      <div class="stat-card">
        <span class="stat-label">监测层级</span>
        <span class="stat-value cyan">
          8
          <span class="stat-unit">层</span>
        </span>
      </div>
      <div class="stat-card">
        <span class="stat-label">数据刷新周期</span>
        <span class="stat-value green">
          1
          <span class="stat-unit">秒</span>
        </span>
      </div>
    </div>

    <div class="charts-row">
      <HeatmapChart :heatmap-data="heatmap" />
      <ThicknessLineChart :thickness-map="thicknessMap" />
    </div>

    <div class="bottom-row">
      <LayerBarChart :heatmap-data="heatmap" />
      <ErosionRadar :thickness-map="thicknessMap" />
    </div>
  </div>

  <div class="loading-overlay" v-else>
    <div class="loading-spinner"></div>
    <span class="loading-text">正在连接高炉传感器数据源...</span>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchStatus, fetchHeatmap, fetchThickness } from './api.js'
import HeatmapChart from './components/HeatmapChart.vue'
import ThicknessLineChart from './components/ThicknessLineChart.vue'
import LayerBarChart from './components/LayerBarChart.vue'
import ErosionRadar from './components/ErosionRadar.vue'

const loading = ref(true)
const status = ref({})
const heatmap = ref([])
const thicknessMap = ref([])

let timer = null

const alertClass = computed(() => {
  const level = status.value.alert_level
  if (level === '严重') return 'danger'
  if (level === '警告' || level === '注意') return 'warning'
  return 'normal'
})

const alertColor = computed(() => {
  const level = status.value.alert_level
  if (level === '严重') return '#f44336'
  if (level === '警告' || level === '注意') return '#ffc107'
  return '#4caf50'
})

const loadData = async () => {
  try {
    const [statusData, heatmapData, thicknessData] = await Promise.all([
      fetchStatus(),
      fetchHeatmap(),
      fetchThickness()
    ])
    status.value = statusData
    heatmap.value = heatmapData.temperatures || []
    thicknessMap.value = thicknessData.thickness_map || []
    loading.value = false
  } catch (e) {
    console.error('数据加载失败:', e)
  }
}

onMounted(() => {
  loadData()
  timer = setInterval(loadData, 2000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
