<template>
  <div class="digital-port" :class="{ 'read-only': isReadOnly }">
    <label class="digital-switch" :class="{ 'active': isActive, 'disabled': isReadOnly }">
      <input
        type="checkbox"
        :checked="isActive"
        :disabled="isReadOnly"
        @change="toggleValue"
        class="switch-input"
      />
      <span class="switch-slider"></span>
      <div class="switch-labels">
        <span class="label-off" :class="{ 'active': !isActive }">{{ offLabel }}</span>
        <span class="label-on" :class="{ 'active': isActive }">{{ onLabel }}</span>
      </div>
    </label>
    
    <!-- Индикатор состояния -->
    <div class="status-indicator" :class="{ 'active': isActive }">
      <div class="indicator-dot"></div>
      <span class="status-text">{{ isActive ? onLabel : offLabel }}</span>
    </div>
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
  }
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
  if (isReadOnly.value) return
  
  const newValue = event.target.checked
  emit('update', props.port.code, newValue ? '1' : '0')
}
</script>

<style scoped>
.digital-port {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  min-width: 100px;
}

.digital-port.read-only {
  background: rgba(255, 255, 255, 0.02);
}

.digital-switch {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.digital-switch.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.switch-input {
  display: none;
}

.switch-slider {
  position: relative;
  width: 50px;
  height: 24px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  transition: background-color 0.3s ease;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.switch-slider::before {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 18px;
  height: 18px;
  background: #ffffff;
  border-radius: 50%;
  transition: transform 0.3s ease, background-color 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.digital-switch.active .switch-slider {
  background: #68b700;
  border-color: #68b700;
}

.digital-switch.active .switch-slider::before {
  transform: translateX(26px);
  background: #ffffff;
}

.switch-labels {
  display: flex;
  gap: 16px;
  font-size: 0.8em;
  font-weight: 500;
}

.label-off,
.label-on {
  color: rgba(255, 255, 255, 0.6);
  transition: color 0.3s ease;
}

.label-off.active,
.label-on.active {
  color: #68b700;
}

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
  background: rgba(255, 255, 255, 0.3);
  transition: background-color 0.3s ease;
}

.status-indicator.active .indicator-dot {
  background: #68b700;
  box-shadow: 0 0 8px rgba(104, 183, 0, 0.5);
}

.status-text {
  color: rgba(255, 255, 255, 0.8);
  font-weight: 500;
}

.status-indicator.active .status-text {
  color: #68b700;
}

/* Hover эффекты для интерактивных элементов */
.digital-switch:not(.disabled):hover .switch-slider {
  background: rgba(255, 255, 255, 0.3);
}

.digital-switch.active:not(.disabled):hover .switch-slider {
  background: #7bc908;
}

/* Темная тема */
@media (prefers-color-scheme: dark) {
  .digital-port {
    background: rgba(255, 255, 255, 0.08);
  }
  
  .digital-port.read-only {
    background: rgba(255, 255, 255, 0.04);
  }
}
</style>







