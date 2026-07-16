<template>
  <div><h2>👥 用户管理</h2>
    <div class="table-wrap"><table><thead><tr><th>ID</th><th>姓名</th><th>邮箱</th><th>角色</th><th>操作</th></tr></thead>
    <tbody><tr v-for="u in users" :key="u.id"><td>{{u.id}}</td><td>{{u.name}}</td><td>{{u.email}}</td><td><span class="tag tag-info">{{u.role}}</span></td><td><button class="btn-edit">编辑</button><button class="btn-del">删除</button></td></tr></tbody></table></div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
const users = reactive([
  {id:1,name:'张三',email:'zhang@example.com',role:'管理员'},
  {id:2,name:'李四',email:'li@example.com',role:'编辑'},
  {id:3,name:'王五',email:'wang@example.com',role:'用户'}
])
</script>

<style scoped>
.table-wrap{background:#fff;padding:24px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:12px;border-bottom:1px solid #f0f0f0}
.tag-info{background:#e6f7ff;color:#1890ff;border:1px solid #91d5ff;padding:2px 10px;border-radius:4px;font-size:12px}
button{padding:4px 12px;margin:0 4px;border:none;border-radius:4px;cursor:pointer;font-size:12px}
.btn-edit{background:#1890ff;color:#fff}
.btn-del{background:#ff4d4f;color:#fff}
</style>
