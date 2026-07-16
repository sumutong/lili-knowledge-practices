<template>
  <div class="cart-page">
    <h2>🛒 购物车</h2>
    <div v-if="cart.length === 0" class="empty">购物车是空的 <router-link to="/">去逛逛</router-link></div>
    <div v-else>
      <div class="cart-item" v-for="item in cart" :key="item.id">
        <span class="item-icon">{{ item.icon }}</span>
        <div class="item-info">
          <h4>{{ item.name }}</h4>
          <p>¥{{ item.price }} × {{ item.qty }}</p>
        </div>
        <div class="qty-ctrl">
          <button @click="changeQty(item, -1)">-</button>
          <span>{{ item.qty }}</span>
          <button @click="changeQty(item, 1)">+</button>
        </div>
        <span class="subtotal">¥{{ item.price * item.qty }}</span>
        <button class="btn-remove" @click="removeItem(item)">删除</button>
      </div>
      <div class="cart-footer">
        <span>合计: <strong>¥{{ total }}</strong></span>
        <button class="btn-checkout">去结算</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, computed } from 'vue'
const cart = inject('cart')
const total = computed(() => cart.value.reduce((s, i) => s + i.price * i.qty, 0))

function changeQty(item, delta) {
  item.qty += delta
  if (item.qty <= 0) removeItem(item)
  localStorage.setItem('ecart', JSON.stringify(cart.value))
}

function removeItem(item) {
  const idx = cart.value.indexOf(item)
  if (idx > -1) cart.value.splice(idx, 1)
  localStorage.setItem('ecart', JSON.stringify(cart.value))
}
</script>

<style scoped>
.cart-page{max-width:700px;margin:0 auto;padding:20px}
.empty{text-align:center;padding:60px;color:#999}
.empty a{color:#e74c3c}
.cart-item{display:flex;align-items:center;gap:16px;background:#fff;padding:16px 20px;border-radius:8px;margin-bottom:10px}
.item-icon{font-size:36px}
.item-info{flex:1}
.item-info p{color:#e74c3c;font-weight:600}
.qty-ctrl{display:flex;align-items:center;gap:8px}
.qty-ctrl button{width:28px;height:28px;border:1px solid #ddd;background:#fff;border-radius:4px;cursor:pointer;font-size:16px}
.subtotal{font-weight:700;min-width:80px;text-align:right}
.btn-remove{background:none;border:none;color:#999;cursor:pointer}
.cart-footer{display:flex;justify-content:space-between;align-items:center;background:#fff;padding:16px 20px;border-radius:8px;margin-top:16px}
.cart-footer strong{font-size:22px;color:#e74c3c}
.btn-checkout{background:#e74c3c;color:#fff;border:none;padding:12px 36px;border-radius:6px;font-size:16px;cursor:pointer}
</style>
