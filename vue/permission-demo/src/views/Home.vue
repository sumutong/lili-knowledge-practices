<template>
  <div class="home">
    <h2>🏠 首页 - 公开页面</h2>
    <p>所有用户都可以访问此页面。</p>
    <div class="info-cards">
      <div class="info-card"><h4>权限控制方案</h4><p>基于路由守卫 + 角色校验实现页面级权限。</p></div>
      <div class="info-card"><h4>RBAC 模型</h4><p>用户 → 角色 → 权限，支持多角色分配。</p></div>
      <div class="info-card"><h4>指令级控制</h4><p>v-permission 指令控制按钮/组件显隐。</p></div>
    </div>
  </div>
</template>
<style scoped>
.home{padding:20px;background:#fff;border-radius:8px}
.info-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:20px}
.info-card{background:#f6f8fa;padding:20px;border-radius:8px}
.info-card h4{color:#333;margin-bottom:8px}
.info-card p{color:#666;font-size:14px}
</style>
