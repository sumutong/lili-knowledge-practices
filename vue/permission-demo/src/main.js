import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, defineStore } from 'pinia'
import App from './App.vue'
import Home from './views/Home.vue'
import Admin from './views/Admin.vue'

// 权限 Store
const useAuthStore = defineStore('auth', {
  state: () => ({ user: null, role: null }),
  actions: {
    login(role) { this.role = role; this.user = { name: role === 'admin' ? '管理员' : '普通用户' } },
    logout() { this.user = null; this.role = null },
    hasPermission(route) {
      if (route.meta.roles && !route.meta.roles.includes(this.role)) return false
      return true
    }
  }
})

const routes = [
  { path: '/', component: Home },
  { path: '/admin', component: Admin, meta: { roles: ['admin'] } }
]

const router = createRouter({ history: createWebHistory(), routes })
const pinia = createPinia()

// 路由守卫
router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  if (to.meta.roles && !to.meta.roles.includes(auth.role)) {
    next('/')
  } else {
    next()
  }
})

createApp(App).use(router).use(pinia).mount('#app')
