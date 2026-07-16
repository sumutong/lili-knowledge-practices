<template>
  <div class="dashboard">
    <header class="dash-header">
      <h1>📊 数据可视化大屏</h1>
      <div class="time">{{ currentTime }}</div>
    </header>
    <div class="grid">
      <div class="card"><h3>实时访问量</h3><div ref="chart1" class="chart"></div></div>
      <div class="card"><h3>用户分布</h3><div ref="chart2" class="chart"></div></div>
      <div class="card"><h3>销售额趋势</h3><div ref="chart3" class="chart"></div></div>
      <div class="card"><h3>订单状态</h3><div ref="chart4" class="chart"></div></div>
      <div class="card span2"><h3>全国销售热力图</h3><div ref="chart5" class="chart"></div></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const chart1 = ref(null), chart2 = ref(null), chart3 = ref(null), chart4 = ref(null), chart5 = ref(null)
const currentTime = ref('')
let charts = []

onMounted(() => {
  // 时间更新
  setInterval(() => { currentTime.value = new Date().toLocaleString('zh-CN') }, 1000)

  // 图表1 - 折线图
  const c1 = echarts.init(chart1.value)
  c1.setOption({
    tooltip: {}, grid: { top: 10, right: 10, bottom: 20, left: 40 },
    xAxis: { data: ['00:00','02:00','04:00','06:00','08:00','10:00','12:00'] },
    yAxis: {}, series: [{ name: 'PV', type: 'line', data: [120,200,150,280,450,620,580], smooth: true, areaStyle: { color: '#42b88333' } }]
  })
  charts.push(c1)

  // 图表2 - 饼图
  const c2 = echarts.init(chart2.value)
  c2.setOption({
    tooltip: {}, series: [{ type: 'pie', radius: ['40%','70%'], data: [{value:335,name:'北京'},{value:310,name:'上海'},{value:234,name:'广州'},{value:135,name:'深圳'},{value:548,name:'其他'}] }]
  })
  charts.push(c2)

  // 图表3 - 柱状图
  const c3 = echarts.init(chart3.value)
  c3.setOption({
    tooltip: {}, grid: { top: 10, right: 10, bottom: 20, left: 50 },
    xAxis: { data: ['周一','周二','周三','周四','周五','周六','周日'] },
    yAxis: {}, series: [{ type: 'bar', data: [12,18,15,22,25,30,20], itemStyle: { color: '#667eea' } }]
  })
  charts.push(c3)

  // 图表4 - 仪表盘
  const c4 = echarts.init(chart4.value)
  c4.setOption({
    series: [{ type: 'gauge', detail: { formatter: '{value}%' }, data: [{ value: 85, name: '完成率' }] }]
  })
  charts.push(c4)

  // 图表5 - 中国地图散点
  const c5 = echarts.init(chart5.value)
  c5.setOption({
    tooltip: {}, grid: { top: 10, right: 20, bottom: 20, left: 60 },
    xAxis: { name: '经度' }, yAxis: { name: '纬度' },
    series: [{
      type: 'scatter', symbolSize: 20,
      data: [[116.4,39.9],[121.5,31.2],[113.3,23.1],[114.1,22.5],[120.2,30.3]],
      itemStyle: { color: '#e74c3c' }
    }]
  })
  charts.push(c5)
})

onBeforeUnmount(() => charts.forEach(c => c.dispose()))
</script>

<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif;background:#0a1628;color:#fff}
.dashboard{padding:16px;min-height:100vh}
.dash-header{display:flex;justify-content:space-between;align-items:center;padding:20px 0}
.dash-header h1{font-size:26px;background:linear-gradient(90deg,#42b883,#667eea);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.time{font-size:16px;color:#8899aa}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
.card{background:#0d2137;border-radius:10px;padding:16px;border:1px solid #1a3a5c}
.card h3{font-size:15px;margin-bottom:10px;color:#8899aa}
.chart{width:100%;height:260px}
.span2{grid-column:span 2}
</style>
