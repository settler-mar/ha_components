<template>
  <div class="smart-port" :class="portClasses">
    <!-- Заголовок порта -->
    <div class="port-header">
      <div class="port-title">
        <span class="port-name">{{ port.title || port.name || port.code }}</span>
        <span v-if="showCode" class="port-code">{{ port.code }}</span>
      </div>
      
      <!-- Индикатор типа порта -->
      <div class="port-type-indicator" :title="portTypeDescription">
        <v-icon :icon="portTypeIcon" size="14"></v-icon>
      </div>
    </div>
    
    <!-- Описание порта -->
    <div v-if="port.description" class="port-description">
      {{ port.description }}
    </div>
    
    <!-- Компонент порта в зависимости от типа -->
    <component
      :is="portComponent"
      :port="port"
      :value="currentValue"
      @update="handlePortUpdate"
      class="port-component"
    />
    
    <!-- Дополнительная информация -->
    <div v-if="showAdditionalInfo" class="port-additional-info">
      <div v-if="port.unit" class="port-unit">
        Единица: {{ port.unit }}
      </div>
      <div v-if="hasRange" class="port-range">
        Диапазон: {{ port.min }} - {{ port.max }}
      </div>
      <div v-if="port.step" class="port-step">
        Шаг: {{ port.step }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, defineProps, defineEmits } from 'vue'
import AnalogPort from './AnalogPort.vue'
import DigitalPort from './DigitalPort.vue'
import ColorPort from './ColorPort.vue'
import ListPort from './ListPort.vue'

const props = defineProps({
  port: {
    type: Object,
    required: true
  },
  value: {
    type: [String, Number, Boolean],
    default: null
  },
  showCode: {
    type: Boolean,
    default: false
  },
  showAdditionalInfo: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update'])

// Computed properties
const currentValue = computed(() => {
  return props.value !== undefined ? props.value : props.port.val
})

const portType = computed(() => {
  // Определяем тип порта на основе различных свойств
  const type = props.port.type || ''
  
  // Если есть список значений - это list порт
  if (props.port.list || props.port.options) {
    return 'list'
  }
  
  // Если это цветовой порт
  if (type.includes('color') || props.port.color !== undefined) {
    return 'color'
  }
  
  // Если это текстовый порт (in.text, out.text)
  if (type.includes('text')) {
    return 'analog' // Используем аналоговый компонент для текста
  }
  
  // Если это цифровой порт
  if (type.includes('didgi') || type.includes('digital') || type.includes('bool')) {
    return 'digital'
  }
  
  // Если это аналоговый порт
  if (type.includes('analog') || type.includes('int') || type.includes('float') || 
      props.port.min !== undefined || props.port.max !== undefined) {
    return 'analog'
  }
  
  // По умолчанию - аналоговый для числовых значений, иначе цифровой
  if (typeof currentValue.value === 'number') {
    return 'analog'
  }
  
  return 'analog' // По умолчанию аналоговый для текстовых значений
})

const portComponent = computed(() => {
  const components = {
    analog: AnalogPort,
    digital: DigitalPort,
    color: ColorPort,
    list: ListPort
  }
  
  return components[portType.value] || AnalogPort
})

const portClasses = computed(() => {
  const isInput = props.port.type?.startsWith('in.') || props.port.direction === 'in'
  
  return {
    'port-input': isInput,
    'port-output': !isInput,
    [`port-type-${portType.value}`]: true
  }
})

const portTypeIcon = computed(() => {
  const icons = {
    analog: 'mdi-chart-line',
    digital: 'mdi-toggle-switch',
    color: 'mdi-palette',
    list: 'mdi-format-list-bulleted'
  }
  
  return icons[portType.value] || 'mdi-circle'
})

const portTypeDescription = computed(() => {
  const descriptions = {
    analog: 'Аналоговый порт',
    digital: 'Цифровой порт',
    color: 'Цветовой порт',
    list: 'Порт со списком значений'
  }
  
  const direction = props.port.type?.startsWith('in.') ? ' (Вход)' : ' (Выход)'
  
  return descriptions[portType.value] + direction
})

const hasRange = computed(() => {
  return props.port.min !== undefined && props.port.max !== undefined
})

// Methods
const handlePortUpdate = (code, value) => {
  emit('update', code, value)
}
</script>

<style scoped>
.smart-port {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.2s ease;
  min-width: 200px;
}

.smart-port:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.2);
}

.smart-port.port-input {
  border-left: 3px solid #4caf50;
}

.smart-port.port-output {
  border-left: 3px solid #ff9800;
}

.port-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.port-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.port-name {
  font-size: 0.95em;
  font-weight: 600;
  color: #ffffff;
  line-height: 1.2;
}

.port-code {
  font-size: 0.75em;
  color: rgba(255, 255, 255, 0.6);
  font-family: monospace;
}

.port-type-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.7);
  transition: background-color 0.2s ease;
}

.smart-port:hover .port-type-indicator {
  background: rgba(255, 255, 255, 0.15);
}

.port-description {
  font-size: 0.8em;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.3;
  margin-top: -4px;
}

.port-component {
  margin-top: 4px;
}

.port-additional-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.port-unit,
.port-range,
.port-step {
  font-size: 0.75em;
  color: rgba(255, 255, 255, 0.5);
}

/* Специфичные стили для разных типов портов */
.smart-port.port-type-analog {
  --port-accent: #2196f3;
}

.smart-port.port-type-digital {
  --port-accent: #4caf50;
}

.smart-port.port-type-color {
  --port-accent: #e91e63;
}

.smart-port.port-type-list {
  --port-accent: #ff9800;
}

/* Темная тема */
@media (prefers-color-scheme: dark) {
  .smart-port {
    background: rgba(255, 255, 255, 0.05);
  }
  
  .smart-port:hover {
    background: rgba(255, 255, 255, 0.08);
  }
}
</style>
