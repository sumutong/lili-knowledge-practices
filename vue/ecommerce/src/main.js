import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Home from './views/Home.vue'
import ProductDetail from './views/ProductDetail.vue'
import Cart from './views/Cart.vue'

const routes = [
  { path: '/', component: Home },
  { path: '/product/:id', component: ProductDetail },
  { path: '/cart', component: Cart }
]

const router = createRouter({ history: createWebHistory(), routes })
createApp(App).use(router).mount('#app')
