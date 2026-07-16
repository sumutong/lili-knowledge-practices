<template>
  <div class="discover">
    <div class="search-bar">🔍 搜索感兴趣的内容</div>
    <div class="topic-list">
      <div class="topic-card" v-for="t in topics" :key="t.id">
        <h4>{{ t.title }}</h4>
        <p>{{ t.desc }}</p>
        <span class="hot">{{ t.heat }}热度</span>
      </div>
    </div>
  </div>
</template>
<script setup>
import { reactive } from 'vue'
const topics = reactive([
  { id: 1, title: '# Vue3最佳实践', desc: '300篇讨论', heat: '8.2w' },
  { id: 2, title: '# 前端开发趋势', desc: '200篇讨论', heat: '5.6w' },
  { id: 3, title: '# AI与编程', desc: '450篇讨论', heat: '12w' }
])
</script>
<style scoped>
.discover{padding:16px}
.search-bar{background:#f0f0f0;padding:12px 16px;border-radius:20px;color:#999;font-size:14px;margin-bottom:16px}
.topic-card{background:#fff;padding:16px;border-radius:10px;margin-bottom:10px;box-shadow:0 1px 4px rgba(0,0,0,.04)}
.topic-card h4{font-size:16px;margin-bottom:6px}
.topic-card p{color:#999;font-size:13px}
.hot{color:#e74c3c;font-size:12px;margin-top:4px;display:block}
</style>
