<template>
  <div class="compact-digital-port">
    <!-- Переключатель для всех цифровых портов (и входных, и выходных) -->
    <label class="digital-toggle" :class="{ 'active': isActive, 'disabled': isReadOnly }">
      <input
        type="checkbox"
        :checked="isActive"
        :disabled="isReadOnly"
        @change="toggleValue"
        class="toggle-input"
      />
      <span class="toggle-slider"></span>
      <span class="toggle-label">{{ isActive ? onLabel : offLabel }}</span>
    </label>
  </div>
</template>

<script setup>
import { computed, defineProps, defineEmits } from 'vue'

const props = defineProps({
  port: {
    type: Object,
    required: true
  },
  value: {
    type: [String, Number, Boolean],
    default: false
  },
})

const emit = defineEmits(['update'])

// Computed properties
const isReadOnly = computed(() => {
  return props.port.type?.startsWith('in.') || props.port.direction === 'in'
})

const isActive = computed(() => {
  if (typeof props.value === 'boolean') return props.value
  if (typeof props.value === 'string') return props.value !== '0' && props.value.toLowerCase() !== 'false'
  if (typeof props.value === 'number') return props.value !== 0
  return false
})

const onLabel = computed(() => {
  return props.port.on || props.port.labels?.on || 'ON'
})

const offLabel = computed(() => {
  return props.port.off || props.port.labels?.off || 'OFF'
})

// Methods
const toggleValue = (event) => {
  if (isReadOnly.value) return // Не обновляем входные порты
  
  const newValue = event.target.checked
  emit('update', props.port.code, newValue ? '1' : '0')
}
</script>

<style scoped>
.compact-digital-port {
  display: flex;
  align-items: center;
  min-width: 60px;
}

/* Стили для индикатора (входные порты) */
.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85em;
}

.indicator-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
  transition: background-color 0.3s ease;
}

.status-indicator.active .indicator-dot {
  background: #4caf50;
}

.status-text {
  color: #666;
  font-weight: 500;
}

.status-indicator.active .status-text {
  color: #4caf50;
}

/* Стили для переключателя (выходные порты) */
.digital-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.85em;
  min-width: 80px;
  justify-content: flex-start;
}

.toggle-input {
  display: none;
}

.toggle-slider {
  position: relative;
  width: 34px;
  height: 18px;
  background: #ccc;
  border-radius: 9px;
  transition: background-color 0.3s ease;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  background: white;
  border-radius: 50%;
  transition: transform 0.3s ease;
}

.digital-toggle.active .toggle-slider {
  background: #4caf50;
}

.digital-toggle.active .toggle-slider::before {
  transform: translateX(16px);
}

.toggle-label {
  color: #666;
  font-weight: 500;
  min-width: 25px;
}

.digital-toggle.active .toggle-label {
  color: #4caf50;
}

.digital-toggle:hover:not(.disabled) .toggle-slider {
  background: #bbb;
}

.digital-toggle.active:hover:not(.disabled) .toggle-slider {
  background: #45a049;
}

.digital-toggle.disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.digital-toggle.disabled .toggle-slider {
  background: #e0e0e0;
}

.digital-toggle.disabled.active .toggle-slider {
  background: #a5d6a7;
}

.digital-toggle.disabled .toggle-label {
  color: #999;
}
</style>
