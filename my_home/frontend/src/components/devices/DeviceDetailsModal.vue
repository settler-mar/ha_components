<template>
  <v-dialog :model-value="showModal" @update:model-value="$emit('update:showModal', $event)" max-width="900px" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="me-2">mdi-information</v-icon>
        <span v-if="hasLogsModule">Детали бэкапов и логов - {{ deviceName }}</span>
        <span v-else>Детали бэкапов - {{ deviceName }}</span>
      </v-card-title>
      
      <v-card-text style="max-height: 600px;">
        <!-- Всегда показываем табы -->
        <v-tabs :model-value="activeTab" @update:model-value="$emit('update:activeTab', $event)" class="mb-4">
          <v-tab value="settings">Настройки</v-tab>
          <v-tab value="backup">Бэкапы</v-tab>
          <v-tab value="logs" v-if="hasLogsModule">Логи</v-tab>
          <v-tab value="ports">Настройка портов</v-tab>
          <v-tab value="options" v-if="hasOptionsOrConfig">Options/Config</v-tab>
          <v-tab value="info">Информация</v-tab>
        </v-tabs>
        
        <v-tabs-window :model-value="activeTab">
          <!-- Вкладка настроек устройства -->
          <v-tabs-window-item value="settings">
            <DeviceSettingsSection 
              :device-id="deviceId"
              :device="device"
              :custom-params="customParams"
              @saved="$emit('device-saved')"
              @device-updated="$emit('device-updated', $event)"
            />
          </v-tabs-window-item>
          
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
          <v-tabs-window-item value="logs" v-if="hasLogsModule">
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
          
          <!-- Вкладка Options/Config -->
          <v-tabs-window-item value="options" v-if="hasOptionsOrConfig">
            <OptionsConfigSection 
              :ports-data="portsData"
            />
          </v-tabs-window-item>
          
          <!-- Вкладка информации об устройстве -->
          <v-tabs-window-item value="info">
            <DeviceInfoSection 
              :device-info="deviceInfo"
              :loading="loadingDeviceInfo"
              @load-info="$emit('load-device-info')"
            />
          </v-tabs-window-item>
        </v-tabs-window>
      </v-card-text>
      
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn @click="$emit('close')">Закрыть</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { watch, computed } from 'vue'
import BackupSection from './BackupSection.vue'
import LogsSection from './LogsSection.vue'
import PortsSettingsSection from './PortsSettingsSection.vue'
import DeviceInfoSection from './DeviceInfoSection.vue'
import OptionsConfigSection from './OptionsConfigSection.vue'
import DeviceSettingsSection from './DeviceSettingsSection.vue'

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
  },
  deviceInfo: {
    type: Object,
    default: () => null
  },
  loadingDeviceInfo: {
    type: Boolean,
    default: false
  },
  device: {
    type: Object,
    default: () => ({})
  },
  customParams: {
    type: Object,
    default: () => ({})
  }
})

const hasOptionsOrConfig = computed(() => {
  if (!props.portsData || !Array.isArray(props.portsData)) return false
  return props.portsData.some(port => port.mode === 'options' || port.mode === 'config')
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
  'update-logs-config',
  'load-device-info',
  'device-saved',
  'device-updated'
])

// Загружаем информацию об устройстве при открытии модалки
watch(() => props.showModal, (newVal) => {
  if (newVal && props.activeTab === 'info') {
    // Всегда загружаем при открытии, даже если данные уже есть (для обновления)
    emit('load-device-info')
  }
  if (newVal && props.activeTab === 'logs') {
    // Загружаем файлы логов при открытии модалки на вкладке логов
    emit('refresh-log-files')
  }
})

watch(() => props.activeTab, (newTab) => {
  if (newTab === 'info') {
    // Загружаем информацию при переключении на вкладку "Информация"
    emit('load-device-info')
  }
  if (newTab === 'logs') {
    // Загружаем файлы логов при переключении на вкладку "Логи"
    emit('refresh-log-files')
  }
})
</script>

<style scoped>
/* Стили будут наследоваться от дочерних компонентов */
</style>