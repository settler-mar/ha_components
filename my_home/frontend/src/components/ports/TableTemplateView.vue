<template>
  <div class="table-template-view">
    <!-- Заголовок группы -->
    <div v-if="title" class="group-header" @click="toggleCollapse">
      <div class="d-flex align-center">
        <v-checkbox
          v-if="showHaCheckboxes"
          :model-value="groupHaPublished"
          @update:model-value="toggleGroupHA"
          hide-details
          class="me-2"
          size="small"
          @click.stop
        ></v-checkbox>
        
        <v-icon 
          :icon="isCollapsed ? 'mdi-chevron-right' : 'mdi-chevron-down'" 
          size="16" 
          class="me-2"
        ></v-icon>
        
        <v-icon :icon="groupIcon" class="me-2"></v-icon>
        
        <span class="font-weight-medium">{{ title }}</span>
        
        <!-- Индикатор обновления группы -->
        <div class="update-indicator-wrapper group-update-wrapper" style="position: relative;">
          <UpdateIndicator 
            :show="showGroupUpdate" 
            :duration="1000"
            title="Группа обновлена"
          />
        </div>
        
        <v-chip size="x-small" color="primary" variant="outlined" class="ms-2">
          {{ ports.length }}
        </v-chip>
        
        <v-chip 
          v-if="publishedPortsCount > 0"
          size="x-small" 
          color="orange" 
          variant="outlined" 
          class="ms-1"
        >
          HA: {{ publishedPortsCount }}
        </v-chip>
      </div>
    </div>
    
    <!-- Табличное отображение -->
    <v-expand-transition>
      <div v-show="!isCollapsed" class="table-content">
        <v-table density="compact" class="template-table">
          <thead>
            <tr>
              <th class="text-left">Параметр</th>
              <th v-for="col in tableColumns" :key="col" class="text-center">
                <div class="d-flex flex-column align-center">
                  <span>Канал {{ col }}</span>
                  <v-tooltip :text="getColumnTooltip(col)" location="bottom">
                    <template v-slot:activator="{ props }">
                      <v-chip 
                        v-bind="props"
                        size="x-small" 
                        :color="getColumnOnlineStatus(col) ? 'success' : 'error'"
                        variant="outlined"
                        class="cursor-help"
                      >
                        {{ getColumnOnlineStatus(col) ? 'Online' : 'Offline' }}
                      </v-chip>
                    </template>
                  </v-tooltip>
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in tableRows" :key="row" class="table-row">
              <td class="text-body-2 font-weight-medium">
                <div class="d-flex align-center">
                  <v-checkbox
                    v-if="showHaCheckboxes"
                    :model-value="isRowPublished(row)"
                    @update:model-value="(value) => toggleRowPublishing(row, value)"
                    hide-details
                    class="me-2"
                    size="small"
                  ></v-checkbox>
                  <span>{{ getRowTitle(row) }}</span>
                </div>
              </td>
              <td v-for="col in tableColumns" :key="`${row}-${col}`" class="text-center table-cell">
                <div v-if="getCellPort(row, col)" class="cell-content">
                  <v-tooltip :text="getCellTooltip(row, col)" location="top">
                    <template v-slot:activator="{ props }">
                      <div v-bind="props" class="cell-wrapper">
                        <div class="cell-content-with-indicator" style="position: relative;">
                          <!-- Используем компактные компоненты для ячеек -->
                          <component
                            :is="getCellComponent(row, col)"
                            :port="getCellPort(row, col)"
                            :value="getCellValue(row, col)"
                            @update="handleCellUpdate"
                            class="table-cell-control"
                          />
                          
                          <!-- Индикатор обновления ячейки -->
                          <UpdateIndicator 
                            :show="isCellUpdated(row, col)" 
                            :duration="1000"
                            title="Значение обновлено"
                            style="top: 2px; right: 2px; left: auto;"
                          />
                        </div>
                      </div>
                    </template>
                  </v-tooltip>
                </div>
                <span v-else class="text-grey">-</span>
              </td>
            </tr>
          </tbody>
        </v-table>
      </div>
    </v-expand-transition>
  </div>
</template>

<script setup>
import { ref, computed, defineProps, defineEmits } from 'vue'
import CompactAnalogPort from './CompactAnalogPort.vue'
import CompactDigitalPort from './CompactDigitalPort.vue'
import CompactColorPort from './CompactColorPort.vue'
import CompactListPort from './CompactListPort.vue'
import UpdateIndicator from '@/components/UpdateIndicator.vue'

const props = defineProps({
  ports: {
    type: Array,
    default: () => []
  },
  title: {
    type: String,
    default: ''
  },
  groupIcon: {
    type: String,
    default: 'mdi-table'
  },
  collapsible: {
    type: Boolean,
    default: true
  },
  defaultCollapsed: {
    type: Boolean,
    default: false
  },
  showHaCheckboxes: {
    type: Boolean,
    default: false
  },
  showGroupUpdate: {
    type: Boolean,
    default: false
  },
  updatedPorts: {
    type: Set,
    default: () => new Set()
  }
})

const emit = defineEmits(['update', 'ha-toggle-port', 'ha-toggle-group'])

// Reactive data
const isCollapsed = ref(props.defaultCollapsed)

