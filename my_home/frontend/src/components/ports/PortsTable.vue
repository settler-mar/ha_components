<template>
  <div class="ports-table-container">
    <!-- Заголовок группы -->
    <div v-if="title" class="group-header" @click="toggleCollapse">
      <div class="d-flex align-center">
        <div class="me-2 checkbox-container" :class="{ 'has-pending-changes': hasGroupPendingChanges }">
          <v-checkbox
            v-if="showHaCheckboxes"
            :model-value="groupHaPublished"
            :indeterminate="groupHaPublished === null"
            @update:model-value="toggleGroupHA"
            hide-details
            density="compact"
            :color="hasGroupPendingChanges ? 'warning' : undefined"
            @click.stop
          ></v-checkbox>
        </div>
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
          title="Портов опубликовано в Home Assistant"
        >
          HA: {{ publishedPortsCount }}
        </v-chip>
      </div>
    </div>

    <!-- Таблица портов -->
    <v-expand-transition>
      <div v-show="!isCollapsed" class="ports-table-content">
        <v-table density="compact" class="ports-table">
          <tbody>
            <CompactSmartPort
              v-for="port in visiblePorts"
              :key="port.id || port.code"
              :port="port"
              :value="getPortValue(port)"
              :show-ha-checkbox="showHaCheckboxes"
              :show-edit-button="showEditButtons"
              :show-update-indicator="getPortUpdateStatus(port)"
              :current-status="getPortCurrentStatus(port)"
              :has-pending-changes="hasPortChanges(port.code)"
              @update="handlePortUpdate"
              @edit="handlePortEdit"
              @ha-toggle="handlePortHAToggle"
            />
          </tbody>
        </v-table>

        <!-- Сообщение если нет портов -->
        <div v-if="ports.length === 0" class="no-ports-message">
          <v-icon icon="mdi-information-outline" class="mr-2"></v-icon>
          Порты не найдены
        </div>

        <!-- Пагинация -->
        <div v-if="showPagination" class="table-pagination">
          <v-pagination
            v-model="currentPage"
            :length="totalPages"
            :total-visible="5"
            size="small"
            variant="outlined"
          ></v-pagination>
        </div>
      </div>
    </v-expand-transition>
  </div>
</template>

<script setup>
import {ref, computed, defineProps, defineEmits} from 'vue'
import CompactSmartPort from './CompactSmartPort.vue'
import { useHAChangesStore } from '@/store/haChangesStore'
import UpdateIndicator from '@/components/UpdateIndicator.vue'
import FileListView from './FileListView.vue'
import TableTemplateView from './TableTemplateView.vue'

