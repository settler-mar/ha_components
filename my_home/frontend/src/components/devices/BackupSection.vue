<template>
  <div class="mb-4">
    <h3 class="text-h6 mb-2">История бэкапов</h3>
    <div class="d-flex align-center mb-3">
      <v-chip size="small" :color="backupStatusColor" variant="tonal" class="me-2">
        {{ backupStatusText }}
      </v-chip>
      <v-spacer></v-spacer>
      <v-btn size="small" @click="$emit('trigger-backup')" :loading="backupLoading" class="me-2">
        <v-icon size="16" class="me-1">mdi-backup-restore</v-icon>
        Бэкап изменений
      </v-btn>
      <v-btn size="small" variant="outlined" @click="$emit('trigger-forced-backup')" :loading="forcedBackupLoading">
        <v-icon size="16" class="me-1">mdi-backup-restore</v-icon>
        Полный бэкап
      </v-btn>
    </div>
    
    <!-- Табы для разных разделов бэкапов -->
    <v-tabs v-model="backupTab" class="mb-4">
      <v-tab value="history">Файл запусков</v-tab>
      <v-tab value="configs">Файлы конфигураций</v-tab>
    </v-tabs>
    
    <v-tabs-window v-model="backupTab">
      <!-- Вкладка истории запусков -->
      <v-tabs-window-item value="history">
        <BackupHistoryView 
          :device-id="deviceId"
          :backup-history="backupHistory"
          :loading="loadingHistory"
          @refresh="$emit('refresh-history')"
          @download="$emit('download-backup-log')"
          @view="$emit('view-backup-log')"
          @view-config-file="$emit('view-config-file', $event)"
          @download-config-file="$emit('download-config-file', $event)"
          @notification="$emit('notification', $event)"
        />
      </v-tabs-window-item>
      
      <!-- Вкладка файлов конфигураций -->
      <v-tabs-window-item value="configs">
        <ConfigFilesManager 
          :device-id="deviceId"
          @notification="$emit('notification', $event)"
        />
      </v-tabs-window-item>
    </v-tabs-window>
  </div>
</template>

<script setup>
import {ref} from 'vue'
import BackupHistoryView from './BackupHistoryView.vue'
import ConfigFilesManager from './ConfigFilesManager.vue'

// Состояние табов
const backupTab = ref('history')

const props = defineProps({
  deviceId: {
    type: Number,
    required: true
  },
  backupHistory: {
    type: Array,
    default: () => []
  },
  backupLoading: {
    type: Boolean,
    default: false
  },
  forcedBackupLoading: {
    type: Boolean,
    default: false
  },
  loadingHistory: {
    type: Boolean,
    default: false
  },
  backupStatusColor: {
    type: String,
    default: 'grey'
  },
  backupStatusText: {
    type: String,
    default: ''
  }
})

const emit = defineEmits([
  'trigger-backup',
  'trigger-forced-backup',
  'refresh-history',
  'download-backup-log',
  'view-backup-log',
  'view-config-file',
  'download-config-file',
  'notification'
])
</script>

<style scoped>
/* Стили наследуются от дочерних компонентов */
</style>
