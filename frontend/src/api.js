import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

export async function fetchStatus() {
  const { data } = await api.get('/status')
  return data
}

export async function fetchHeatmap() {
  const { data } = await api.get('/heatmap')
  return data
}

export async function fetchThickness() {
  const { data } = await api.get('/thickness')
  return data
}

export async function fetchLayerThickness(layerId) {
  const { data } = await api.get(`/thickness/layer/${layerId}`)
  return data
}

export async function fetchLayerTemperature(layerId) {
  const { data } = await api.get(`/temperature/layer/${layerId}`)
  return data
}

export default api
