<template>
  <div class="admin">
    <h2>⚙️ 管理后台 - 仅管理员</h2>
    <p>此页面仅管理员角色可访问。</p>
    <div class="admin-actions">
      <div class="action-card">
        <h4>用户管理</h4>
        <p>增删改查用户账号</p>
        <button>进入</button>
      </div>
      <div class="action-card">
        <h4>角色管理</h4>
        <p>配置角色与权限映射</p>
        <button>进入</button>
      </div>
      <div class="action-card">
        <h4>系统日志</h4>
        <p>查看操作审计日志</p>
        <button>进入</button>
      </div>
    </div>
  </div>
</template>
<style scoped>
.admin{padding:20px;background:#fff;border-radius:8px}
.admin-actions{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:20px}
.action-card{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:24px;border-radius:10px}
.action-card h4{font-size:18px;margin-bottom:8px}
.action-card p{opacity:.9;margin-bottom:12px;font-size:14px}
.action-card button{background:#fff;color:#667eea;border:none;padding:8px 24px;border-radius:6px;cursor:pointer;font-weight:600}
</style>
