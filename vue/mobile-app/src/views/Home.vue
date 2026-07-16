<template>
  <div class="home">
    <div class="swiper">🔥 Vue3移动端实战项目</div>
    <div class="grid-menu">
      <div class="menu-item" v-for="m in menus" :key="m.name">
        <span class="menu-icon">{{ m.icon }}</span>
        <span>{{ m.name }}</span>
      </div>
    </div>
    <div class="feed">
      <div class="feed-item" v-for="item in feeds" :key="item.id">
        <img :src="item.avatar" class="avatar" />
        <div class="feed-body">
          <h4>{{ item.user }}</h4>
          <p>{{ item.content }}</p>
          <div class="feed-actions">
            <span>❤️ {{ item.likes }}</span><span>💬 {{ item.comments }}</span><span>↗️ 分享</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
const menus = reactive([
  { name: '美食', icon: '🍔' }, { name: '电影', icon: '🎬' }, { name: '酒店', icon: '🏨' },
  { name: '景点', icon: '🏔️' }, { name: '外卖', icon: '🛵' }, { name: '打车', icon: '🚕' },
  { name: '超市', icon: '🏪' }, { name: '更多', icon: '⋯' }
])
const feeds = reactive([
  { id: 1, user: '小明', avatar: '😊', content: '今天天气真好，出去爬山了!', likes: 128, comments: 23 },
  { id: 2, user: '小红', avatar: '😍', content: '新买的口红💄超好看！', likes: 256, comments: 45 },
  { id: 3, user: '技术宅', avatar: '🤓', content: 'Vue3 + Vite 开发体验真棒!', likes: 89, comments: 12 }
])
</script>

<style scoped>
.swiper{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:24px;text-align:center;font-size:18px;border-radius:0 0 16px 16px}
.grid-menu{display:grid;grid-template-columns:repeat(4,1fr);padding:20px 16px;gap:16px}
.menu-item{display:flex;flex-direction:column;align-items:center;gap:6px;font-size:13px;color:#333}
.menu-icon{font-size:30px}
.feed{padding:0 16px}
.feed-item{display:flex;gap:12px;padding:16px 0;border-bottom:1px solid #f0f0f0}
.avatar{font-size:36px;width:40px;text-align:center}
.feed-body{flex:1}
.feed-body h4{font-size:15px;margin-bottom:4px}
.feed-body p{font-size:14px;color:#333;line-height:1.5}
.feed-actions{display:flex;gap:20px;margin-top:10px;font-size:12px;color:#999}
</style>
