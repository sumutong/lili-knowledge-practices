import { createApp } from 'vue'
import { createI18n } from 'vue-i18n'
import App from './App.vue'
import zh from './locales/zh.json'
import en from './locales/en.json'

const i18n = createI18n({
  legacy: false,
  locale: 'zh',
  fallbackLocale: 'en',
  messages: { zh, en }
})

createApp(App).use(i18n).mount('#app')
