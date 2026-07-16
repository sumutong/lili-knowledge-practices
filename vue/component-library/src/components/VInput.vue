<template>
  <input :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" :placeholder="placeholder" class="v-input" />
</template>
<script setup>
defineProps({ modelValue: String, placeholder: String })
defineEmits(['update:modelValue'])
</script>
<style scoped>
.v-input{width:100%;padding:10px 14px;border:2px solid #e0e0e0;border-radius:6px;font-size:14px;transition:.2s;outline:none}
.v-input:focus{border-color:#1890ff}
</style>
