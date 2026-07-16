<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="logo">🏢 后台管理</div>
      <nav>
        <router-link to="/">📊 仪表盘</router-link>
        <router-link to="/users">👥 用户管理</router-link>
        <router-link to="/settings">⚙️ 系统设置</router-link>
      </nav>
    </aside>
    <main class="content">
      <header class="topbar">
        <span>管理员</span>
      </header>
      <div class="page"><router-view /></div>
    </main>
  </div>
</template>

<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif;background:#f0f2f5}
.layout{display:flex;min-height:100vh}
.sidebar{width:220px;background:#001529;color:#fff;padding:20px 0}
.sidebar .logo{padding:0 20px 20px;font-size:18px;font-weight:700;border-bottom:1px solid #002140}
.sidebar nav{display:flex;flex-direction:column;padding:10px 0}
.sidebar a{color:#ffffffb3;padding:12px 20px;text-decoration:none;transition:.2s}
.sidebar a:hover,.sidebar a.router-link-active{color:#fff;background:#1890ff}
.content{flex:1;display:flex;flex-direction:column}
.topbar{background:#fff;padding:14px 24px;text-align:right;border-bottom:1px solid #e8e8e8}
.page{padding:24px}
</style>
