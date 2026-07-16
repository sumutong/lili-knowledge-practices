<template>
  <div class="home">
    <div class="banner"><h2>🔥 618年中大促</h2><p>全场低至5折，限时抢购</p></div>
    <div class="products">
      <div class="product-card" v-for="p in products" :key="p.id">
        <router-link :to="'/product/'+p.id">
          <div class="product-img">{{ p.icon }}</div>
          <h4>{{ p.name }}</h4>
        </router-link>
        <p class="price">¥{{ p.price }}</p>
        <div class="rating">⭐ {{ p.rating }}</div>
        <button @click="$emit('addToCart', p)">加入购物车</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
defineEmits(['addToCart'])
const products = reactive([
  { id: 1, name: '无线蓝牙耳机', price: 299, rating: 4.8, icon: '🎧', desc: '主动降噪，续航30小时，Hi-Fi音质' },
  { id: 2, name: '智能手表Pro', price: 1299, rating: 4.6, icon: '⌚', desc: '心率血氧监测，GPS定位，50米防水' },
  { id: 3, name: '机械键盘RGB', price: 599, rating: 4.9, icon: '⌨️', desc: 'Cherry轴体，全键热插拔，RGB背光' },
  { id: 4, name: '4K显示器', price: 2899, rating: 4.7, icon: '🖥️', desc: '27英寸IPS，Type-C 65W反向充电' },
  { id: 5, name: '无线鼠标', price: 199, rating: 4.5, icon: '🖱️', desc: '人体工学设计，静音按键，双模连接' },
  { id: 6, name: '移动电源', price: 149, rating: 4.4, icon: '🔋', desc: '20000mAh大容量，65W快充' }
])
</script>

<style scoped>
.banner{background:linear-gradient(135deg,#e74c3c,#f39c12);color:#fff;text-align:center;padding:40px 20px;border-radius:12px;margin:20px 0}
.banner h2{font-size:28px;margin-bottom:8px}
.products{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;max-width:960px;margin:0 auto;padding:0 20px 40px}
.product-card{background:#fff;border-radius:10px;padding:20px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.06);transition:.2s}
.product-card:hover{transform:translateY(-4px);box-shadow:0 6px 20px rgba(0,0,0,.1)}
.product-img{font-size:56px;margin-bottom:10px}
.product-card a{text-decoration:none;color:#333}
.product-card h4{margin:8px 0}
.price{color:#e74c3c;font-size:20px;font-weight:700;margin:8px 0}
.rating{color:#f39c12;font-size:13px;margin-bottom:10px}
.product-card button{background:#e74c3c;color:#fff;border:none;padding:8px 20px;border-radius:20px;cursor:pointer;font-size:14px;transition:.2s}
.product-card button:hover{background:#c0392b}
</style>
