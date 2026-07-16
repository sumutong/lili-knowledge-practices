import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia } from 'pinia'
import App from './App.vue'
import Dashboard from './views/Dashboard.vue'
import Users from './views/Users.vue'
import Settings from './views/Settings.vue'

const routes = [
  { path: '/', component: Dashboard, meta: { title: '仪表盘' } },
  { path: '/users', component: Users, meta: { title: '用户管理' } },
  { path: '/settings', component: Settings, meta: { title: '系统设置' } }
]

const router = createRouter({ history: createWebHistory(), routes })
const pinia = createPinia()

createApp(App).use(router).use(pinia).mount('#app')
