<template>
  <v-container>
    <v-row>
      <v-col cols="12">
        <v-card elevation="2">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-cog</v-icon>
            Бэкапы конфигураций устройств
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
            <!-- Бэкапы конфигураций устройств -->
            <div v-if="systemBackupInfo" class="mb-6">
              <h2 class="text-h5 mb-3 d-flex align-center">
                <v-icon class="mr-2" color="primary">mdi-cog</v-icon>
                Бэкапы конфигураций устройств
              </h2>
              
              <div v-if="systemBackupInfo.device_config_backups.length > 0">
                <v-row>
                  <v-col
                    v-for="deviceBackup in systemBackupInfo.device_config_backups"
                    :key="deviceBackup.device_id"
                    cols="12"
                    md="6"
                    lg="4"
                  >
                    <v-card variant="outlined" class="h-100">
                      <v-card-title class="text-subtitle-1">
                        <v-icon class="mr-2">mdi-memory</v-icon>
                        {{ deviceBackup.device_name }}
                      </v-card-title>
                      
                      <v-card-text>
                        <div class="d-flex justify-space-between align-center mb-1">
                          <span class="text-body-2">ID устройства:</span>
                          <v-chip size="small" color="info">{{ deviceBackup.device_id }}</v-chip>
                        </div>
                        
                        <div class="d-flex justify-space-between align-center mb-1">
                          <span class="text-body-2">Последний бэкап:</span>
                          <span class="text-caption">{{ deviceBackup.backup_time }}</span>
                        </div>
                        
                        <div class="d-flex justify-space-between align-center mb-1">
                          <span class="text-body-2">Всего бэкапов:</span>
                          <span class="text-caption">{{ deviceBackup.total_backups }}</span>
                        </div>
                        
                        <div class="d-flex justify-space-between align-center mb-1">
                          <span class="text-body-2">Файлов:</span>
                          <span class="text-caption">{{ deviceBackup.files_count }}</span>
                        </div>
                        
                        <div class="d-flex justify-space-between align-center">
                          <span class="text-body-2">Размер:</span>
                          <span class="text-caption">{{ formatBytes(deviceBackup.total_size) }}</span>
                        </div>
                      </v-card-text>
                      
                      <v-card-actions>
                        <v-btn
                          size="small"
                          variant="outlined"
                          color="info"
                          @click="viewDeviceBackups(deviceBackup.device_id)"
                        >
                          Подробнее
                        </v-btn>
                      </v-card-actions>
                    </v-card>
                  </v-col>
                </v-row>
              </div>
              
              <div v-else class="text-center text-disabled py-4">
                <v-icon size="48" class="mb-2">mdi-folder-open-outline</v-icon>
                <div>Бэкапы конфигураций устройств не найдены</div>
              </div>
            </div>
            
            <div v-else class="text-center text-disabled py-8">
              <v-progress-circular indeterminate class="mb-2"></v-progress-circular>
              <div>Загрузка информации о системных бэкапах...</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Диалог подробной информации о бэкапах устройства -->
    <v-dialog v-model="deviceBackupDialog" max-width="1000px">
      <v-card>
        <v-card-title>
          Бэкапы конфигурации устройства
          <v-spacer></v-spacer>
          <v-btn icon="mdi-close" variant="text" @click="deviceBackupDialog = false"></v-btn>
        </v-card-title>
        
        <v-card-text>
          <div v-if="selectedDeviceBackups">
            <div class="mb-4">
              <h3 class="text-h6">{{ selectedDeviceBackups.device_name }}</h3>
              <p class="text-body-2 text-medium-emphasis">{{ selectedDeviceBackups.description }}</p>
            </div>
            
            <div v-if="selectedDeviceBackups.backups.length > 0">
              <v-expansion-panels variant="accordion">
                <v-expansion-panel
                  v-for="backup in selectedDeviceBackups.backups"
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
          </div>
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { secureFetch } from '@/services/fetch'

// Reactive data
const loading = ref(false)
const systemBackupInfo = ref(null)
const selectedDeviceBackups = ref(null)
const deviceBackupDialog = ref(false)

// Methods
const refreshData = async () => {
  loading.value = true
  try {
    await loadSystemBackupInfo()
  } finally {
    loading.value = false
  }
}

const loadSystemBackupInfo = async () => {
  try {
    const response = await secureFetch('/api/system/backup/status')
    if (response.success) {
      systemBackupInfo.value = response
    }
  } catch (error) {
    console.error('Error loading system backup info:', error)
  }
}

const viewDeviceBackups = async (deviceId) => {
  try {
    const response = await secureFetch(`/api/devices/${deviceId}/config-backup/status`)
    if (response.success) {
      selectedDeviceBackups.value = response
      deviceBackupDialog.value = true
    }
  } catch (error) {
    console.error('Error loading device backup details:', error)
  }
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
.v-card {
  height: 100%;
}

.text-body-2 {
  font-weight: 500;
}
</style>
