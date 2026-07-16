<template>
  <div class="v-card">
    <div class="v-card-title" v-if="title">{{ title }}</div>
    <div class="v-card-body"><slot /></div>
    <div class="v-card-footer" v-if="$slots.footer"><slot name="footer" /></div>
  </div>
</template>
<script setup>
defineProps({ title: String })
</script>
<style scoped>
.v-card{border:1px solid #e8e8e8;border-radius:8px;overflow:hidden;max-width:400px}
.v-card-title{padding:14px 20px;font-weight:600;background:#fafafa;border-bottom:1px solid #f0f0f0}
.v-card-body{padding:20px;line-height:1.6}
.v-card-footer{padding:12px 20px;border-top:1px solid #f0f0f0;background:#fafafa}
</style>
