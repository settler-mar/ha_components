<template>
  <v-card class="logs-backup-manager" elevation="2">
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-database-export</v-icon>
      Логи и Бэкапы
      <v-spacer></v-spacer>
      <v-btn 
        icon="mdi-refresh" 
        size="small" 
        variant="text"
        @click="refreshData"
        :loading="loading"
      ></v-btn>
    </v-card-title>

    <v-card-text>
      <div class="d-flex gap-2 flex-wrap">
        <!-- Кнопки логов -->
        <v-btn
          color="primary"
          variant="outlined"
          prepend-icon="mdi-export"
          @click="exportLogs"
          :loading="exportingLogs"
          :disabled="!logsStatus?.google_available"
          size="small"
        >
          Экспорт логов
        </v-btn>
        
        <v-btn
          color="info"
          variant="outlined"
          prepend-icon="mdi-text-box"
          @click="showLogsInfo"
          size="small"
        >
          Логи
        </v-btn>
        
        <!-- Кнопки бэкапов -->
        <v-btn
          color="primary"
          variant="outlined"
          prepend-icon="mdi-backup-restore"
          @click="createConfigBackup"
          :loading="creatingBackup"
          size="small"
        >
          Создать бэкап
        </v-btn>
        
        <v-btn
          color="info"
          variant="outlined"
          prepend-icon="mdi-cog"
          @click="showBackupInfo"
          size="small"
        >
          Бэкапы
        </v-btn>
      </div>
    </v-card-text>

    <!-- Диалог истории логов -->
    <v-dialog v-model="logsHistoryDialog" max-width="800px">
      <v-card>
        <v-card-title>
          История логов устройства
          <v-spacer></v-spacer>
          <v-btn icon="mdi-close" variant="text" @click="logsHistoryDialog = false"></v-btn>
        </v-card-title>
        
        <v-card-text>
          <div v-if="logsHistory.length > 0">
            <v-data-table
              :headers="logsHistoryHeaders"
              :items="logsHistory"
              :items-per-page="10"
              class="elevation-1"
            >
              <template v-slot:item.size="{ item }">
                {{ formatBytes(item.size) }}
              </template>
              
              <template v-slot:item.content="{ item }">
                <v-btn
                  size="small"
                  variant="outlined"
                  @click="showLogContent(item)"
                >
                  Просмотр
                </v-btn>
              </template>
            </v-data-table>
          </div>
          <div v-else class="text-center text-disabled py-4">
            История логов пуста
          </div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- Диалог истории бэкапов -->
    <v-dialog v-model="backupHistoryDialog" max-width="1000px">
      <v-card>
        <v-card-title>
          История бэкапов конфигурации
          <v-spacer></v-spacer>
          <v-btn icon="mdi-close" variant="text" @click="backupHistoryDialog = false"></v-btn>
        </v-card-title>
        
        <v-card-text>
          <div v-if="configBackupStatus?.backups.length > 0">
            <v-expansion-panels variant="accordion">
              <v-expansion-panel
                v-for="backup in configBackupStatus.backups"
                :key="backup.name"
              >
                <v-expansion-panel-title>
                  <div class="d-flex justify-space-between align-center w-100">
                    <span class="font-weight-medium">{{ backup.name }}</span>
                    <div class="text-caption text-medium-emphasis">
                      {{ backup.timestamp }} • {{ backup.files_count }} файлов • {{ formatBytes(backup.total_size) }}
                    </div>
                  </div>
                </v-expansion-panel-title>
                
                <v-expansion-panel-text>
                  <v-list density="compact">
                    <v-list-item
                      v-for="file in backup.files"
                      :key="file.name"
                    >
                      <template v-slot:prepend>
                        <v-icon>mdi-file</v-icon>
                      </template>
                      
                      <v-list-item-title>{{ file.name }}</v-list-item-title>
                      
                      <template v-slot:append>
                        <div class="text-caption text-medium-emphasis">
                          {{ formatBytes(file.size) }} • {{ file.modified }}
                        </div>
                      </template>
                    </v-list-item>
                  </v-list>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </div>
          <div v-else class="text-center text-disabled py-4">
            История бэкапов пуста
          </div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- Диалог содержимого лога -->
    <v-dialog v-model="logContentDialog" max-width="800px">
      <v-card>
        <v-card-title>
          Содержимое лога: {{ selectedLog?.log_name }}
          <v-spacer></v-spacer>
          <v-btn icon="mdi-close" variant="text" @click="logContentDialog = false"></v-btn>
        </v-card-title>
        
        <v-card-text>
          <pre class="log-content">{{ selectedLog?.content }}</pre>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- Диалог информации о логах -->
    <v-dialog v-model="logsInfoDialog" max-width="600px">
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">mdi-text-box</v-icon>
          Информация о логах
          <v-spacer></v-spacer>
          <v-btn icon="mdi-close" variant="text" @click="logsInfoDialog = false"></v-btn>
        </v-card-title>
        
        <v-card-text>
          <div v-if="logsStatus">
            <div class="d-flex justify-space-between align-center mb-2">
              <span class="text-subtitle-2">Последняя выгрузка:</span>
              <span v-if="logsStatus.last_export" class="text-body-2">
                {{ logsStatus.last_export.timestamp }}
                ({{ logsStatus.last_export.logs_count }} логов)
              </span>
              <span v-else class="text-body-2 text-disabled">Нет данных</span>
            </div>
            
            <div class="d-flex justify-space-between align-center mb-2">
              <span class="text-subtitle-2">Google Sheets:</span>
              <v-chip 
                :color="logsStatus.gsheet_config.enabled ? 'success' : 'default'"
                size="small"
              >
                {{ logsStatus.gsheet_config.enabled ? 'Включен' : 'Отключен' }}
              </v-chip>
            </div>
            
            <div class="d-flex justify-space-between align-center mb-2">
              <span class="text-subtitle-2">Всего логов в БД:</span>
              <span class="text-body-2">{{ logsStatus.total_logs_in_db }}</span>
            </div>
            
            <div v-if="logsStatus.local_logs" class="d-flex justify-space-between align-center mb-2">
              <span class="text-subtitle-2">Локальные файлы:</span>
              <span class="text-body-2">
                {{ logsStatus.local_logs.timestamp }}
                ({{ logsStatus.local_logs.files_count }} файлов)
              </span>
            </div>
          </div>
          
          <div v-else class="text-center text-disabled">
            Загрузка информации о логах...
          </div>
        </v-card-text>
        
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            color="info"
            variant="outlined"
            prepend-icon="mdi-history"
            @click="showLogsHistory(); logsInfoDialog = false"
          >
            История логов
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Диалог информации о бэкапах -->
    <v-dialog v-model="backupInfoDialog" max-width="600px">
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">mdi-cog</v-icon>
          Информация о бэкапах
          <v-spacer></v-spacer>
          <v-btn icon="mdi-close" variant="text" @click="backupInfoDialog = false"></v-btn>
        </v-card-title>
        
        <v-card-text>
          <div v-if="configBackupStatus">
            <div class="d-flex justify-space-between align-center mb-2">
              <span class="text-subtitle-2">Всего бэкапов:</span>
              <span class="text-body-2">{{ configBackupStatus.backups.length }}</span>
            </div>
            
            <div v-if="configBackupStatus.backups.length > 0" class="d-flex justify-space-between align-center mb-2">
              <span class="text-subtitle-2">Последний бэкап:</span>
              <span class="text-body-2">
                {{ configBackupStatus.backups[0].timestamp }}
                ({{ configBackupStatus.backups[0].files_count }} файлов)
              </span>
            </div>
            
            <div class="d-flex justify-space-between align-center mb-2">
              <span class="text-subtitle-2">Тип:</span>
              <span class="text-body-2">{{ configBackupStatus.backup_type }}</span>
            </div>
            
            <p class="text-body-2 text-medium-emphasis mt-3">
              {{ configBackupStatus.description }}
            </p>
          </div>
          
          <div v-else class="text-center text-disabled">
            Загрузка информации о бэкапах...
          </div>
        </v-card-text>
        
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            color="info"
            variant="outlined"
            prepend-icon="mdi-history"
            @click="showBackupHistory(); backupInfoDialog = false"
          >
            История бэкапов
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, onMounted, defineProps } from 'vue'
import { secureFetch } from '@/services/fetch'

