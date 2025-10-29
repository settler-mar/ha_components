<template>
  <div class="analog-port" :class="{ 'read-only': isReadOnly }">
    <!-- Числовое значение -->
    <div class="port-value">
      <span class="value-text">{{ formattedValue }}</span>
      <span v-if="port.unit" class="value-unit">{{ port.unit }}</span>
    </div>
    
    <!-- Прогресс-бар для аналоговых значений -->
    <div v-if="hasMinMax" class="progress-container">
      <div class="progress-bar">
        <div 
          class="progress-fill" 
          :style="{ width: progressPercent + '%' }"
          :class="getProgressColorClass()"
        ></div>
        
        <!-- Интерактивные элементы для out портов -->
        <div v-if="!isReadOnly" class="progress-controls">
          <span
            v-for="i in controlSteps"
            :key="i"
            class="control-step"
            :style="{ left: (i / controlSteps * 100) + '%' }"
            @click="setValue(getStepValue(i))"
          ></span>
        </div>
      </div>
      
      <!-- Подписи мин/макс -->
      <div class="progress-labels">
        <span class="min-label">{{ port.min }}</span>
        <span class="max-label">{{ port.max }}</span>
      </div>
    </div>
    
    <!-- Поле ввода для out портов -->
    <div v-if="!isReadOnly && !hasMinMax" class="input-container">
      <input
        v-model.number="inputValue"
        type="number"
        :min="port.min"
        :max="port.max"
        :step="port.step || 1"
        @change="setValue(inputValue)"
        @keyup.enter="setValue(inputValue)"
        class="value-input"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, defineProps, defineEmits } from 'vue'

const props = defineProps({
  port: {
    type: Object,
    required: true
  },
  value: {
    type: [Number, String],
    default: 0
  }
})

const emit = defineEmits(['update'])

// Reactive data
const inputValue = ref(parseFloat(props.value) || 0)

// Computed properties
const isReadOnly = computed(() => {
  return props.port.type?.startsWith('in.') || props.port.direction === 'in'
})

const hasMinMax = computed(() => {
  return props.port.min !== undefined && props.port.max !== undefined
})

const formattedValue = computed(() => {
  const val = parseFloat(props.value) || 0
  return val % 1 === 0 ? val.toString() : val.toFixed(2)
})

const progressPercent = computed(() => {
  if (!hasMinMax.value) return 0
  
  const val = parseFloat(props.value) || 0
  const min = parseFloat(props.port.min) || 0
  const max = parseFloat(props.port.max) || 100
  
  let percent = ((val - min) / (max - min)) * 100
  percent = Math.max(0, Math.min(100, percent))
  
  return percent
})

const controlSteps = computed(() => {
  return hasMinMax.value ? 40 : 10
})

// Methods
const setValue = (newValue) => {
  const val = parseFloat(newValue) || 0
  inputValue.value = val
  emit('update', props.port.code, val)
}

const getStepValue = (step) => {
  if (!hasMinMax.value) return step
  
  const min = parseFloat(props.port.min) || 0
  const max = parseFloat(props.port.max) || 100
  
  return min + (max - min) * (step / controlSteps.value)
}

const getProgressColorClass = () => {
  const percent = progressPercent.value
  if (percent < 25) return 'progress-low'
  if (percent < 75) return 'progress-medium'
  return 'progress-high'
}

// Watchers
watch(() => props.value, (newValue) => {
  inputValue.value = parseFloat(newValue) || 0
})
</script>

<style scoped>
.analog-port {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  min-width: 120px;
}

.analog-port.read-only {
  background: rgba(255, 255, 255, 0.02);
}

.port-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
  font-weight: 500;
}

.value-text {
  font-size: 1.1em;
  color: #ffffff;
}

.value-unit {
  font-size: 0.85em;
  color: #b0b0b0;
}

.progress-container {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.progress-bar {
  position: relative;
  height: 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease, background-color 0.3s ease;
}

.progress-fill.progress-low {
  background: linear-gradient(90deg, #4caf50, #8bc34a);
}

.progress-fill.progress-medium {
  background: linear-gradient(90deg, #ff9800, #ffc107);
}

.progress-fill.progress-high {
  background: linear-gradient(90deg, #f44336, #ff5722);
}

.progress-controls {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  cursor: pointer;
}

.control-step {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: transparent;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.control-step:hover {
  background: rgba(255, 255, 255, 0.3);
}

.progress-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.75em;
  color: #888;
}

.input-container {
  display: flex;
}

.value-input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  font-size: 0.9em;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.value-input:focus {
  outline: none;
  border-color: #68b700;
  background: rgba(255, 255, 255, 0.15);
}

.value-input::-webkit-outer-spin-button,
.value-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.value-input[type="number"] {
  -moz-appearance: textfield;
}

/* Темная тема */
@media (prefers-color-scheme: dark) {
  .analog-port {
    background: rgba(255, 255, 255, 0.08);
  }
  
  .analog-port.read-only {
    background: rgba(255, 255, 255, 0.04);
  }
}
</style>







