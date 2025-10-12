<template>
  <div class="list-port" :class="{ 'read-only': isReadOnly }">
    <!-- Текущее значение для read-only портов -->
    <div v-if="isReadOnly" class="current-value">
      <div class="value-display">
        <span class="value-text">{{ currentLabel }}</span>
        <span v-if="showKey" class="value-key">({{ currentValue }})</span>
      </div>
    </div>
    
    <!-- Селект для out портов -->
    <div v-else class="select-container">
      <select
        v-model="selectedValue"
        @change="updateValue"
        class="value-select"
      >
        <option
          v-for="(label, key) in optionsList"
          :key="key"
          :value="key"
        >
          {{ label }}
        </option>
      </select>
      
      <!-- Кастомная стрелка -->
      <div class="select-arrow">
        <svg width="12" height="8" viewBox="0 0 12 8" fill="currentColor">
          <path d="M6 8L0 2L1.4 0.6L6 5.2L10.6 0.6L12 2L6 8Z"/>
        </svg>
      </div>
    </div>
    
    <!-- Опциональный список всех доступных значений -->
    <div v-if="showAllOptions && optionsList" class="options-list">
      <div class="options-header">Доступные значения:</div>
      <div class="options-grid">
        <div
          v-for="(label, key) in optionsList"
          :key="key"
          class="option-item"
          :class="{ 'active': key == currentValue, 'clickable': !isReadOnly }"
          @click="!isReadOnly && selectOption(key)"
        >
          <span class="option-label">{{ label }}</span>
          <span class="option-key">{{ key }}</span>
        </div>
      </div>
    </div>
    
    <!-- Кнопка показать/скрыть все опции -->
    <button
      v-if="Object.keys(optionsList || {}).length > 3"
      @click="showAllOptions = !showAllOptions"
      class="toggle-options"
    >
      {{ showAllOptions ? 'Скрыть' : 'Показать все' }}
      <svg 
        width="12" 
        height="8" 
        viewBox="0 0 12 8" 
        fill="currentColor"
        :class="{ 'rotated': showAllOptions }"
      >
        <path d="M6 8L0 2L1.4 0.6L6 5.2L10.6 0.6L12 2L6 8Z"/>
      </svg>
    </button>
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
    type: [String, Number],
    default: ''
  }
})

const emit = defineEmits(['update'])

// Reactive data
const selectedValue = ref(props.value || '')
const showAllOptions = ref(false)

// Computed properties
const isReadOnly = computed(() => {
  return props.port.type?.startsWith('in.') || props.port.direction === 'in'
})

const optionsList = computed(() => {
  return props.port.list || props.port.options || {}
})

const currentValue = computed(() => {
  return props.value !== undefined ? props.value : selectedValue.value
})

const currentLabel = computed(() => {
  const options = optionsList.value
  if (!options || typeof options !== 'object') return currentValue.value
  
  const label = options[currentValue.value]
  return label !== undefined ? label : currentValue.value
})

const showKey = computed(() => {
  return currentValue.value !== currentLabel.value
})

// Methods
const updateValue = () => {
  emit('update', props.port.code, selectedValue.value)
}

const selectOption = (key) => {
  if (isReadOnly.value) return
  
  selectedValue.value = key
  emit('update', props.port.code, key)
}

// Watchers
watch(() => props.value, (newValue) => {
  selectedValue.value = newValue || ''
}, { immediate: true })
</script>

<style scoped>
.list-port {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  min-width: 120px;
}

.list-port.read-only {
  background: rgba(255, 255, 255, 0.02);
}

.current-value {
  display: flex;
  flex-direction: column;
}

.value-display {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.value-text {
  font-size: 0.95em;
  font-weight: 500;
  color: #ffffff;
}

.value-key {
  font-size: 0.8em;
  color: rgba(255, 255, 255, 0.6);
  font-family: monospace;
}

.select-container {
  position: relative;
  display: flex;
  align-items: center;
}

.value-select {
  width: 100%;
  padding: 6px 24px 6px 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  font-size: 0.9em;
  cursor: pointer;
  appearance: none;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.value-select:focus {
  outline: none;
  border-color: #68b700;
  background: rgba(255, 255, 255, 0.15);
}

.value-select option {
  background: #2c3e50;
  color: #ffffff;
  padding: 4px 8px;
}

.select-arrow {
  position: absolute;
  right: 8px;
  pointer-events: none;
  color: rgba(255, 255, 255, 0.6);
  transition: transform 0.2s ease;
}

.value-select:focus + .select-arrow {
  transform: rotate(180deg);
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
}

.options-header {
  font-size: 0.8em;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}

.options-grid {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 120px;
  overflow-y: auto;
}

.option-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.05);
  transition: background-color 0.2s ease;
}

.option-item.active {
  background: rgba(104, 183, 0, 0.2);
  border: 1px solid rgba(104, 183, 0, 0.4);
}

.option-item.clickable {
  cursor: pointer;
}

.option-item.clickable:hover {
  background: rgba(255, 255, 255, 0.1);
}

.option-item.active.clickable:hover {
  background: rgba(104, 183, 0, 0.3);
}

.option-label {
  font-size: 0.85em;
  color: #ffffff;
  flex: 1;
}

.option-key {
  font-size: 0.75em;
  color: rgba(255, 255, 255, 0.5);
  font-family: monospace;
}

.toggle-options {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 4px 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.8);
  font-size: 0.8em;
  cursor: pointer;
  transition: all 0.2s ease;
}

.toggle-options:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.3);
}

.toggle-options svg {
  transition: transform 0.2s ease;
}

.toggle-options svg.rotated {
  transform: rotate(180deg);
}

/* Кастомный скроллбар для списка опций */
.options-grid::-webkit-scrollbar {
  width: 4px;
}

.options-grid::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.options-grid::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.3);
  border-radius: 2px;
}

.options-grid::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.5);
}

/* Темная тема */
@media (prefers-color-scheme: dark) {
  .list-port {
    background: rgba(255, 255, 255, 0.08);
  }
  
  .list-port.read-only {
    background: rgba(255, 255, 255, 0.04);
  }
}
</style>


