<template>
  <!-- Обычная строка таблицы для широких экранов -->
  <tr v-if="!isMobileView" class="compact-smart-port" :class="portClasses">
    <!-- Чекбокс для HA (если в режиме конфигурации) -->
    <td v-if="showHaCheckbox" style="width: 40px; position: relative;">
      <div class="checkbox-container" :class="{ 'has-pending-changes': hasPendingChanges }">
        <v-checkbox
          :model-value="currentStatus"
          @update:model-value="(value) => $emit('ha-toggle', port, value)"
          hide-details
          density="compact"
          :color="hasPendingChanges ? 'warning' : undefined"
        ></v-checkbox>
      </div>
    </td>
    
    <!-- Название и иконка порта -->
    <td style="width: 50%;">
      <v-tooltip location="top">
        <template #activator="{ props: tooltipProps }">
          <div v-bind="tooltipProps" class="d-flex align-center">
            <v-icon
              :icon="portTypeIcon"
              size="16"
              :color="portTypeColor"
              class="me-2"
            ></v-icon>
            <span>{{ port.title || port.name || port.code }}</span>
            
            <!-- HA индикатор -->
            <v-chip
              v-if="port.ha?.ha_published"
              size="x-small"
              color="orange"
              variant="tonal"
              class="ms-2"
              title="Опубликовано в Home Assistant"
            >
              HA
            </v-chip>
          </div>
        </template>
        {{ port.description || port.code }}
      </v-tooltip>
    </td>
    
    <!-- Элемент управления вместо текстового значения -->
    <td class="text-right control-cell">
      <component
        :is="compactPortComponent"
        :port="port"
        :value="currentValue"
        @update="handlePortUpdate"
      />
    </td>
    
    <!-- Индикатор обновления значения -->
    <td class="text-right update-cell" style="width: 30px; position: relative;">
      <UpdateIndicator 
        :show="showUpdateIndicator" 
        :duration="1000"
        title="Значение обновлено"
      />
    </td>
  </tr>

  <!-- Мобильная версия - 2 строки -->
  <template v-else>
    <tr class="compact-smart-port mobile-port-header" :class="portClasses">
      <td :colspan="getColspan()" class="mobile-port-title" style="position: relative;">
        <div class="d-flex align-center justify-space-between">
          <div class="d-flex align-center">
            <div class="me-2 checkbox-container" :class="{ 'has-pending-changes': hasPendingChanges }">
              <v-checkbox
                v-if="showHaCheckbox"
                :model-value="currentStatus"
                @update:model-value="(value) => $emit('ha-toggle', port, value)"
                hide-details
                density="compact"
                :color="hasPendingChanges ? 'warning' : undefined"
              ></v-checkbox>
            </div>
            
            <v-icon
              :icon="portTypeIcon"
              size="16"
              :color="portTypeColor"
              class="me-2"
            ></v-icon>
            <span class="font-weight-medium">{{ port.title || port.name || port.code }}</span>
            
            <!-- HA индикатор -->
            <v-chip
              v-if="port.ha?.ha_published"
              size="x-small"
              color="orange"
              variant="tonal"
              class="ms-2"
              title="Опубликовано в Home Assistant"
            >
              HA
            </v-chip>
          </div>
          
          <!-- Индикатор обновления -->
          <UpdateIndicator 
            :show="showUpdateIndicator" 
            :duration="1000"
            title="Значение обновлено"
          />
        </div>
      </td>
    </tr>
    
    <tr class="compact-smart-port mobile-port-control" :class="portClasses">
      <td :colspan="getColspan()" class="mobile-control-cell">
        <component
          :is="compactPortComponent"
          :port="port"
          :value="currentValue"
          @update="handlePortUpdate"
        />
      </td>
    </tr>
  </template>
</template>

<script setup>
import { computed, defineProps, defineEmits } from 'vue'
import CompactAnalogPort from './CompactAnalogPort.vue'
import CompactDigitalPort from './CompactDigitalPort.vue'
import CompactColorPort from './CompactColorPort.vue'
import CompactListPort from './CompactListPort.vue'
import UpdateIndicator from '@/components/UpdateIndicator.vue'

const props = defineProps({
  port: {
    type: Object,
    required: true
  },
  value: {
    type: [String, Number, Boolean],
    default: null
  },
  showHaCheckbox: {
    type: Boolean,
    default: false
  },
  showEditButton: {
    type: Boolean,
    default: true
  },
  showUpdateIndicator: {
    type: Boolean,
    default: false
  },
  currentStatus: {
    type: Boolean,
    default: false
  },
  hasPendingChanges: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update', 'edit', 'ha-toggle'])

// Computed properties
const isMobileView = computed(() => {
  // Определяем мобильный вид на основе ширины экрана
  if (typeof window !== 'undefined') {
    return window.innerWidth < 768
  }
  return false
})

const getColspan = () => {
  let cols = 3 // название, управление, индикатор
  if (props.showHaCheckbox) cols += 1
  return cols
}
const currentValue = computed(() => {
  return props.value !== undefined ? props.value : props.port.val
})

const isReadOnly = computed(() => {
  return props.port.type?.startsWith('in.') || props.port.direction === 'in'
})

const portType = computed(() => {
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

const compactPortComponent = computed(() => {
  const components = {
    analog: CompactAnalogPort,
    digital: CompactDigitalPort,
    color: CompactColorPort,
    list: CompactListPort
  }
  
  return components[portType.value] || CompactAnalogPort
})

const portClasses = computed(() => {
  return {
    'port-input': isReadOnly.value,
    'port-output': !isReadOnly.value,
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

const portTypeColor = computed(() => {
  const colors = {
    analog: 'blue',
    digital: 'green',
    color: 'purple',
    list: 'orange'
  }
  
  return colors[portType.value] || 'grey'
})

// hasPendingChanges теперь приходит как prop

// Methods
const handlePortUpdate = (code, value) => {
  emit('update', code, value)
}
</script>

<style scoped>
.compact-smart-port {
  transition: background-color 0.2s ease;
}

.compact-smart-port:hover {
  background-color: rgba(0, 0, 0, 0.02);
}

.compact-smart-port.port-input {
  background-color: rgba(76, 175, 80, 0.05);
}

.compact-smart-port.port-output {
  background-color: rgba(255, 152, 0, 0.05);
}

.control-cell {
  min-width: 120px;
  padding: 8px 12px;
}

.update-indicator-wrapper {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-left: 4px;
}

/* Мобильные стили - 2 строки */
.mobile-port-header {
  border-bottom: none !important;
}

.mobile-port-control {
  border-top: none !important;
  border-bottom: 1px solid #e0e0e0 !important;
}

.mobile-port-title {
  padding: 8px 12px 4px 12px !important;
  background-color: rgba(0, 0, 0, 0.02);
}

.mobile-control-cell {
  padding: 4px 12px 8px 12px !important;
  background-color: rgba(0, 0, 0, 0.01);
}

/* Стили для эффекта свечения */
.checkbox-container {
  position: relative;
  transition: all 0.3s ease;
}

.checkbox-container.has-pending-changes :deep(.v-selection-control__wrapper) {
  animation: glow-pulse 2s infinite;
}

.checkbox-container.has-pending-changes :deep(.v-selection-control__input) {
  animation: glow-pulse 2s infinite;
}

@keyframes glow-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.7);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(255, 193, 7, 0.3);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.7);
  }
}

/* Адаптивные стили */
@media (max-width: 768px) {
  .control-cell {
    min-width: 100px;
    padding: 6px 8px;
  }
}
</style>
