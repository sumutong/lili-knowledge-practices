<template>
  <button :class="['v-btn', `v-btn-${type}`]" :disabled="disabled" @click="$emit('click')">
    <slot />
  </button>
</template>
<script setup>
defineProps({ type: { type: String, default: 'default' }, disabled: Boolean })
defineEmits(['click'])
</script>
<style scoped>
.v-btn{padding:8px 22px;border:none;border-radius:6px;cursor:pointer;font-size:14px;transition:.2s;margin:0 6px 6px 0}
.v-btn-default{background:#f0f0f0;color:#333}.v-btn-default:hover{background:#e0e0e0}
.v-btn-primary{background:#1890ff;color:#fff}.v-btn-primary:hover{background:#40a9ff}
.v-btn-success{background:#52c41a;color:#fff}.v-btn-success:hover{background:#73d13d}
.v-btn-danger{background:#ff4d4f;color:#fff}.v-btn-danger:hover{background:#ff7875}
.v-btn:disabled{opacity:.5;cursor:not-allowed}
</style>
