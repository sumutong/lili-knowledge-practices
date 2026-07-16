<template>
  <div class="app">
    <header class="header">
      <h1>📱 Vue3 PWA 实战</h1>
      <p>离线可用 · 消息推送 · 安装到桌面</p>
    </header>
    <main class="main">
      <div class="card" v-for="item in items" :key="item.id">
        <h3>{{ item.title }}</h3>
        <p>{{ item.body }}</p>
      </div>
    </main>
    <footer>
      <div class="status">
        <span class="dot" :class="{ online: isOnline }"></span>
        {{ isOnline ? '在线' : '离线模式' }}
      </div>
      <button @click="addNotification">🔔 发送通知</button>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const items = ref([])
const isOnline = ref(navigator.onLine)

// 模拟 API 数据 (会被 Service Worker 缓存)
const mockData = [
  { id: 1, title: 'PWA 核心特性', body: 'Service Worker 实现离线缓存，NetworkFirst 策略优先网络请求' },
  { id: 2, title: 'Web App Manifest', body: '配置 manifest.json 让应用可安装到桌面，全屏体验' },
  { id: 3, title: '消息推送', body: '通过 Notification API 实现本地消息推送通知' },
  { id: 4, title: '缓存策略', body: 'Workbox 运行时缓存，API 数据自动缓存 24 小时' }
]

onMounted(() => {
  items.value = mockData
  window.addEventListener('online', () => isOnline.value = true)
  window.addEventListener('offline', () => isOnline.value = false)
})

function addNotification() {
  if (Notification.permission === 'granted') {
    new Notification('PWA 通知', { body: '你有一条新消息!', icon: '/vite.svg' })
  } else {
    Notification.requestPermission()
  }
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: system-ui, sans-serif; background: #f0f2f5; }
.app { max-width: 600px; margin: 0 auto; padding: 20px; }
.header { text-align: center; padding: 30px 0; }
.header h1 { color: #42b883; font-size: 28px; }
.header p { color: #666; margin-top: 8px; }
.card { background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 14px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.card h3 { color: #333; margin-bottom: 8px; }
.card p { color: #666; line-height: 1.6; }
footer { display: flex; justify-content: space-between; align-items: center; margin-top: 20px; }
.status { display: flex; align-items: center; gap: 8px; }
.dot { width: 10px; height: 10px; border-radius: 50%; background: #ccc; }
.dot.online { background: #42b883; }
button { background: #42b883; color: #fff; border: none; padding: 10px 22px; border-radius: 8px; cursor: pointer; font-size: 15px; }
button:hover { background: #35a372; }
</style>