// Computed properties
const tableColumns = computed(() => {
  const columns = new Set()
  props.ports.forEach(port => {
    if (port.column !== undefined) {
      columns.add(port.column)
    }
  })
  return Array.from(columns).sort((a, b) => a - b)
})

const tableRows = computed(() => {
  const rows = new Set()
  props.ports.forEach(port => {
    if (port.row !== undefined && port.row >= 0) {
      rows.add(port.row)
    }
  })
  return Array.from(rows).sort((a, b) => a - b)
})

const groupHaPublished = computed(() => {
  return props.ports.some(port => port.haPublished)
})

const publishedPortsCount = computed(() => {
  return props.ports.filter(port => port.haPublished).length
})

// Methods
const toggleCollapse = () => {
  if (props.collapsible) {
    isCollapsed.value = !isCollapsed.value
  }
}

const getCellPort = (row, col) => {
  return props.ports.find(port => port.row === row && port.column === col)
}

const getCellValue = (row, col) => {
  const port = getCellPort(row, col)
  return port ? (port.val !== undefined ? port.val : port.value) : null
}

const getCellComponent = (row, col) => {
  const port = getCellPort(row, col)
  if (!port) return null
  
  const type = port.type || ''
  
  // Определяем компонент на основе типа
  if (port.list || port.options) return CompactListPort
  if (type.includes('color')) return CompactColorPort
  if (type.includes('didgi') || type.includes('digital')) return CompactDigitalPort
  return CompactAnalogPort
}

const getRowTitle = (row) => {
  // Находим первый порт в строке для получения названия
  const firstPort = props.ports.find(port => port.row === row)
  if (firstPort) {
    return firstPort.title || firstPort.name || `Строка ${row}`
  }
  return `Строка ${row}`
}

const getColumnOnlineStatus = (col) => {
  // Ищем порт "Online" в этой колонке (row: -1 означает заголовок)
  const onlinePort = props.ports.find(port => 
    port.column === col && 
    port.row === -1 && 
    port.type === 'in.didgi' && 
    port.title === 'Online'
  )
  
  if (onlinePort) {
    // Проверяем значение: "255" означает онлайн, "0" - офлайн
    return onlinePort.val === "255" || onlinePort.val === 255
  }
  
  // Если нет порта Online, считаем офлайн
  return false
}

const isRowPublished = (row) => {
  const rowPorts = props.ports.filter(port => port.row === row)
  return rowPorts.some(port => port.haPublished)
}

const toggleRowPublishing = (row, value) => {
  const rowPorts = props.ports.filter(port => port.row === row)
  rowPorts.forEach(port => {
    port.haPublished = value
    emit('ha-toggle-port', port, value)
  })
}

const toggleGroupHA = (value) => {
  emit('ha-toggle-group', props.ports, value)
}

const isCellUpdated = (row, col) => {
  const port = getCellPort(row, col)
  return port ? props.updatedPorts.has(port.code) : false
}

const handleCellUpdate = (code, value) => {
  emit('update', code, value)
}

const getCellTooltip = (row, col) => {
  const port = getCellPort(row, col)
  if (!port) return ''
  
  // Показываем только код порта
  return port.code || 'Код неизвестен'
}

const getColumnTooltip = (col) => {
  const onlinePort = props.ports.find(port => 
    port.column === col && 
    port.row === -1 && 
    port.type === 'in.didgi' && 
    port.title === 'Online'
  )
  
  if (onlinePort) {
    const status = getColumnOnlineStatus(col) ? 'Online' : 'Offline'
    const value = onlinePort.val
    return `Статус канала ${col}: ${status}\nЗначение: ${value}\nКод: ${onlinePort.code}`
  }
  
  return `Канал ${col} - статус неизвестен`
}
</script>

<style scoped>
.table-template-view {
  margin-bottom: 8px;
}

.group-header {
  padding: 8px 12px;
  background-color: #f5f5f5;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
  border: 1px solid #e0e0e0;
  margin-bottom: 4px;
}

.group-header:hover {
  background-color: #eeeeee;
}

.table-content {
  background-color: #fafafa;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.template-table {
  border: none;
  box-shadow: none;
}

.template-table :deep(.v-table__wrapper) {
  border: none;
}

.template-table th {
  background-color: #f5f5f5;
  font-weight: 600;
  border-bottom: 2px solid #e0e0e0;
  padding: 8px 12px;
}

.table-row {
  transition: background-color 0.2s ease;
}

.table-row:hover {
  background-color: rgba(0, 0, 0, 0.02);
}

.table-cell {
  padding: 4px 8px;
  vertical-align: middle;
}

.cell-content {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 32px;
}

.cell-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  cursor: help;
}

.cell-content-with-indicator {
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
}

.cursor-help {
  cursor: help !important;
}

.table-cell-control {
  max-width: 100px;
}

.update-indicator-wrapper {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-left: 4px;
}

/* Адаптивные стили */
@media (max-width: 768px) {
  .group-header {
    padding: 6px 8px;
    font-size: 0.9em;
  }
  
  .template-table th {
    padding: 6px 8px;
    font-size: 0.8em;
  }
  
  .table-cell {
    padding: 2px 4px;
  }
  
  .table-cell-control {
    max-width: 80px;
  }
}
</style>
