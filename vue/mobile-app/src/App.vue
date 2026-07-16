<template>
  <div class="mobile-app">
    <div class="status-bar">9:41</div>
    <header class="nav-bar">
      <h1>Vue Mobile</h1>
    </header>
    <main class="main-content">
      <router-view />
    </main>
    <nav class="tab-bar">
      <router-link to="/" class="tab-item">
        <span class="tab-icon">🏠</span><span>首页</span>
      </router-link>
      <router-link to="/discover" class="tab-item">
        <span class="tab-icon">🔍</span><span>发现</span>
      </router-link>
      <router-link to="/profile" class="tab-item">
        <span class="tab-icon">👤</span><span>我的</span>
      </router-link>
    </nav>
  </div>
</template>

<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f5;max-width:414px;margin:0 auto;min-height:100vh}
.mobile-app{display:flex;flex-direction:column;min-height:100vh;background:#fff;position:relative}
.status-bar{padding:8px 16px;background:#fff;font-size:12px;text-align:center}
.nav-bar{padding:12px 16px;background:#fff;border-bottom:1px solid #f0f0f0;text-align:center}
.nav-bar h1{font-size:17px;font-weight:600}
.main-content{flex:1;overflow-y:auto;padding-bottom:60px}
.tab-bar{position:fixed;bottom:0;width:100%;max-width:414px;display:flex;background:#fff;border-top:1px solid #eee;padding:6px 0 env(safe-area-inset-bottom)}
.tab-item{flex:1;display:flex;flex-direction:column;align-items:center;text-decoration:none;color:#999;padding:4px 0;font-size:10px;transition:.2s}
.tab-item.router-link-active{color:#007aff}
.tab-icon{font-size:22px;margin-bottom:2px}
</style>
