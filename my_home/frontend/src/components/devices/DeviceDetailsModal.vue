<template>
  <v-dialog :model-value="showModal" @update:model-value="$emit('update:showModal', $event)" max-width="900px" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="me-2">mdi-information</v-icon>
        <span v-if="hasLogsModule">Детали бэкапов и логов - {{ deviceName }}</span>
        <span v-else>Детали бэкапов - {{ deviceName }}</span>
      </v-card-title>
      
      <v-card-text style="max-height: 600px;">
        <!-- Показываем табы только если есть и бэкапы, и логи -->
        <div v-if="hasLogsModule">
          <v-tabs :model-value="activeTab" @update:model-value="$emit('update:activeTab', $event)" class="mb-4">
            <v-tab value="backup">Бэкапы</v-tab>
            <v-tab value="logs">Логи</v-tab>
            <v-tab value="ports">Настройка портов</v-tab>
          </v-tabs>
          
          <v-tabs-window :model-value="activeTab">
            <!-- Вкладка бэкапов -->
            <v-tabs-window-item value="backup">
              <BackupSection 
                :device-id="deviceId"
                :backup-history="backupHistory"
                :backup-loading="backupLoading"
                :forced-backup-loading="forcedBackupLoading"
                :loading-history="loadingBackupHistory"
                :backup-status-color="backupStatusColor"
                :backup-status-text="backupStatusText"
                @trigger-backup="$emit('trigger-backup')"
                @trigger-forced-backup="$emit('trigger-forced-backup')"
                @refresh-history="$emit('refresh-backup-history')"
                @download-backup-log="$emit('download-backup-log')"
                @view-backup-log="$emit('view-backup-log')"
                @view-config-file="$emit('view-config-file', $event)"
                @download-config-file="$emit('download-config-file', $event)"
                @notification="$emit('notification', $event)"
              />
            </v-tabs-window-item>
            
            <!-- Вкладка логов -->
            <v-tabs-window-item value="logs">
              <LogsSection 
                :device-id="deviceId"
                :logs-loading="logsLoading"
                :loading-files="loadingLogFiles"
                :logs-status-color="logsStatusColor"
                :logs-status-text="logsStatusText"
                :log-files="logFiles"
                @trigger-logs-export="$emit('trigger-logs-export')"
                @refresh-log-files="$emit('refresh-log-files')"
                @download-log-file="$emit('download-log-file', $event)"
                @view-log-file="$emit('view-log-file', $event)"
                @notification="$emit('notification', $event)"
              />
            </v-tabs-window-item>
            
            <!-- Вкладка настройки портов -->
            <v-tabs-window-item value="ports">
              <PortsSettingsSection 
                :device-id="deviceId"
                :device-data="deviceData"
                :ports-data="portsData"
                :logs-config="logsConfig"
                @update-port-param="$emit('update-port-param', $event)"
                @update-ha-settings="$emit('update-ha-settings', $event)"
                @update-favorite-ports="$emit('update-favorite-ports', $event)"
                @update-logs-config="$emit('update-logs-config', $event)"
                @notification="$emit('notification', $event)"
              />
            </v-tabs-window-item>
          </v-tabs-window>
        </div>
        
        <!-- Если нет модуля логов, показываем только бэкапы без табов -->
        <div v-else>
          <BackupSection 
            :device-id="deviceId"
            :backup-history="backupHistory"
            :backup-loading="backupLoading"
            :forced-backup-loading="forcedBackupLoading"
            :loading-history="loadingBackupHistory"
            :backup-status-color="backupStatusColor"
            :backup-status-text="backupStatusText"
            @trigger-backup="$emit('trigger-backup')"
            @trigger-forced-backup="$emit('trigger-forced-backup')"
            @refresh-history="$emit('refresh-backup-history')"
            @download-backup-log="$emit('download-backup-log')"
            @view-backup-log="$emit('view-backup-log')"
            @view-config-file="$emit('view-config-file', $event)"
            @download-config-file="$emit('download-config-file', $event)"
            @notification="$emit('notification', $event)"
          />
        </div>
      </v-card-text>
      
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn @click="$emit('close')">Закрыть</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import BackupSection from './BackupSection.vue'
import LogsSection from './LogsSection.vue'
import PortsSettingsSection from './PortsSettingsSection.vue'

const props = defineProps({
  showModal: {
    type: Boolean,
    default: false
  },
  deviceId: {
    type: Number,
    required: true
  },
  deviceName: {
    type: String,
    required: true
  },
  hasLogsModule: {
    type: Boolean,
    default: false
  },
  activeTab: {
    type: String,
    default: 'backup'
  },
  // Данные бэкапов
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
  loadingBackupHistory: {
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
  },
  // Данные логов
  logsLoading: {
    type: Boolean,
    default: false
  },
  loadingLogFiles: {
    type: Boolean,
    default: false
  },
  logsStatusColor: {
    type: String,
    default: 'grey'
  },
  logsStatusText: {
    type: String,
    default: ''
  },
  logFiles: {
    type: Array,
    default: () => []
  },
  // Данные портов
  deviceData: {
    type: Object,
    default: () => ({})
  },
  portsData: {
    type: Array,
    default: () => []
  },
  logsConfig: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits([
  'close',
  'update:showModal',
  'update:activeTab',
  'trigger-backup',
  'trigger-forced-backup', 
  'refresh-backup-history',
  'download-backup-log',
  'view-backup-log',
  'view-config-file',
  'download-config-file',
  'trigger-logs-export',
  'refresh-log-files',
  'download-log-file',
  'view-log-file',
  'notification',
  'update-port-param',
  'update-ha-settings',
  'update-favorite-ports',
  'update-logs-config'
])
</script>

<style scoped>
/* Стили будут наследоваться от дочерних компонентов */
</style>
