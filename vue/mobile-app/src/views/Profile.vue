<template>
  <div class="profile">
    <div class="user-card">
      <div class="avatar">😎</div>
      <h3>用户昵称</h3>
      <p>Vue3 移动端开发实战</p>
    </div>
    <div class="stats">
      <div><strong>128</strong>关注</div><div><strong>368</strong>粉丝</div><div><strong>56</strong>动态</div>
    </div>
    <div class="menu-list">
      <div class="menu-row" v-for="m in menus" :key="m">📋 {{ m }} <span>→</span></div>
    </div>
  </div>
</template>
<script setup>
const menus = ['我的订单', '我的收藏', '浏览记录', '设置', '关于我们']
</script>
<style scoped>
.profile{padding:20px 16px}
.user-card{text-align:center;padding:20px 0}
.avatar{font-size:64px;margin-bottom:12px}
.user-card h3{font-size:20px;margin-bottom:4px}
.user-card p{color:#999;font-size:13px}
.stats{display:flex;justify-content:space-around;padding:16px 0;border-top:1px solid #f0f0f0;border-bottom:1px solid #f0f0f0}
.stats div{text-align:center;font-size:14px}
.stats strong{display:block;font-size:18px;color:#333}
.menu-list{margin-top:16px}
.menu-row{padding:14px 0;display:flex;justify-content:space-between;border-bottom:1px solid #f5f5f5;font-size:15px;cursor:pointer}
.menu-row span{color:#ccc}
</style>
