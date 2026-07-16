<template>
  <div class="app">
    <header class="lib-header">
      <h1>🧩 Vue3 组件库实战</h1>
      <p>从零构建企业级 UI 组件库</p>
    </header>
    <section class="section">
      <h2>Button 按钮</h2>
      <VButton type="primary">主要按钮</VButton>
      <VButton type="success">成功按钮</VButton>
      <VButton type="danger">危险按钮</VButton>
      <VButton type="default" disabled>禁用按钮</VButton>
    </section>
    <section class="section">
      <h2>Modal 弹窗</h2>
      <VButton type="primary" @click="showModal = true">打开弹窗</VButton>
      <VModal v-if="showModal" title="提示" @close="showModal = false">
        <p>这是一个可复用的弹窗组件。</p>
      </VModal>
    </section>
    <section class="section">
      <h2>Input 输入框</h2>
      <VInput v-model="inputVal" placeholder="请输入内容" />
      <p class="preview">实时预览: {{ inputVal }}</p>
    </section>
    <section class="section">
      <h2>Card 卡片</h2>
      <VCard title="组件化开发">
        <p>通过封装可复用组件，提高开发效率和代码质量。</p>
        <template #footer><VButton type="primary">了解更多</VButton></template>
      </VCard>
    </section>
    <section class="section">
      <h2>Tag 标签</h2>
      <VTag type="success">已完成</VTag>
      <VTag type="warning">处理中</VTag>
      <VTag type="danger">已取消</VTag>
      <VTag>默认</VTag>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import VButton from './components/VButton.vue'
import VModal from './components/VModal.vue'
import VInput from './components/VInput.vue'
import VCard from './components/VCard.vue'
import VTag from './components/VTag.vue'

const showModal = ref(false)
const inputVal = ref('')
</script>

<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif;background:#f8f9fa}
.app{max-width:800px;margin:0 auto;padding:24px}
.lib-header{text-align:center;padding:30px 0;border-bottom:2px solid #e9ecef;margin-bottom:30px}
.lib-header h1{font-size:28px;color:#333}.lib-header p{color:#666;margin-top:8px}
.section{padding:24px;background:#fff;border-radius:10px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,.04)}
.section h2{font-size:18px;margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid #f0f0f0}
.preview{color:#666;font-size:13px;margin-top:8px}
</style>
