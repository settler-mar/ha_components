<template>
  <div class="file-list-view">
    <!-- Заголовок группы -->
    <div v-if="title" class="group-header" @click="toggleCollapse">
      <div class="d-flex align-center">
        <v-icon 
          :icon="isCollapsed ? 'mdi-chevron-right' : 'mdi-chevron-down'" 
          size="16" 
          class="me-2"
        ></v-icon>
        
        <v-icon icon="mdi-file-document-multiple" class="me-2"></v-icon>
        
        <span class="font-weight-medium">{{ title }}</span>
        
        <!-- Индикатор обновления группы -->
        <div class="update-indicator-wrapper group-update-wrapper" style="position: relative;">
          <UpdateIndicator 
            :show="showGroupUpdate" 
            :duration="1000"
            title="Список файлов обновлен"
          />
        </div>
        
        <v-chip size="x-small" color="primary" variant="outlined" class="ms-2">
          {{ files.length }}
        </v-chip>
      </div>
    </div>
    
    <!-- Простой список файлов -->
    <v-expand-transition>
      <div v-show="!isCollapsed" class="files-content">
        <div class="simple-files-list">
          <div 
            v-for="(file, index) in files" 
            :key="index" 
            class="file-item"
          >
            {{ getFileName(file) }}
          </div>
          
          <!-- Сообщение если нет файлов -->
          <div v-if="files.length === 0" class="no-files-message">
            Файлы не найдены
          </div>
        </div>
      </div>
    </v-expand-transition>
  </div>
</template>

<script setup>
import { ref, computed, defineProps, defineEmits } from 'vue'
import UpdateIndicator from '@/components/UpdateIndicator.vue'

const props = defineProps({
  files: {
    type: Array,
    default: () => []
  },
  title: {
    type: String,
    default: 'Файлы'
  },
  collapsible: {
    type: Boolean,
    default: true
  },
  defaultCollapsed: {
    type: Boolean,
    default: false
  },
  showGroupUpdate: {
    type: Boolean,
    default: false
  },
  baseUrl: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['download'])

// Reactive data
const isCollapsed = ref(props.defaultCollapsed)

// Methods
const toggleCollapse = () => {
  if (props.collapsible) {
    isCollapsed.value = !isCollapsed.value
  }
}

const getFileName = (filePath) => {
  if (typeof filePath === 'string') {
    return filePath.split('/').pop() || filePath
  }
  return filePath
}

const getFileIcon = (filePath) => {
  const fileName = getFileName(filePath).toLowerCase()
  
  if (fileName.endsWith('.txt')) return 'mdi-file-document'
  if (fileName.endsWith('.log')) return 'mdi-file-document-outline'
  if (fileName.endsWith('.json')) return 'mdi-code-json'
  if (fileName.endsWith('.csv')) return 'mdi-file-delimited'
  
  return 'mdi-file'
}

const getFileColor = (filePath) => {
  const fileName = getFileName(filePath).toLowerCase()
  
  if (fileName.endsWith('.txt')) return 'blue'
  if (fileName.endsWith('.log')) return 'green'
  if (fileName.endsWith('.json')) return 'orange'
  if (fileName.endsWith('.csv')) return 'purple'
  
  return 'grey'
}

// Файлы отображаются только для просмотра, без скачивания
</script>

<style scoped>
.file-list-view {
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

.files-content {
  background-color: #fafafa;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.simple-files-list {
  padding: 8px 12px;
}

.file-item {
  padding: 4px 0;
  font-size: 0.85em;
  font-family: monospace;
  color: #333;
}

.no-files-message {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: rgba(0, 0, 0, 0.5);
  font-style: italic;
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
  
  .file-name {
    font-size: 0.8em;
  }
}
</style>
