<template>
  <div class="detail" v-if="product">
    <button class="back" @click="$router.back()">← 返回</button>
    <div class="detail-content">
      <div class="detail-img">{{ product.icon }}</div>
      <div class="detail-info">
        <h2>{{ product.name }}</h2>
        <div class="rating">⭐ {{ product.rating }} (128条评价)</div>
        <p class="price">¥{{ product.price }}</p>
        <p class="desc">{{ product.desc }}</p>
        <div class="specs">
          <span>品牌：VueShop</span><span>库存：有货</span><span>发货：24小时内</span>
        </div>
        <div class="actions">
          <button class="btn-cart" @click="add">加入购物车</button>
          <button class="btn-buy" @click="add;$router.push('/cart')">立即购买</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const emit = defineEmits(['addToCart'])

const products = [
  { id: 1, name: '无线蓝牙耳机', price: 299, rating: 4.8, icon: '🎧', desc: '主动降噪，续航30小时，Hi-Fi音质' },
  { id: 2, name: '智能手表Pro', price: 1299, rating: 4.6, icon: '⌚', desc: '心率血氧监测，GPS定位，50米防水' },
  { id: 3, name: '机械键盘RGB', price: 599, rating: 4.9, icon: '⌨️', desc: 'Cherry轴体，全键热插拔，RGB背光' },
  { id: 4, name: '4K显示器', price: 2899, rating: 4.7, icon: '🖥️', desc: '27英寸IPS，Type-C 65W反向充电' },
  { id: 5, name: '无线鼠标', price: 199, rating: 4.5, icon: '🖱️', desc: '人体工学设计，静音按键，双模连接' },
  { id: 6, name: '移动电源', price: 149, rating: 4.4, icon: '🔋', desc: '20000mAh大容量，65W快充' }
]

const product = computed(() => products.find(p => p.id === parseInt(route.params.id)))

function add() {
  emit('addToCart', product.value)
}
</script>

<style scoped>
.detail{max-width:900px;margin:0 auto;padding:20px}
.back{background:none;border:none;color:#666;cursor:pointer;font-size:15px;margin-bottom:20px}
.detail-content{display:flex;gap:40px;background:#fff;padding:40px;border-radius:12px}
.detail-img{font-size:140px;text-align:center;min-width:200px}
.detail-info{flex:1}
.detail-info h2{font-size:24px;margin-bottom:12px}
.price{color:#e74c3c;font-size:28px;font-weight:700;margin:16px 0}
.desc{color:#666;line-height:1.7;margin-bottom:16px}
.specs{display:flex;gap:16px;margin:16px 0;color:#888;font-size:13px}
.actions{display:flex;gap:12px;margin-top:20px}
.actions button{padding:12px 30px;border-radius:6px;font-size:16px;cursor:pointer;border:none}
.btn-cart{background:#fff;color:#e74c3c;border:2px solid #e74c3c !important}
.btn-buy{background:#e74c3c;color:#fff}
</style>
