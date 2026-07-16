<template>
  <div class="app">
    <header class="top-header">
      <router-link to="/" class="logo">🛒 VueShop</router-link>
      <div class="header-right">
        <input v-model="searchQuery" placeholder="搜索商品..." class="search" />
        <router-link to="/cart" class="cart-btn">🛒 购物车 ({{ cartCount }})</router-link>
      </div>
    </header>
    <main><router-view :cart="cart" @add-to-cart="addToCart" /></main>
  </div>
</template>

<script setup>
import { ref, provide } from 'vue'

const cart = ref(JSON.parse(localStorage.getItem('ecart') || '[]'))
const cartCount = ref(cart.value.reduce((s, i) => s + i.qty, 0))
const searchQuery = ref('')

function addToCart(product) {
  const existing = cart.value.find(i => i.id === product.id)
  if (existing) { existing.qty++ } else { cart.value.push({ ...product, qty: 1 }) }
  cartCount.value = cart.value.reduce((s, i) => s + i.qty, 0)
  localStorage.setItem('ecart', JSON.stringify(cart.value))
}

provide('cart', cart)
</script>

<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif;background:#f5f5f5}
.top-header{display:flex;justify-content:space-between;align-items:center;background:#fff;padding:12px 24px;box-shadow:0 2px 8px rgba(0,0,0,.06);position:sticky;top:0;z-index:100}
.logo{font-size:22px;font-weight:700;color:#e74c3c;text-decoration:none}
.header-right{display:flex;gap:16px;align-items:center}
.search{padding:8px 16px;border:2px solid #eee;border-radius:20px;width:240px;font-size:14px}
.cart-btn{text-decoration:none;font-size:15px;color:#333}
</style>
