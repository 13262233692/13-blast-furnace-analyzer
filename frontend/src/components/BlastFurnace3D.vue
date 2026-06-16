<template>
  <div class="chart-panel furnace-3d-panel">
    <div class="chart-title">
      高炉 3D 数字孪生模型
      <span class="subtitle">（拖动旋转 · 滚轮缩放 · 自动旋转中）</span>
    </div>
    <div ref="containerRef" class="furnace-3d-container"></div>
    <div class="furnace-legend">
      <div class="legend-item">
        <span class="legend-color" style="background: #267326"></span>
        <span>轻微侵蚀</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #f2d133"></span>
        <span>中度侵蚀</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #ff591a"></span>
        <span>严重侵蚀</span>
      </div>
      <div class="legend-item">
        <span class="legend-color glow"></span>
        <span>发红发亮损伤区</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { createFurnaceScene } from '../utils/furnace3d.js'

const props = defineProps({
  thicknessMap: { type: Array, default: () => [] }
})

const containerRef = ref(null)
let furnace3d = null

onMounted(() => {
  if (!containerRef.value) return
  furnace3d = createFurnaceScene(containerRef.value)

  if (props.thicknessMap && props.thicknessMap.length > 0) {
    furnace3d.updateErosionMap(props.thicknessMap)
  }
})

onUnmounted(() => {
  if (furnace3d) {
    furnace3d.destroy()
    furnace3d = null
  }
})

watch(() => props.thicknessMap, (newMap) => {
  if (furnace3d && newMap && newMap.length > 0) {
    furnace3d.updateErosionMap(newMap)
  }
}, { deep: true })
</script>

<style scoped>
.furnace-3d-panel {
  position: relative;
}

.furnace-3d-container {
  flex: 1;
  min-height: 420px;
  width: 100%;
  border-radius: 6px;
  overflow: hidden;
}

.subtitle {
  font-size: 11px;
  color: #8892b0;
  font-weight: normal;
  margin-left: 10px;
  letter-spacing: 0;
}

.furnace-legend {
  position: absolute;
  bottom: 20px;
  left: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: rgba(10, 14, 39, 0.75);
  padding: 10px 14px;
  border-radius: 6px;
  border: 1px solid rgba(30, 42, 90, 0.6);
  backdrop-filter: blur(4px);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #b0b8d4;
}

.legend-color {
  display: inline-block;
  width: 18px;
  height: 10px;
  border-radius: 2px;
}

.legend-color.glow {
  background: #ff3d00;
  box-shadow: 0 0 10px #ff6600, 0 0 20px #ff3d00;
}
</style>
