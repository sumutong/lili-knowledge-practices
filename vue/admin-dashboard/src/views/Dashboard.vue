<template>
  <div class="dashboard">
    <h2>📊 仪表盘</h2>
    <div class="stats">
      <div class="stat-card" v-for="s in stats" :key="s.label">
        <div class="stat-value">{{ s.value }}</div>
        <div class="stat-label">{{ s.label }}</div>
      </div>
    </div>
    <div class="chart-area">
      <h3>最近订单</h3>
      <table><thead><tr><th>订单号</th><th>客户</th><th>金额</th><th>状态</th></tr></thead>
      <tbody><tr v-for="o in orders" :key="o.id"><td>{{o.id}}</td><td>{{o.customer}}</td><td>¥{{o.amount}}</td><td><span :class="'tag tag-'+(o.status==='已完成'?'success':'warning')">{{o.status}}</span></td></tr></tbody></table>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
const stats = reactive([
  { label: '总用户', value: '12,846' },
  { label: '今日订单', value: '342' },
  { label: '营收', value: '¥58,420' },
  { label: '转化率', value: '8.6%' }
])
const orders = reactive([
  { id:'ORD-001',customer:'张三',amount:'1,280',status:'已完成'},
  { id:'ORD-002',customer:'李四',amount:'3,560',status:'处理中'},
  { id:'ORD-003',customer:'王五',amount:'890',status:'已完成'},
  { id:'ORD-004',customer:'赵六',amount:'2,150',status:'已取消'}
])
</script>

<style scoped>
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0}
.stat-card{background:#fff;padding:24px;border-radius:8px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.stat-value{font-size:28px;font-weight:700;color:#1890ff}
.stat-label{color:#666;margin-top:8px}
.chart-area{background:#fff;padding:24px;border-radius:8px;margin-top:20px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
table{width:100%;border-collapse:collapse;margin-top:16px}
th,td{text-align:left;padding:12px;border-bottom:1px solid #f0f0f0}
.tag{padding:2px 10px;border-radius:4px;font-size:12px}
.tag-success{background:#f6ffed;color:#52c41a;border:1px solid #b7eb8f}
.tag-warning{background:#fffbe6;color:#faad14;border:1px solid #ffe58f}
</style>
