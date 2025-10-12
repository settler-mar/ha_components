<template>
  <div class="compact-list-port">
    <!-- Для входных портов - только текущее значение -->
    <span v-if="isReadOnly" class="current-value">
      {{ currentLabel }}
    </span>
    
    <!-- Для выходных портов - селект -->
    <select
      v-else
      v-model="selectedValue"
      @change="updateValue"
      class="port-select"
    >
      <option
        v-for="(label, key) in optionsList"
        :key="key"
        :value="key"
      >
        {{ label }}
      </option>
    </select>
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
  },
})

const emit = defineEmits(['update'])

// Reactive data
const selectedValue = ref(props.value || '')

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

// Methods
const updateValue = () => {
  emit('update', props.port.code, selectedValue.value)
}

// Watchers
watch(() => props.value, (newValue) => {
  selectedValue.value = newValue || ''
}, { immediate: true })
</script>

<style scoped>
.compact-list-port {
  display: flex;
  align-items: center;
  min-width: 80px;
}

.current-value {
  font-weight: 500;
  color: #333;
  font-size: 0.9em;
}

.port-select {
  width: 100%;
  min-width: 100px;
  max-width: 150px;
  padding: 2px 6px;
  border: 1px solid #ddd;
  border-radius: 3px;
  background: white;
  font-size: 0.85em;
  cursor: pointer;
}

.port-select:focus {
  outline: none;
  border-color: #007bff;
}

.port-select option {
  padding: 2px 4px;
}
</style>