const props = defineProps({
  deviceId: {
    type: Number,
    required: true
  }
})

// Reactive data
const loading = ref(false)
const exportingLogs = ref(false)
const creatingBackup = ref(false)
const logsStatus = ref(null)
const configBackupStatus = ref(null)
const logsHistory = ref([])
const selectedLog = ref(null)

// Dialogs
const logsHistoryDialog = ref(false)
const backupHistoryDialog = ref(false)
const logContentDialog = ref(false)
const logsInfoDialog = ref(false)
const backupInfoDialog = ref(false)

// Table headers
const logsHistoryHeaders = [
  { title: 'Название', key: 'log_name' },
  { title: 'Время', key: 'timestamp' },
  { title: 'Размер', key: 'size' },
  { title: 'Действие', key: 'content', sortable: false }
]

// Methods
const refreshData = async () => {
  loading.value = true
  try {
    await Promise.all([
      loadLogsStatus(),
      loadConfigBackupStatus()
    ])
  } finally {
    loading.value = false
  }
}

const loadLogsStatus = async () => {
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/logs/status`)
    if (response.success) {
      logsStatus.value = response
    }
  } catch (error) {
    console.error('Error loading logs status:', error)
  }
}

const loadConfigBackupStatus = async () => {
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/config-backup/status`)
    if (response.success) {
      configBackupStatus.value = response
    }
  } catch (error) {
    console.error('Error loading config backup status:', error)
  }
}

const exportLogs = async () => {
  exportingLogs.value = true
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/logs/export`, {
      method: 'POST'
    })
    
    if (response.success) {
      // Обновляем данные через некоторое время
      setTimeout(loadLogsStatus, 2000)
    }
  } catch (error) {
    console.error('Error exporting logs:', error)
  } finally {
    exportingLogs.value = false
  }
}

const createConfigBackup = async () => {
  creatingBackup.value = true
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/config-backup/create`, {
      method: 'POST'
    })
    
    if (response.success) {
      // Обновляем данные через некоторое время
      setTimeout(loadConfigBackupStatus, 2000)
    }
  } catch (error) {
    console.error('Error creating config backup:', error)
  } finally {
    creatingBackup.value = false
  }
}

const showLogsHistory = async () => {
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/logs/history?limit=100`)
    if (response.success) {
      logsHistory.value = response.logs
      logsHistoryDialog.value = true
    }
  } catch (error) {
    console.error('Error loading logs history:', error)
  }
}

const showBackupHistory = () => {
  backupHistoryDialog.value = true
}

const showLogsInfo = () => {
  logsInfoDialog.value = true
}

const showBackupInfo = () => {
  backupInfoDialog.value = true
}

const showLogContent = (log) => {
  selectedLog.value = log
  logContentDialog.value = true
}

const formatBytes = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// Lifecycle
onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.logs-backup-manager {
  margin-bottom: 16px;
}

.log-content {
  max-height: 400px;
  overflow-y: auto;
  background-color: #f5f5f5;
  padding: 16px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
}

.text-subtitle-2 {
  font-weight: 500;
}
</style>
