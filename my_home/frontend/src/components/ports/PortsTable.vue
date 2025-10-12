<template>
  <div class="ports-table-container">
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
import { ref, computed, defineProps, defineEmits } from 'vue'
import CompactSmartPort from './CompactSmartPort.vue'
import UpdateIndicator from '@/components/UpdateIndicator.vue'
import FileListView from './FileListView.vue'
import TableTemplateView from './TableTemplateView.vue'

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
  }
})

const emit = defineEmits(['update', 'edit', 'ha-toggle-port', 'ha-toggle-group'])

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
  emit('ha-toggle-port', port, value)
}

const toggleGroupHA = (value) => {
  emit('ha-toggle-group', props.ports, value)
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
</style>
