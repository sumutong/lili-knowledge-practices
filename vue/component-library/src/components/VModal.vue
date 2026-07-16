<template>
  <div class="v-modal-overlay" @click.self="$emit('close')">
    <div class="v-modal">
      <div class="v-modal-header">
        <h3>{{ title }}</h3>
        <button class="v-modal-close" @click="$emit('close')">✕</button>
      </div>
      <div class="v-modal-body"><slot /></div>
      <div class="v-modal-footer"><slot name="footer" /></div>
    </div>
  </div>
</template>
<script setup>
defineProps({ title: String })
defineEmits(['close'])
</script>
<style scoped>
.v-modal-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:1000}
.v-modal{background:#fff;border-radius:10px;width:90%;max-width:460px;box-shadow:0 10px 40px rgba(0,0,0,.2)}
.v-modal-header{display:flex;justify-content:space-between;align-items:center;padding:16px 20px;border-bottom:1px solid #f0f0f0}
.v-modal-header h3{margin:0;font-size:16px}
.v-modal-close{background:none;border:none;font-size:18px;cursor:pointer;color:#999}
.v-modal-body{padding:20px;line-height:1.6}
.v-modal-footer{padding:12px 20px;border-top:1px solid #f0f0f0;display:flex;justify-content:flex-end;gap:8px}
</style>
