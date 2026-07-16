import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Home from './views/Home.vue'
import Discover from './views/Discover.vue'
import Profile from './views/Profile.vue'

const routes = [
  { path: '/', component: Home },
  { path: '/discover', component: Discover },
  { path: '/profile', component: Profile }
]

const router = createRouter({ history: createWebHistory(), routes })
createApp(App).use(router).mount('#app')
