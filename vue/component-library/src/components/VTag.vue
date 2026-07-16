<template>
  <span :class="['v-tag', `v-tag-${type}`]"><slot /></span>
</template>
<script setup>
defineProps({ type: { type: String, default: 'default' } })
</script>
<style scoped>
.v-tag{display:inline-block;padding:2px 12px;border-radius:4px;font-size:12px;margin:2px 4px}
.v-tag-default{background:#f0f0f0;color:#666}
.v-tag-success{background:#f6ffed;color:#52c41a;border:1px solid #b7eb8f}
.v-tag-warning{background:#fffbe6;color:#faad14;border:1px solid #ffe58f}
.v-tag-danger{background:#fff2f0;color:#ff4d4f;border:1px solid #ffccc7}
</style>
