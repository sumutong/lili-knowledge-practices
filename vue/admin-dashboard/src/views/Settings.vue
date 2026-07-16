<template>
  <div><h2>⚙️ 系统设置</h2>
    <div class="settings-form">
      <div class="form-item"><label>站点名称</label><input v-model="siteName" /></div>
      <div class="form-item"><label>主题色</label><input type="color" v-model="themeColor" /></div>
      <div class="form-item"><label>每页条数</label><select v-model="pageSize"><option>10</option><option>20</option><option>50</option></select></div>
      <button class="btn-save" @click="save">保存设置</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const siteName = ref('后台管理系统')
const themeColor = ref('#1890ff')
const pageSize = ref('20')
function save(){ alert('设置已保存!') }
</script>

<style scoped>
.settings-form{background:#fff;padding:24px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.06);max-width:500px}
.form-item{margin-bottom:16px}
.form-item label{display:block;margin-bottom:6px;font-weight:500}
input,select{width:100%;padding:8px 12px;border:1px solid #d9d9d9;border-radius:4px;font-size:14px}
.btn-save{background:#1890ff;color:#fff;border:none;padding:10px 30px;border-radius:4px;cursor:pointer;margin-top:10px}
</style>
