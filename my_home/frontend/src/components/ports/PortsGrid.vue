<template>
  <div class="ports-grid" :class="gridClasses">
    <!-- Заголовок группы -->
    <div v-if="title" class="grid-header">
      <h3 class="grid-title">
        {{ title }}
        <span v-if="showPortCount" class="port-count">({{ ports.length }})</span>
      </h3>
      
      <!-- Кнопки управления -->
      <div class="grid-controls">
        <v-btn
          v-if="collapsible"
          :icon="isCollapsed ? 'mdi-chevron-down' : 'mdi-chevron-up'"
          size="small"
          variant="text"
          @click="toggleCollapse"
          :title="isCollapsed ? 'Развернуть' : 'Свернуть'"
        ></v-btn>
        
        <v-btn
          :icon="viewMode === 'grid' ? 'mdi-view-list' : 'mdi-view-grid'"
          size="small"
          variant="text"
          @click="toggleViewMode"
          :title="viewMode === 'grid' ? 'Список' : 'Сетка'"
        ></v-btn>
      </div>
    </div>
    
    <!-- Контейнер портов -->
    <v-expand-transition>
      <div v-show="!isCollapsed" class="ports-container" :class="containerClasses">
        <SmartPort
          v-for="port in visiblePorts"
          :key="port.id || port.code"
          :port="port"
          :value="getPortValue(port)"
          :show-code="showPortCodes"
          :show-additional-info="showAdditionalInfo"
          @update="handlePortUpdate"
          class="port-item"
        />
        
        <!-- Сообщение если нет портов -->
        <div v-if="ports.length === 0" class="no-ports-message">
          <v-icon icon="mdi-information-outline" class="mr-2"></v-icon>
          Порты не найдены
        </div>
      </div>
    </v-expand-transition>
    
    <!-- Пагинация для большого количества портов -->
    <div v-if="showPagination" class="grid-pagination">
      <v-pagination
        v-model="currentPage"
        :length="totalPages"
        :total-visible="5"
        size="small"
        variant="outlined"
      ></v-pagination>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, defineProps, defineEmits } from 'vue'
import SmartPort from './SmartPort.vue'

const props = defineProps({
  ports: {
    type: Array,
    default: () => []
  },
  title: {
    type: String,
    default: ''
  },
  collapsible: {
    type: Boolean,
    default: false
  },
  defaultCollapsed: {
    type: Boolean,
    default: false
  },
  showPortCount: {
    type: Boolean,
    default: true
  },
  showPortCodes: {
    type: Boolean,
    default: false
  },
  showAdditionalInfo: {
    type: Boolean,
    default: false
  },
  itemsPerPage: {
    type: Number,
    default: 20
  },
  defaultViewMode: {
    type: String,
    default: 'grid',
    validator: (value) => ['grid', 'list'].includes(value)
  },
  minItemWidth: {
    type: Number,
    default: 200
  },
  maxColumns: {
    type: Number,
    default: 4
  }
})

const emit = defineEmits(['update', 'view-mode-changed'])

// Reactive data
const isCollapsed = ref(props.defaultCollapsed)
const viewMode = ref(props.defaultViewMode)
const currentPage = ref(1)

// Computed properties
const gridClasses = computed(() => ({
  'ports-grid--collapsed': isCollapsed.value,
  [`ports-grid--${viewMode.value}`]: true
}))

const containerClasses = computed(() => ({
  'ports-container--grid': viewMode.value === 'grid',
  'ports-container--list': viewMode.value === 'list'
}))

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

// Methods
const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
}

const toggleViewMode = () => {
  viewMode.value = viewMode.value === 'grid' ? 'list' : 'grid'
  emit('view-mode-changed', viewMode.value)
}

const getPortValue = (port) => {
  return port.val !== undefined ? port.val : port.value
}

const handlePortUpdate = (code, value) => {
  emit('update', code, value)
}
</script>

<style scoped>
.ports-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.grid-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.grid-title {
  font-size: 1.1em;
  font-weight: 600;
  color: #ffffff;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.port-count {
  font-size: 0.8em;
  color: rgba(255, 255, 255, 0.6);
  font-weight: normal;
}

.grid-controls {
  display: flex;
  gap: 4px;
}

.ports-container {
  display: grid;
  gap: 12px;
}

.ports-container--grid {
  grid-template-columns: repeat(auto-fill, minmax(v-bind(minItemWidth + 'px'), 1fr));
  max-grid-columns: v-bind(maxColumns);
}

.ports-container--list {
  grid-template-columns: 1fr;
  gap: 8px;
}

.port-item {
  width: 100%;
}

.no-ports-message {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: rgba(255, 255, 255, 0.5);
  font-style: italic;
  grid-column: 1 / -1;
}

.grid-pagination {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

/* Адаптивные стили */
@media (max-width: 1200px) {
  .ports-container--grid {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  }
}

@media (max-width: 768px) {
  .ports-grid {
    padding: 12px;
  }
  
  .ports-container--grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 8px;
  }
  
  .grid-header {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  
  .grid-controls {
    justify-content: center;
  }
}

@media (max-width: 480px) {
  .ports-container--grid {
    grid-template-columns: 1fr;
  }
  
  .grid-title {
    font-size: 1em;
  }
}

/* Состояния */
.ports-grid--collapsed .grid-header {
  border-bottom: none;
  padding-bottom: 0;
}

/* Анимации */
.port-item {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.port-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

/* Темная тема */
@media (prefers-color-scheme: dark) {
  .ports-grid {
    background: rgba(255, 255, 255, 0.02);
    border-color: rgba(255, 255, 255, 0.05);
  }
}
</style>







