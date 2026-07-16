<template>
  <div class="app">
    <header>
      <h1>{{ t('app.title') }}</h1>
      <p>{{ t('app.subtitle') }}</p>
      <div class="lang-switch">
        <button :class="{ active: locale==='zh' }" @click="setLocale('zh')">中文</button>
        <button :class="{ active: locale==='en' }" @click="setLocale('en')">English</button>
      </div>
    </header>
    <nav>
      <a href="#">{{ t('nav.home') }}</a>
      <a href="#">{{ t('nav.about') }}</a>
      <a href="#">{{ t('nav.products') }}</a>
    </nav>
    <main>
      <div class="hero">
        <h2>{{ t('home.welcome') }}</h2>
        <p>{{ t('home.description') }}</p>
      </div>
      <h3>{{ t('product.title') }}</h3>
      <div class="products">
        <div class="product-card" v-for="p in products" :key="p.id">
          <img :src="p.image" :alt="locale==='zh'?p.nameZh:p.nameEn" />
          <h4>{{ locale==='zh'?p.nameZh:p.nameEn }}</h4>
          <p>¥{{ p.price }}</p>
          <button>{{ t('product.addToCart') }}</button>
        </div>
      </div>
    </main>
    <footer>{{ t('footer.copyright') }}</footer>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
const { t, locale } = useI18n()

function setLocale(lang) { locale.value = lang }

const products = [
  { id: 1, nameZh: '无线耳机', nameEn: 'Wireless Earbuds', price: 299, image: '🎧' },
  { id: 2, nameZh: '智能手表', nameEn: 'Smart Watch', price: 1299, image: '⌚' },
  { id: 3, nameZh: '机械键盘', nameEn: 'Mechanical Keyboard', price: 599, image: '⌨️' }
]
</script>

<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif;background:#f5f5f5}
.app{max-width:800px;margin:0 auto;padding:20px}
header{text-align:center;padding:30px 0}
header h1{font-size:30px;color:#333}header p{color:#666;margin-top:8px}
.lang-switch{margin-top:16px}
.lang-switch button{padding:6px 20px;margin:0 4px;border:2px solid #ddd;background:#fff;border-radius:6px;cursor:pointer;font-size:14px;transition:.2s}
.lang-switch button.active{background:#42b883;color:#fff;border-color:#42b883}
nav{display:flex;gap:10px;background:#fff;padding:12px 20px;border-radius:8px;margin-bottom:20px;box-shadow:0 1px 4px rgba(0,0,0,.05)}
nav a{text-decoration:none;color:#555;padding:6px 14px}
.hero{text-align:center;padding:40px 20px;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border-radius:12px;margin-bottom:24px}
.hero h2{font-size:26px;margin-bottom:12px}
.products{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.product-card{background:#fff;padding:20px;border-radius:10px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.product-card img{font-size:48px}
.product-card h4{margin:12px 0 6px}
.product-card p{color:#e74c3c;font-weight:700;margin-bottom:10px}
.product-card button{background:#42b883;color:#fff;border:none;padding:8px 20px;border-radius:6px;cursor:pointer}
footer{text-align:center;padding:24px;color:#999;margin-top:30px}
</style>
