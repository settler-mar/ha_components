<template>
  <v-card variant="outlined" class="mb-4">
    <!-- Шапка с кнопками -->
    <v-card-title class="text-subtitle-1 d-flex align-center justify-space-between">
      <span>Файл запусков: backup.log</span>
      <div>
        <v-btn size="x-small" variant="outlined" @click="$emit('refresh')" :loading="loading" class="me-1">
          <v-icon size="12">mdi-refresh</v-icon>
        </v-btn>
        <v-btn size="x-small" variant="outlined" @click="$emit('download')" class="me-1">
          <v-icon size="12">mdi-download</v-icon>
        </v-btn>
        <v-btn size="x-small" variant="outlined" @click="$emit('view')">
          <v-icon size="12">mdi-eye</v-icon>
        </v-btn>
      </div>
    </v-card-title>
    
    <!-- Блок с записями (новые выше) -->
    <v-card-text>
      <div v-if="backupHistory.length" class="backup-history">
        <div v-for="entry in sortedBackupHistory" :key="entry.timestamp" class="backup-event">
          <!-- Дата события -->
          <div class="event-header d-flex align-center mb-2">
            <v-icon size="16" color="primary" class="me-2">mdi-clock</v-icon>
            <span class="text-body-1 font-weight-medium">{{ formatTimestamp(entry.timestamp) }}</span>
          </div>
          
          <!-- Список файлов с кнопками -->
          <div class="event-files ms-6">
            <div v-if="entry.changed_files.length" class="files-list">
              <div v-for="file in entry.changed_files" :key="file" class="file-item d-flex align-center justify-space-between py-1">
                <div class="d-flex align-center">
                  <v-icon size="14" color="blue" class="me-2">mdi-file-code</v-icon>
                  <span class="text-body-2">{{ file }}</span>
                </div>
                <div>
                  <v-btn size="x-small" variant="outlined" @click="viewConfigFile(file, entry.timestamp)" class="me-1">
                    <v-icon size="10">mdi-eye</v-icon>
                  </v-btn>
                  <v-btn size="x-small" variant="outlined" @click="downloadConfigFile(file, entry.timestamp)">
                    <v-icon size="10">mdi-download</v-icon>
                  </v-btn>
                </div>
              </div>
            </div>
            <div v-else class="text-caption text-grey">
              Нет изменений
            </div>
          </div>
        </div>
      </div>
      <div v-else class="text-grey text-center py-4">
        История бэкапов пуста
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import {computed} from 'vue'

const props = defineProps({
  deviceId: {
    type: Number,
    required: true
  },
  backupHistory: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['refresh', 'download', 'view', 'view-config-file', 'download-config-file'])

// Сортируем историю - новые записи сверху
const sortedBackupHistory = computed(() => {
  return [...props.backupHistory].sort((a, b) => {
    const dateA = new Date(a.timestamp)
    const dateB = new Date(b.timestamp)
    return dateB - dateA // Убывающий порядок (новые сверху)
  })
})

// Форматирование временной метки
const formatTimestamp = (timestamp) => {
  try {
    let date
    if (timestamp.includes('T')) {
      date = new Date(timestamp)
    } else if (timestamp.includes('-') && timestamp.includes(':')) {
      date = new Date(timestamp.replace(' ', 'T'))
    } else {
      date = new Date(timestamp)
    }
    
    if (isNaN(date.getTime())) {
      return timestamp
    }
    
    return date.toLocaleString('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch (error) {
    return timestamp
  }
}

const viewConfigFile = (filename, timestamp) => {
  emit('view-config-file', { filename, timestamp })
}

const downloadConfigFile = (filename, timestamp) => {
  emit('download-config-file', { filename, timestamp })
}
</script>

<style scoped>
.backup-history {
  max-height: 400px;
  overflow-y: auto;
}

.backup-event {
  border-left: 3px solid #e3f2fd;
  padding-left: 12px;
  margin-bottom: 16px;
  background-color: #fafafa;
  border-radius: 4px;
  padding: 12px;
}

.backup-event:last-child {
  margin-bottom: 0;
}

.event-header {
  border-bottom: 1px solid #e0e0e0;
  padding-bottom: 8px;
}

.files-list {
  margin-top: 8px;
}

.file-item {
  border-radius: 4px;
  padding: 4px 8px;
  background-color: white;
  border: 1px solid #e0e0e0;
  margin-bottom: 4px;
}

.file-item:last-child {
  margin-bottom: 0;
}

.file-item:hover {
  background-color: #f5f5f5;
}
</style>







