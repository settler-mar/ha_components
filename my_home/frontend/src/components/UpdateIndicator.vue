<template>
  <div 
    class="update-indicator"
    :class="{ 'visible': isVisible, 'hidden': !isVisible }"
    :title="title"
  ></div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  duration: {
    type: Number,
    default: 1000
  },
  title: {
    type: String,
    default: 'Обновлено'
  }
})

const isVisible = ref(false)
let timer = null

// Функция для сброса таймера
const resetTimer = () => {
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
}

// Функция для показа индикатора
const showIndicator = () => {
  resetTimer()
  isVisible.value = true
  
  timer = setTimeout(() => {
    isVisible.value = false
    timer = null
  }, props.duration)
}

// Следим за изменениями props.show
watch(() => props.show, (newValue) => {
  if (newValue) {
    showIndicator()
  }
}, { immediate: true })

// Очищаем таймер при размонтировании
import { onUnmounted } from 'vue'
onUnmounted(() => {
  resetTimer()
})
</script>

<style scoped>
.update-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #4caf50;
  display: inline-block;
  vertical-align: baseline;
  margin-top: 2px;
  transition: all 0.3s ease-in-out;
  opacity: 0;
  transform: scale(0.5);
  position: absolute;
  top: 0;
  left: 0;
}

.update-indicator.visible {
  opacity: 1;
  transform: scale(1);
  animation: pulse 0.3s ease-in-out;
}

.update-indicator.hidden {
  opacity: 0;
  transform: scale(0.5);
}

@keyframes pulse {
  0% {
    opacity: 0;
    transform: scale(0.5);
  }
  50% {
    opacity: 1;
    transform: scale(1.2);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
