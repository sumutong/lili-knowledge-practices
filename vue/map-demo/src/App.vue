<template>
  <div class="app">
    <header><h1>🗺️ Vue3 地图实战</h1><p>基于 Leaflet 的交互式地图应用</p></header>
    <div class="map-toolbar">
      <button @click="addMarker">📍 添加标记</button>
      <button @click="clearMarkers">🗑️ 清除标记</button>
      <button @click="locateMe">🎯 我的位置</button>
      <span class="info">标记数: {{ markerCount }}</span>
    </div>
    <div ref="mapContainer" class="map-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import L from 'leaflet'

const mapContainer = ref(null)
const markerCount = ref(0)
let map = null
let markers = []

onMounted(() => {
  map = L.map(mapContainer.value).setView([39.9042, 116.4074], 12)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
  }).addTo(map)

  // 预设标记点
  const spots = [
    { name: '天安门', lat: 39.9087, lng: 116.3975 },
    { name: '故宫', lat: 39.9163, lng: 116.3972 },
    { name: '王府井', lat: 39.9138, lng: 116.4106 }
  ]
  spots.forEach(s => {
    const m = L.marker([s.lat, s.lng]).addTo(map).bindPopup(`<b>${s.name}</b>`)
    markers.push(m)
  })
  markerCount.value = markers.length
})

function addMarker() {
  const center = map.getCenter()
  const m = L.marker([center.lat, center.lng]).addTo(map).bindPopup(`标记点 ${markers.length + 1}`)
  markers.push(m)
  markerCount.value = markers.length
}

function clearMarkers() {
  markers.forEach(m => map.removeLayer(m))
  markers = []
  markerCount.value = 0
}

function locateMe() {
  map.locate({ setView: true, maxZoom: 16 })
  map.on('locationfound', e => {
    L.marker(e.latlng).addTo(map).bindPopup('你在这里').openPopup()
    L.circle(e.latlng, { radius: e.accuracy / 2 }).addTo(map)
  })
}
</script>

<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif}
.app{display:flex;flex-direction:column;height:100vh}
header{text-align:center;padding:16px;background:#2c3e50;color:#fff}
header h1{font-size:22px}header p{font-size:13px;opacity:.8;margin-top:4px}
.map-toolbar{display:flex;gap:10px;padding:10px 16px;background:#fff;border-bottom:1px solid #eee;align-items:center}
.map-toolbar button{padding:6px 16px;background:#42b883;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px}
.map-toolbar button:hover{background:#35a372}
.info{color:#666;font-size:13px}
.map-container{flex:1}
</style>
