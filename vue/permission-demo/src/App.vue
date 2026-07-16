<template>
  <div class="app">
    <header>
      <h1>🔐 权限管理实战</h1>
      <div class="auth-bar">
        <span v-if="auth.user">{{ auth.user.name }} ({{ auth.role }}) <button @click="auth.logout">退出</button></span>
        <select v-else v-model="selectedRole"><option value="">选择角色</option><option value="admin">管理员</option><option value="user">普通用户</option></select>
        <button v-if="!auth.user" @click="auth.login(selectedRole)" :disabled="!selectedRole">登录</button>
      </div>
    </header>
    <nav>
      <router-link to="/">🏠 首页</router-link>
      <router-link to="/admin" v-if="auth.role==='admin'">⚙️ 管理后台</router-link>
    </nav>
    <main><router-view /></main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from './main.js'  // actually from store, but using inline
const auth = useAuthStore()
const selectedRole = ref('')
</script>

<script>
import { defineStore } from 'pinia'
export const useAuthStore = defineStore('auth', {
  state: () => ({ user: null, role: null }),
  actions: {
    login(role) { this.role = role; this.user = { name: role === 'admin' ? '管理员' : '普通用户' } },
    logout() { this.user = null; this.role = null },
    hasPermission(route) { return !route.meta.roles || route.meta.roles.includes(this.role) }
  }
})
</script>

<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif;background:#f0f2f5}
.app{max-width:700px;margin:0 auto;padding:20px}
header{display:flex;justify-content:space-between;align-items:center;padding:16px 0}
.auth-bar{display:flex;gap:8px;align-items:center}
.auth-bar select{padding:6px 12px;border:1px solid #ddd;border-radius:4px}
.auth-bar button{padding:6px 16px;background:#1890ff;color:#fff;border:none;border-radius:4px;cursor:pointer}
.auth-bar button:disabled{opacity:.5}
nav{display:flex;gap:10px;background:#fff;padding:12px 20px;border-radius:8px;margin-bottom:20px}
nav a{text-decoration:none;color:#555;padding:6px 14px}
nav a.router-link-active{color:#1890ff;font-weight:600}
</style>
