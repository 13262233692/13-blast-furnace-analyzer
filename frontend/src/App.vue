<template>
  <div class="dashboard v2" v-if="!loading">
    <header class="header">
      <div class="header-title">
        <div class="header-icon">🔥</div>
        <h1>高炉内部侵蚀状况监测平台 · 3D 数字孪生</h1>
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

    <div class="main-grid">
      <div class="left-col">
        <div class="stats-col">
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
            <span class="stat-label">数据刷新</span>
            <span class="stat-value green">
              2
              <span class="stat-unit">秒</span>
            </span>
          </div>
        </div>

        <div class="chart-panel">
          <div class="chart-title">各层残损厚度对比</div>
          <div class="chart-container small">
            <ThicknessLineChart :thickness-map="thicknessMap" />
          </div>
        </div>

        <div class="chart-panel">
          <div class="chart-title">侵蚀预警雷达</div>
          <div class="chart-container small">
            <ErosionRadar :thickness-map="thicknessMap" />
          </div>
        </div>
      </div>

      <div class="center-col">
        <BlastFurnace3D :thickness-map="thicknessMap" />
      </div>

      <div class="right-col">
        <div class="chart-panel">
          <div class="chart-title">温度分布热力图</div>
          <div class="chart-container">
            <HeatmapChart :heatmap-data="heatmap" />
          </div>
        </div>

        <div class="chart-panel">
          <div class="chart-title">各层温度柱状对比</div>
          <div class="chart-container small">
            <LayerBarChart :heatmap-data="heatmap" />
          </div>
        </div>

        <div class="chart-panel ero-summary">
          <div class="chart-title">侵蚀热点 TOP 5</div>
          <div class="ero-list">
            <div
              v-for="(item, i) in topErosionPoints"
              :key="i"
              class="ero-item"
            >
              <span class="ero-rank" :class="'rank-' + (i + 1)">{{ i + 1 }}</span>
              <span class="ero-label">第{{ item.layer }}层 · {{ item.angle }}°</span>
              <span class="ero-bar">
                <span
                  class="ero-bar-fill"
                  :style="{ width: (item.erosion * 100).toFixed(1) + '%' }"
                ></span>
              </span>
              <span class="ero-val">{{ (item.erosion * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </div>
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
import BlastFurnace3D from './components/BlastFurnace3D.vue'

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

const topErosionPoints = computed(() => {
  const original = 450
  const points = []
  const tm = thicknessMap.value
  if (!tm || !tm.length) return []
  for (let layer = 0; layer < tm.length; layer++) {
    for (let angleIdx = 0; angleIdx < tm[layer].length; angleIdx++) {
      const t = tm[layer][angleIdx]
      const erosion = 1 - t / original
      points.push({
        layer,
        angle: angleIdx * 10,
        erosion,
        thickness: t,
      })
    }
  }
  return points
    .sort((a, b) => b.erosion - a.erosion)
    .slice(0, 5)
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

<style scoped>
.dashboard.v2 {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 10px 12px;
  gap: 10px;
}

.main-grid {
  flex: 1;
  display: grid;
  grid-template-columns: 320px 1fr 360px;
  gap: 10px;
  min-height: 0;
}

.left-col,
.right-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}

.center-col {
  min-height: 0;
  display: flex;
}

.stats-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.stats-col .stat-card {
  padding: 12px 14px;
  min-height: auto;
}

.stats-col .stat-value {
  font-size: 22px;
}

.chart-container.small {
  min-height: 180px;
}

.ero-summary {
  flex: none;
}

.ero-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0;
}

.ero-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.ero-rank {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 11px;
  color: #0a0e27;
  flex-shrink: 0;
}

.ero-rank.rank-1 { background: #f44336; color: #fff; }
.ero-rank.rank-2 { background: #ff9800; color: #fff; }
.ero-rank.rank-3 { background: #ffc107; }
.ero-rank.rank-4 { background: #81d4fa; }
.ero-rank.rank-5 { background: #90caf9; }

.ero-label {
  color: #b0b8d4;
  width: 90px;
  flex-shrink: 0;
}

.ero-bar {
  flex: 1;
  height: 6px;
  background: #1e2a5a;
  border-radius: 3px;
  overflow: hidden;
}

.ero-bar-fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #4fc3f7, #ff9800, #f44336);
  border-radius: 3px;
  transition: width 0.5s ease;
}

.ero-val {
  color: #e8ecf4;
  font-weight: 600;
  width: 48px;
  text-align: right;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.center-col .chart-panel {
  width: 100%;
}

@media (max-width: 1400px) {
  .main-grid {
    grid-template-columns: 280px 1fr 320px;
  }
}
</style>
