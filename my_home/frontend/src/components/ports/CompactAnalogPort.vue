<template>
  <div class="compact-analog-port">
    <!-- Для входных портов - только значение -->
    <span v-if="isReadOnly" class="port-value">
      {{ formattedValue }}
      <span v-if="port.unit" class="unit">{{ port.unit }}</span>
    </span>
    
    <!-- Для выходных портов - элемент управления -->
    <div v-else class="port-control">
      <!-- Если есть диапазон - слайдер -->
      <div v-if="hasMinMax" class="slider-container">
        <input
          v-model.number="inputValue"
          type="range"
          :min="port.min"
          :max="port.max"
          :step="port.step || 1"
          @input="updateValue"
          class="port-slider"
        />
        <div class="slider-info">
          <span class="slider-value">{{ formattedValue }}</span>
          <span v-if="port.unit" class="slider-unit">{{ port.unit }}</span>
        </div>
      </div>
      
      <!-- Иначе - поле ввода (текст или число) -->
      <input
        v-else
        v-model="inputValue"
        :type="inputType"
        :min="port.min"
        :max="port.max"
        :step="port.step || 1"
        @change="updateValue"
        @keyup.enter="updateValue"
        class="port-input"
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
  },
})

const emit = defineEmits(['update'])

// Reactive data
const inputValue = ref(props.value || 0)

// Computed properties
const isReadOnly = computed(() => {
  return props.port.type?.startsWith('in.') || props.port.direction === 'in'
})

const hasMinMax = computed(() => {
  return props.port.min !== undefined && props.port.max !== undefined
})

const isTextType = computed(() => {
  return props.port.type?.includes('text')
})

const inputType = computed(() => {
  return isTextType.value ? 'text' : 'number'
})

const formattedValue = computed(() => {
  if (isTextType.value) {
    return props.value || ''
  }
  const val = parseFloat(props.value) || 0
  return val % 1 === 0 ? val.toString() : val.toFixed(2)
})

// Methods
const updateValue = () => {
  if (isTextType.value) {
    emit('update', props.port.code, inputValue.value)
  } else {
    const val = parseFloat(inputValue.value) || 0
    emit('update', props.port.code, val)
  }
}

// Watchers
watch(() => props.value, (newValue) => {
  if (isTextType.value) {
    inputValue.value = newValue || ''
  } else {
    inputValue.value = parseFloat(newValue) || 0
  }
})
</script>

<style scoped>
.compact-analog-port {
  display: flex;
  align-items: center;
  min-width: 80px;
}

.port-value {
  font-weight: 500;
  color: #333;
}

.unit {
  font-size: 0.85em;
  color: #666;
  margin-left: 2px;
}

.port-control {
  display: flex;
  align-items: center;
  width: 100%;
}

.slider-container {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 130px; /* Фиксированная ширина: 80px (слайдер) + 8px (gap) + 42px (значение) */
}

.slider-info {
  display: flex;
  align-items: baseline;
  gap: 2px;
  min-width: 50px;
}

.slider-unit {
  font-size: 0.75em;
  color: #888;
}

.port-slider {
  width: 80px; /* Фиксированная ширина для всех слайдеров */
  height: 4px;
  background: #ddd;
  border-radius: 2px;
  outline: none;
  cursor: pointer;
  appearance: none;
}

.port-slider::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  background: #007bff;
  border: 2px solid #fff;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 123, 255, 0.3);
  transition: all 0.2s ease;
}

.port-slider::-webkit-slider-thumb:hover {
  background: #0056b3;
  transform: scale(1.1);
  box-shadow: 0 3px 6px rgba(0, 123, 255, 0.5);
}

.port-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  background: #007bff;
  border: 2px solid #fff;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 123, 255, 0.3);
  transition: all 0.2s ease;
}

.port-slider::-moz-range-thumb:hover {
  background: #0056b3;
  transform: scale(1.1);
}

.slider-value {
  font-size: 0.85em;
  font-weight: 500;
  color: #333;
  min-width: 40px;
  text-align: right;
}

.port-input {
  width: 80px;
  min-width: 60px;
  max-width: 120px;
  padding: 2px 6px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 0.85em;
  text-align: center;
}

.port-input[type="text"] {
  width: 100px;
  max-width: 150px;
  text-align: left;
}

.port-input:focus {
  outline: none;
  border-color: #007bff;
}

/* Убираем стрелки у number input */
.port-input::-webkit-outer-spin-button,
.port-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.port-input[type="number"] {
  -moz-appearance: textfield;
}
</style>