const props = defineProps({
  ports: {
    type: Array,
    default: () => []
  },
  device_id: {
    type: Number
  },
  title: {
    type: String,
    default: ''
  },
  groupIcon: {
    type: String,
    default: 'mdi-folder'
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
  showEditButtons: {
    type: Boolean,
    default: true
  },
  showGroupUpdate: {
    type: Boolean,
    default: false
  },
  updatedPorts: {
    type: Set,
    default: () => new Set()
  },
  itemsPerPage: {
    type: Number,
    default: 50
  },
  groupType: {
    type: String,
    default: 'ports'
  },
  groupTemplate: {
    type: String,
    default: ''
  },
  filesList: {
    type: Array,
    default: () => []
  },
  deviceBaseUrl: {
    type: String,
    default: ''
  },
})

const emit = defineEmits(['update', 'edit'])

const haChangesStore = useHAChangesStore()

// Reactive data
const isCollapsed = ref(props.defaultCollapsed)
const currentPage = ref(1)

// Computed properties
const totalPages = computed(() => {
  return Math.ceil(props.ports.length / props.itemsPerPage)
})

const showPagination = computed(() => {
  return props.ports.length > props.itemsPerPage
})

const visiblePorts = computed(() => {
  if (!showPagination.value) {
    return props.ports
  }

  const start = (currentPage.value - 1) * props.itemsPerPage
  const end = start + props.itemsPerPage

  return props.ports.slice(start, end)
})

// selectedPorts больше не используется, так как статус рассчитывается через store

// Функция для расчета текущего статуса порта (база + изменение из store)
const getPortCurrentStatus = (port) => {
  // В режиме HA используем реальный статус из HA данных
  if (props.showHaCheckboxes) {
    const haStatus = port.ha?.ha_published || false
    const storeAction = haChangesStore.getPortAction(props.device_id, port.code)

    if (storeAction === 'add') return true
    if (storeAction === 'remove') return false
    return haStatus
  }
  
  // В обычном режиме используем старую логику
  const baseStatus = !!port.published
  const storeAction = haChangesStore.getPortAction(props.device_id, port.code)

  if (storeAction === 'add') return true
  if (storeAction === 'remove') return false
  return baseStatus
}

// Функция для проверки, есть ли изменения для порта
const hasPortChanges = (portCode) => {
  return haChangesStore.hasPortChanges(props.device_id, portCode)
}

const groupHaPublished = computed(() => {
  const publishedCount = props.ports.filter(port => getPortCurrentStatus(port)).length
  const totalCount = props.ports.length

  if (publishedCount === 0) return false
  if (publishedCount === totalCount) return true
  return null // Частично выделено
})

const publishedPortsCount = computed(() => {
  return props.ports.filter(port => port.ha?.ha_published).length
})

const hasGroupPendingChanges = computed(() => {
  // Группа светится, если в ней есть хотя бы одно изменение
  return props.ports.some(port => hasPortChanges(port.code))
})

// Methods
const toggleCollapse = () => {
  if (props.collapsible) {
    isCollapsed.value = !isCollapsed.value
  }
}

const getPortValue = (port) => {
  return port.val !== undefined ? port.val : port.value
}

const getPortUpdateStatus = (port) => {
  return props.updatedPorts.has(port.code)
}

const handlePortUpdate = (code, value) => {
  emit('update', code, value)
}

const handlePortEdit = (port) => {
  emit('edit', port)
}

const handlePortHAToggle = (port, value) => {
  // В режиме HA используем реальный статус из HA данных как базовый
  const baseStatus = props.showHaCheckboxes ? (port.ha?.ha_published || false) : !!port.published
  const currentStatus = getPortCurrentStatus(port)

  console.log('handlePortHAToggle:', {
    portCode: port.code,
    baseStatus,
    currentStatus,
    newValue: value,
    deviceId: props.device_id,
    showHaCheckboxes: props.showHaCheckboxes
  })

  // Вычисляем действие для store
  let action
  if (value === baseStatus) {
    // Возврат к базовому состоянию - убираем изменение
    action = null
  } else {
    // Изменение от базового состояния
    action = value ? 'add' : 'remove'
  }

  console.log('Action for store:', action)

  // Обновляем store
  haChangesStore.updateChange(props.device_id, port.code, action)

  // Обновляем состояние группы после изменения порта
  updateGroupState()
}

const toggleGroupHA = (value) => {
  // Логика трехсостояния:
  // false -> true (выделить все)
  // true -> false (снять все)
  // null -> true (выделить все при клике на частично выделенное)
  let newValue

  if (value === null) {
    // Если частично выделено, выделяем все
    newValue = true
  } else {
    // Иначе переключаем состояние
    newValue = value
  }

  // Обновляем все порты в группе через цикл
  props.ports.forEach(port => {
    // В режиме HA используем реальный статус из HA данных как базовый
    const baseStatus = props.showHaCheckboxes ? (port.ha?.ha_published || false) : !!port.published

    // Вычисляем действие для store
    let action
    if (newValue === baseStatus) {
      // Возврат к базовому состоянию - убираем изменение
      action = null
    } else {
      // Изменение от базового состояния
      action = newValue ? 'add' : 'remove'
    }

    // Обновляем store для каждого порта
    haChangesStore.updateChange(props.device_id, port.code, action)
  })

  // Принудительно обновляем состояние группы после изменения всех портов
  updateGroupState()
}

// Функция для обновления состояния группы
const updateGroupState = () => {
  // Эта функция будет вызываться после обновления store
  // Vue автоматически пересчитает computed properties
}
</script>

<style scoped>
.ports-table-container {
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

.ports-table-content {
  margin-left: 0;
}

.ports-table {
  border: none;
  box-shadow: none;
}

.ports-table :deep(.v-table__wrapper) {
  border: none;
}

.control-cell {
  padding: 4px 8px;
}

.no-ports-message {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: rgba(0, 0, 0, 0.5);
  font-style: italic;
}

.table-pagination {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

.update-indicator-wrapper {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-left: 4px;
}

/* Стили для разных типов портов */
.compact-smart-port.port-input {
  background-color: rgba(76, 175, 80, 0.05);
}

.compact-smart-port.port-output {
  background-color: rgba(255, 152, 0, 0.05);
}

.compact-smart-port:hover {
  background-color: rgba(0, 0, 0, 0.02);
}

/* Адаптивные стили */
@media (max-width: 768px) {
  .group-header {
    padding: 6px 8px;
    font-size: 0.9em;
  }

  .control-cell {
    padding: 2px 4px;
  }

  /* Убираем горизонтальную прокрутку */
  .ports-table {
    width: 100%;
    table-layout: auto;
  }

  .ports-table :deep(table) {
    width: 100%;
    min-width: unset;
  }

  /* Компактные элементы управления на мобильных */
  .control-cell {
    min-width: unset;
    width: auto;
  }
}

@media (max-width: 480px) {
  .group-header {
    padding: 4px 6px;
    font-size: 0.85em;
  }

  /* Еще более компактный вид */
  .ports-table :deep(.v-chip) {
    font-size: 0.7em;
    height: 20px;
  }
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
</style>
