<template>
  <v-card class="mb-2 device-card" elevation="1">
    <v-toolbar density="compact" :elevation="1" border>
      📟 {{ device.name }}
      <v-chip density="comfortable" size="x-small" color="info">id: {{ device.id }}</v-chip>
      
      <!-- Индикация обновления устройства -->
      <div class="update-indicator-wrapper device-update-wrapper">
        <UpdateIndicator 
          :show="deviceUpdated" 
          :duration="1000"
          title="Данные обновлены"
          class="device-update"
        />
      </div>
      <!--      {{device.online ?1 :0}}-->
      <v-chip
        v-if="isDeviceOnline"
        density="comfortable"
        size="x-small"
        color="success"
      >online
      </v-chip>
      <v-chip
        v-else
        density="comfortable"
        size="x-small"
        color="error"
      >offline
      </v-chip>
      
      <!-- Индикация Home Assistant -->
              <v-chip
                v-if="haIntegrationEnabled"
                density="comfortable"
                size="x-small"
                color="grey"
                variant="outlined"
              >
                <v-icon size="12" class="me-1">mdi-home-assistant</v-icon>
                HA
              </v-chip>

      <ActionHandler
        :actions="actions"
        :params="{device_id: device.id, ...device, ...(device?.params || {})}"
      >
        <v-btn icon v-if="!readonly" @click="$emit('edit', device)">
          <v-icon size="18" icon="mdi-pencil"/>
        </v-btn>
      </ActionHandler>
    </v-toolbar>

    <!-- Информационная строка с бэкапами и логами -->
    <div class="info-line">
      <v-divider class="mb-1"></v-divider>
      <div class="d-flex align-center justify-space-between text-caption text-grey-darken-1 px-4 py-2">
        <div class="d-flex align-center">
          <!-- Статус бэкапа -->
          <div class="d-flex align-center me-4">
            <v-icon size="14" class="me-1" :color="backupStatusColor">mdi-backup-restore</v-icon>
            <span class="me-2">{{ backupStatusText }}</span>
            <v-btn size="x-small" variant="outlined" @click="triggerManualBackup" :loading="backupLoading">
              <v-icon size="12">mdi-play</v-icon>
            </v-btn>
          </div>
          
          <!-- Статус логов (если есть модуль логов) -->
          <div v-if="hasLogsModule" class="d-flex align-center me-4">
            <v-icon size="14" class="me-1" :color="logsStatusColor">mdi-file-document</v-icon>
            <span class="me-2">{{ logsStatusText }}</span>
            <v-btn size="x-small" variant="outlined" @click="triggerManualLogsExport" :loading="logsLoading">
              <v-icon size="12">mdi-play</v-icon>
            </v-btn>
          </div>
        </div>
        
        <!-- Кнопка деталей -->
        <v-btn size="small" variant="outlined" @click="showDetailsModal = true">
          <v-icon size="14" class="me-1">mdi-information</v-icon>
          Детали
        </v-btn>
      </div>
      <v-divider class="mt-1"></v-divider>
    </div>

    <v-row
      v-if="false"
      dense
      align="center"
      class="px-2 py-1"
      style="background-color: #f5f5f5; min-height: 32px; font-size: 13px; color: #555;"
    >

      <v-spacer/>
      <v-col cols="auto" class="d-flex align-center">
        <v-tooltip location="top" text="test tooltip">
          <template v-slot:activator="{ props }">
            <div v-bind="props" class="d-flex align-center">
              <v-icon size="18" icon="mdi-information-outline"/>
              <span class="ml-1">aaa</span>
            </div>
          </template>
        </v-tooltip>
      </v-col>
    </v-row>

    <v-card-text class="device-content">
      <v-row v-if="device.description">
        <v-col cols="12">
          {{ device.description }}
        </v-col>
        </v-row>
 
        <!-- Система отображения портов -->
      <div>
        <!-- Обработка разных типов групп -->
        <template v-for="group in processedGroups" :key="group.title">
          <!-- Группа файлов (логи) -->
          <FileListView
            v-if="group.type === 'file_list'"
            :title="group.title"
            :files="group.values || []"
            :collapsible="true"
            :show-group-update="updatedGroups.has(group.title)"
            class="mb-2"
          />
          
          <!-- Табличный шаблон -->
          <TableTemplateView
            v-else-if="group.tpl === 'table'"
            :title="group.title"
            :ports="group.items"
            :group-icon="getGroupIcon(group)"
            :collapsible="true"
            :show-ha-checkboxes="haConfigMode && haIntegrationEnabled"
            :show-group-update="updatedGroups.has(group.title)"
            :updated-ports="updatedPorts"
            @update="handlePortUpdate"
            @ha-toggle-port="togglePortPublishing"
            @ha-toggle-group="(ports, value) => toggleGroupPublishing({...group, items: ports}, value)"
            class="mb-2"
          />
          
          <!-- Обычные порты -->
          <PortsTable
            v-else
            :title="group.title"
            :ports="group.items"
            :group-icon="getGroupIcon(group)"
            :collapsible="true"
            :show-ha-checkboxes="haConfigMode && haIntegrationEnabled"
            :show-edit-buttons="false"
            :show-group-update="updatedGroups.has(group.title)"
            :updated-ports="updatedPorts"
            @update="handlePortUpdate"
            @ha-toggle-port="togglePortPublishing"
            @ha-toggle-group="(ports, value) => toggleGroupPublishing({...group, items: ports}, value)"
            class="mb-2"
          />
        </template>
      </div>
    </v-card-text>




    <!-- Диалог управления options/config -->
    <v-dialog v-model="editOptionsDialog" max-width="600px">
      <v-card>
        <v-tabs v-model="optionsTab" background-color="primary" dark>
          <v-tab v-if="optionsPorts.length" value="options">Options</v-tab>
          <v-tab v-if="configPorts.length" value="config">Config</v-tab>
        </v-tabs>
        <v-tabs-window v-model="optionsTab">
          <v-tabs-window-item value="options" v-if="optionsPorts.length">
            <v-card-text>
              <table>
                <tr v-for="port in optionsPorts" :key="port.id">
                  <td>
                    <v-tooltip location="top">
                      <template #activator="{ props }">
                        <div v-bind="props" class="d-flex align-center">
                          <span>{{ port.label || port.name }}</span>
                        </div>
                      </template>
                      {{ port.description || '' }}
                    </v-tooltip>
                  </td>
                  <td class="py-1 text-right">
                    <span class="ml-1">{{ getPortValue(port) }}</span>
                  </td>
                </tr>
              </table>
            </v-card-text>
          </v-tabs-window-item>
          <v-tabs-window-item value="config" v-if="configPorts.length">
            <v-card-text>
              <table>
                <tr v-for="port in configPorts" :key="port.id">
                  <td>
                    <v-tooltip location="top">
                      <template #activator="{ props }">
                        <div v-bind="props" class="d-flex align-center">
                          <span>{{ port.label || port.name }}</span>
                        </div>
                      </template>
                      {{ port.description || '' }}
                    </v-tooltip>
                  </td>
                  <td class="py-1 text-right">
                    <span class="ml-1">{{ getPortValue(port) }}</span>
                  </td>
                </tr>
              </table>
            </v-card-text>
          </v-tabs-window-item>
        </v-tabs-window>


        <v-card-actions>
          <v-spacer></v-spacer>

          <v-btn
            text="Close"
            @click="editOptionsDialog = false"
          ></v-btn>
        </v-card-actions>
      </v-card>

    </v-dialog>

    <!-- Унифицированная модалка деталей -->
    <DeviceDetailsModal 
      v-model:show-modal="showDetailsModal"
      :device-id="props.device.id"
      :device-name="device.name"
      :has-logs-module="hasLogsModule"
      v-model:active-tab="detailsTab"
      :backup-history="backupHistory"
      :backup-loading="backupLoading"
      :forced-backup-loading="forcedBackupLoading"
      :loading-backup-history="loadingBackupHistory"
      :backup-status-color="backupStatusColor"
      :backup-status-text="backupStatusText"
      :logs-loading="logsLoading"
      :loading-log-files="loadingLogFiles"
      :logs-status-color="logsStatusColor"
      :logs-status-text="logsStatusText"
      :device-data="currentDeviceData"
      :ports-data="flattenedPorts"
      :logs-config="logsConfig"
      :log-files="logFiles"
      @close="showDetailsModal = false"
      @trigger-backup="triggerManualBackup"
      @trigger-forced-backup="triggerForcedBackup"
      @refresh-backup-history="loadBackupHistory"
      @download-backup-log="downloadBackupLog"
      @view-backup-log="viewBackupLog"
      @view-config-file="handleConfigFileView"
      @download-config-file="handleConfigFileDownload"
      @trigger-logs-export="triggerManualLogsExport"
      @refresh-log-files="loadLogFiles"
      @download-log-file="downloadLogFile"
      @view-log-file="viewLogFile"
      @notification="handleNotification"
      @update-port-param="handleUpdatePortParam"
      @update-ha-settings="handleUpdateHASettings"
      @update-favorite-ports="handleUpdateFavoritePorts"
      @update-logs-config="handleUpdateLogsConfig"
    />

    <!-- Модалка просмотра содержимого лог-файла -->
    <v-dialog v-model="showLogViewModal" max-width="800px" scrollable>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="me-2">mdi-file-document</v-icon>
          {{ selectedLogFile?.name }}
        </v-card-title>
        
        <v-card-text style="max-height: 500px;">
          <pre class="log-content">{{ logFileContent }}</pre>
        </v-card-text>
        
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="showLogViewModal = false">Закрыть</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Уведомления -->
    <v-snackbar
      v-model="showSnackbar"
      :color="snackbarColor"
      :timeout="4000"
      location="top right"
    >
      {{ snackbarText }}
      
      <template v-slot:actions>
        <v-btn
          variant="text"
          @click="showSnackbar = false"
        >
          Закрыть
        </v-btn>
      </template>
    </v-snackbar>

  </v-card>
</template>

<script setup>
import {ref, computed, onMounted} from 'vue'
import ActionHandler from '@/components/devices/ActionHandler.vue'
import {useTableStore} from '@/store/tables'
import MyFormField from '@/components/form_elements/MyFormField.vue'
import {usePortsStore} from '@/store/portsStore'
import {secureFetch} from '@/services/fetch'
import {webSocketService} from '@/services/websocket'
import UpdateIndicator from '@/components/UpdateIndicator.vue'
import PortsGrid from '@/components/ports/PortsGrid.vue'
import PortsTable from '@/components/ports/PortsTable.vue'
import FileListView from '@/components/ports/FileListView.vue'
import TableTemplateView from '@/components/ports/TableTemplateView.vue'
import BackupHistoryView from '@/components/devices/BackupHistoryView.vue'
import ConfigFilesManager from '@/components/devices/ConfigFilesManager.vue'
import DeviceDetailsModal from '@/components/devices/DeviceDetailsModal.vue'

const props = defineProps({
  device: Object,
  readonly: {
    type: Boolean,
    default: false
  },
  haConfigMode: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['edit', 'device-updated'])

const tableStore = useTableStore()
const portsStore = usePortsStore()

const port_metadata = computed(() => {
  const metadata = {}
  for (const port of tableStore.tables?.port_metadata?.items || []) {
    metadata[port.id] = port
  }
  return metadata
})

const ports = computed(() => (portsStore?.ports?.ports || []).filter(p => p && p.device_id === props.device.id))

// Проверка статуса онлайн из device.online (не из params)
const isDeviceOnline = computed(() => {
  // Сначала проверяем локальные данные, потом props
  const deviceData = Object.keys(localDeviceData.value).length > 0 ? localDeviceData.value : props.device
  return deviceData?.online === true
})

// Переменные для модалок и состояния
const showDetailsModal = ref(false)
const showLogViewModal = ref(false)
const detailsTab = ref('backup')
const backupLoading = ref(false)
const forcedBackupLoading = ref(false)
const logsLoading = ref(false)
const loadingBackupHistory = ref(false)
const loadingLogFiles = ref(false)

// Данные для модалок
const backupHistory = ref([])
const logFiles = ref([])
const selectedLogFile = ref(null)
const logFileContent = ref('')
const logsConfig = ref({})

// Уведомления
const showSnackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

// Проверка наличия модуля логов
const hasLogsModule = computed(() => {
  return processedGroups.value.some(group => group.title === 'LOGS' && group.type === 'file_list')
})

// Объединенные данные устройства (приоритет локальным данным)
const currentDeviceData = computed(() => {
  return Object.keys(localDeviceData.value).length > 0 ? localDeviceData.value : props.device
})

// Плоский список всех портов из processedGroups
const flattenedPorts = computed(() => {
  const ports = []
  processedGroups.value.forEach(group => {
    if (group.items) {
      group.items.forEach(item => {
        ports.push({
          ...item,
          group: group.title
        })
      })
    }
  })
  return ports
})

// Статус бэкапа
const backupStatusColor = computed(() => {
  const lastBackup = currentDeviceData.value?.params?.last_backup_time
  if (!lastBackup) return 'grey'
  
  const backupDate = new Date(lastBackup)
  const now = new Date()
  const hoursDiff = (now - backupDate) / (1000 * 60 * 60)
  
  if (hoursDiff < 24) return 'success'
  if (hoursDiff < 72) return 'warning'
  return 'error'
})

const backupStatusText = computed(() => {
  const lastBackup = currentDeviceData.value?.params?.last_backup_time
  if (!lastBackup) return 'Нет бэкапов'
  
  const backupDate = new Date(lastBackup)
  const now = new Date()
  const hoursDiff = (now - backupDate) / (1000 * 60 * 60)
  
  if (hoursDiff < 1) return 'Недавно'
  if (hoursDiff < 24) return `${Math.floor(hoursDiff)}ч назад`
  if (hoursDiff < 72) return `${Math.floor(hoursDiff / 24)}д назад`
  return 'Давно'
})

// Статус логов
const logsStatusColor = computed(() => {
  const lastExport = currentDeviceData.value?.params?.last_logs_export
  if (!lastExport) return 'grey'
  
  const exportDate = new Date(lastExport)
  const now = new Date()
  const hoursDiff = (now - exportDate) / (1000 * 60 * 60)
  
  if (hoursDiff < 24) return 'success'
  if (hoursDiff < 72) return 'warning'
  return 'error'
})

const logsStatusText = computed(() => {
  const lastExport = currentDeviceData.value?.params?.last_logs_export
  if (!lastExport) return 'Нет экспорта'
  
  const exportDate = new Date(lastExport)
  const now = new Date()
  const hoursDiff = (now - exportDate) / (1000 * 60 * 60)
  
  if (hoursDiff < 1) return 'Недавно'
  if (hoursDiff < 24) return `${Math.floor(hoursDiff)}ч назад`
  if (hoursDiff < 72) return `${Math.floor(hoursDiff / 24)}д назад`
  return 'Давно'
})

// Данные устройства из API
const deviceData = ref([])
const haIntegrationEnabled = ref(false)

// Состояние для индикации обновлений
const updatedPorts = ref(new Set())
const updatedGroups = ref(new Set())
const deviceUpdated = ref(false)

// Computed property для проверки наличия информации о бэкапах

// Загрузка данных устройства из API
const loadDeviceData = async () => {
  try {
    const response = await secureFetch(`/api/live/${props.device.params?.ip}/get_value`)
    const data = await response.json()
    deviceData.value = data || []
  } catch (error) {
    console.warn('Failed to load device data:', error)
    deviceData.value = []
  }
}


// Загрузка настроек HA интеграции
const loadHASettings = async () => {
  try {
    // Получаем настройки из params устройства
    const haSettings = props.device.params?.ha_integration || {}
    haIntegrationEnabled.value = haSettings.enabled ?? true
    
    // Применяем настройки к группам после их создания
    setTimeout(() => {
      applyHASettingsToGroups(haSettings)
    }, 100)
  } catch (error) {
    console.warn('Failed to load HA settings:', error)
    haIntegrationEnabled.value = true // По умолчанию включен
  }
}

// Применение HA настроек к группам
function applyHASettingsToGroups(haSettings) {
  const publishedPorts = haSettings.publishedPorts || []
  const publishedGroups = haSettings.publishedGroups || []
  
  processedGroups.value.forEach(group => {
    // Проверяем, опубликована ли вся группа
    group.haPublished = publishedGroups.includes(group.title)
    
    // Применяем настройки к портам
    group.items.forEach(item => {
      item.haPublished = group.haPublished || publishedPorts.includes(item.code)
    })
  })
}

// Обработка обновления настроек
const handleSettingsUpdated = async () => {
  // Перезагружаем настройки HA после обновления
  await loadHASettings()
  console.log('HA settings updated')
}

// Загрузка данных при монтировании
onMounted(async () => {
  await loadDeviceData()
  await loadHASettings()
  subscribeToPortUpdates()
  subscribeToDeviceUpdates()
})

// Состояние сворачивания групп
const expandedGroups = ref(new Set())


// Обработка данных из API для группировки
const processedGroups = computed(() => {
  const groups = {}
  
  deviceData.value.forEach(item => {
    if (item.data && Array.isArray(item.data)) {
      // Это группа с подгруппами
      const groupKey = item.title || item.code || 'Группа'
      groups[groupKey] = {
        title: groupKey,
        items: item.data.map(port => ({
          ...port,
          haPublished: false
        })),
        hasSubgroups: true,
        tpl: item.tpl || 'default',
        href: item.href,
        type: item.type,
        haPublished: false
      }
    } else if (item.type === 'file_list' && item.values) {
      // Специальный тип - список файлов
      const groupKey = item.title || 'Файлы'
      groups[groupKey] = {
        title: groupKey,
        values: item.values, // Передаем массив файлов напрямую
        type: 'file_list',
        items: [], // Пустой массив для совместимости
        hasSubgroups: false,
        tpl: 'file_list',
        href: item.href,
        haPublished: false
      }
    } else {
      // Это отдельный элемент
      const groupKey = 'Основные'
      if (!groups[groupKey]) {
        groups[groupKey] = {
          title: groupKey,
          items: [],
          hasSubgroups: false,
          tpl: 'default',
          haPublished: false
        }
      }
      groups[groupKey].items.push({
        ...item,
        haPublished: false
      })
    }
  })
  
  return Object.values(groups)
})

// Функции для управления сворачиванием
const toggleGroup = (groupTitle) => {
  if (expandedGroups.value.has(groupTitle)) {
    expandedGroups.value.delete(groupTitle)
  } else {
    expandedGroups.value.add(groupTitle)
  }
}

const isGroupExpanded = (groupTitle) => {
  return expandedGroups.value.has(groupTitle)
}

const maxPortsWithoutScroll = 10
const showConfigPorts = ref(false)
const editOptionsDialog = ref(false)
const optionsTab = ref(0)

const portsHeaders = [
  {title: 'ID', key: 'id'},
  {title: 'Код', key: 'code'},
  {title: 'Имя', key: 'name'},
  {title: 'Метка', key: 'label'},
  {title: 'Тип', key: 'type'},
  {title: 'Ед.', key: 'unit'},
  {title: 'Описание', key: 'description'},
  {title: '', key: 'actions', sortable: false},
]

const sortedPorts = (portsList) => {
  const nonConfig = portsList.filter(p => !isConfig(p))
  const config = portsList.filter(p => isConfig(p))
  return [...nonConfig, ...config]
}

const isConfig = (port) => port.mode === 'config'
const isDiagnostic = (port) => port.mode === 'diagnostic'
const isOptions = (port) => port.mode === 'options'

const diagnosticPorts = computed(() => (props.device.ports || []).filter(p => isDiagnostic(p)))
const optionsPorts = computed(() => (props.device.ports || []).filter(p => isOptions(p)))
const configPorts = computed(() => (props.device.ports || []).filter(p => isConfig(p)))

const showOptionsConfig = computed(() => optionsPorts.value.length || configPorts.value.length)

const connection = computed(() => tableStore.tables.connections?.items.find(c => c.id === props.device?.connection_id) || {})
const actions = computed(() => {
})

const powerSource = computed(() => props.device?.params?.power_source ?? null)
const powerSourceIcon = computed(() => {
  if (!powerSource.value) return 'mdi-power-plug'
  return powerSource.value.toLowerCase().includes('battery') ? 'mdi-battery' : 'mdi-power-plug'
})

const hasStatusInfo = computed(() => {
  return diagnosticPorts.value.length > 0 || powerSource.value
})

const device_schema = computed(() => {
  let structure = tableStore.tables.devices?.structure || []
  let schema = {}
  for (const field of structure) {
    schema[field.name] = field
  }
  return schema
})

function formatValue(item) {
  // Форматирование значения в зависимости от типа
  if (item.val !== undefined && item.val !== null) {
    if (item.type === 'out.list' && item.list) {
      return item.list[item.val] || item.val
    }
    return item.val
  }
  return '-'
}

function getPortIcon(port) {
  // Определяем иконку на основе типа порта
  if (port.type) {
    if (port.type.includes('temp')) return 'mdi-thermometer'
    if (port.type.includes('humidity')) return 'mdi-water-percent'
    if (port.type.includes('pressure')) return 'mdi-gauge'
    if (port.type.includes('voltage')) return 'mdi-lightning-bolt'
    if (port.type.includes('current')) return 'mdi-flash'
    if (port.type.includes('power')) return 'mdi-power'
    if (port.type.includes('energy')) return 'mdi-battery'
    if (port.type.includes('switch')) return 'mdi-toggle-switch'
    if (port.type.includes('button')) return 'mdi-button-cursor'
    if (port.type.includes('sensor')) return 'mdi-eye'
    if (port.type.includes('out.')) return 'mdi-cog'
  }
  return 'mdi-circle-outline'
}

function getPortColor(port) {
  // Определяем цвет на основе типа порта
  if (port.type) {
    if (port.type.includes('temp')) return 'orange'
    if (port.type.includes('humidity')) return 'blue'
    if (port.type.includes('pressure')) return 'purple'
    if (port.type.includes('voltage') || port.type.includes('current') || port.type.includes('power')) return 'red'
    if (port.type.includes('energy')) return 'green'
    if (port.type.includes('switch') || port.type.includes('button')) return 'primary'
    if (port.type.includes('sensor')) return 'teal'
    if (port.type.includes('out.')) return 'grey'
  }
  return 'grey'
}

function getValueClass(port) {
  // Определяем CSS класс для значения
  if (port.type) {
    if (port.type.includes('temp')) return 'text-orange'
    if (port.type.includes('humidity')) return 'text-blue'
    if (port.type.includes('pressure')) return 'text-purple'
    if (port.type.includes('voltage') || port.type.includes('current') || port.type.includes('power')) return 'text-red'
    if (port.type.includes('energy')) return 'text-green'
    if (port.type.includes('switch') || port.type.includes('button')) return 'text-primary'
    if (port.type.includes('sensor')) return 'text-teal'
    if (port.type.includes('out.')) return 'text-grey'
  }
  return 'text-grey'
}

function getGroupIcon(group) {
  // Определяем иконку для группы на основе названия
  const title = group.title.toLowerCase()
  if (title.includes('clock') || title.includes('время')) return 'mdi-clock'
  if (title.includes('light') || title.includes('свет')) return 'mdi-lightbulb'
  if (title.includes('ws-') || title.includes('led')) return 'mdi-led-strip'
  if (title.includes('wifi') || title.includes('сеть')) return 'mdi-wifi'
  if (title.includes('sensor') || title.includes('датчик')) return 'mdi-eye'
  if (title.includes('основные')) return 'mdi-cog'
  return 'mdi-folder'
}




function getPublishedPortsCount(group) {
  if (group.haPublished) {
    return group.items.length
  }
  return group.items.filter(item => item.haPublished).length
}

// Функции для работы с HA публикацией
function togglePortPublishing(item) {
  // При изменении порта проверяем состояние группы
  const group = processedGroups.value.find(g => g.items.includes(item))
  if (group) {
    const publishedCount = group.items.filter(i => i.haPublished).length
    if (publishedCount === 0) {
      group.haPublished = false
    } else if (publishedCount === group.items.length) {
      group.haPublished = true
    }
  }
  saveHASettings()
}

function toggleGroupPublishing(group) {
  // Если группа включена, включаем все порты
  // Если выключена, выключаем все порты
  group.items.forEach(item => {
    item.haPublished = group.haPublished
  })
  saveHASettings()
}


async function saveHASettings() {
  try {
    const publishedPorts = []
    const publishedGroups = []
    
    processedGroups.value.forEach(group => {
      if (group.haPublished) {
        publishedGroups.push(group.title)
      } else {
        group.items.forEach(item => {
          if (item.haPublished) {
            publishedPorts.push(item.code)
          }
        })
      }
    })
    
    const response = await secureFetch(`/api/devices/${props.device.id}/ha-settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        settings: {
          publishedPorts,
          publishedGroups
        }
      })
    })
    
    if (response.ok) {
      console.log('HA settings saved successfully')
    } else {
      const errorData = await response.json()
      console.error('Failed to save HA settings:', errorData)
      // Можно добавить уведомление пользователю
    }
  } catch (error) {
    console.error('Failed to save HA settings:', error)
    // Можно добавить уведомление пользователю
  }
}

// Функции для индикации обновлений
function showPortUpdate(portCode) {
  updatedPorts.value.add(portCode)
  setTimeout(() => {
    updatedPorts.value.delete(portCode)
  }, 1000)
}

function showGroupUpdate(groupTitle) {
  updatedGroups.value.add(groupTitle)
  setTimeout(() => {
    updatedGroups.value.delete(groupTitle)
  }, 1000)
}

function showDeviceUpdate() {
  deviceUpdated.value = true
  setTimeout(() => {
    deviceUpdated.value = false
  }, 1000)
}

// Подписка на обновления портов через WebSocket
function subscribeToPortUpdates() {
  // Подписываемся на обновления портов для этого устройства
  const deviceIP = props.device.params?.ip
  if (!deviceIP) return

  webSocketService.onMessage('port', 'in', (data) => {
    if (!data || typeof data !== 'object') {
      return;
    }
    
    // Проверяем, относится ли обновление к этому устройству
    if (data.device_id === props.device.id) {
      // Находим порт в processedGroups по коду
      processedGroups.value.forEach(group => {
        const portItem = group.items.find(item => item.code === data.code)
        if (portItem) {
          // Обновляем значение порта
          portItem.val = data.value;
          portItem.value = data.value;
          portItem.value_raw = data.value_raw;
          portItem.ts = data.ts;
          
          showPortUpdate(portItem.code)
          showGroupUpdate(group.title)
          showDeviceUpdate()
        }
      });
    }
  })
}

// Подписка на обновления устройств через WebSocket
function subscribeToDeviceUpdates() {
  // Подписываемся на обновления устройств
  webSocketService.onMessage('device', 'update', (data) => {
    if (data?.device_id === props.device.id) {
      // Обновляем локальные данные
      localDeviceData.value = data.device
      // Эмитим событие для обновления родительского компонента
      emit('device-updated', data.device)
      
      // Показываем индикацию обновления устройства
      showDeviceUpdate()
    }
  })
  
  // Подписываемся на обновления статуса устройств
  webSocketService.onMessage('device', 'status_update', (data) => {
    if (data?.device_id === props.device.id) {
      // Обновляем локальные данные
      localDeviceData.value = data.device
      // Эмитим событие для обновления родительского компонента
      emit('device-updated', data.device)
      
      // Показываем индикацию обновления устройства
      showDeviceUpdate()
    }
  })
}

// Методы для работы с HA публикацией уже определены выше в коде

// Методы для работы с новым интерфейсом портов
const getGroupViewMode = (group) => {
  // Определяем режим отображения для группы на основе ее типа
  if (group.tpl === 'table') return 'list'
  if (group.items && group.items.length > 6) return 'grid'
  return 'grid'
}

const handleViewModeChange = (groupTitle, mode) => {
  console.log(`Group ${groupTitle} view mode changed to: ${mode}`)
}

const handlePortUpdate = (code, value) => {
  try {
    // Отправляем команду на устройство через WebSocket
    const command = {
      type: 'device_command',
      device_id: props.device.id,
      code: code,
      value: value
    }
    
    webSocketService.send(JSON.stringify(command))
    
  } catch (error) {
    console.error('Error sending command via WebSocket:', error)
  }
}

const getDeviceBaseUrl = () => {
  const ip = props.device.params?.ip
  return ip ? `http://${ip}` : ''
}

// Методы для работы с бэкапами
const triggerManualBackup = async () => {
  backupLoading.value = true
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/backup/trigger`, {
      method: 'POST'
    })
    if (response.ok) {
      const result = await response.json()
      if (result.success) {
        // Показываем детальное уведомление
        if (result.has_changes) {
          showNotification(`Бэкап выполнен: ${result.changed_files} файлов изменено`, 'success')
        } else {
          showNotification('Бэкап выполнен: изменений не обнаружено', 'info')
        }
        // Обновляем данные устройства для статусов
        setTimeout(async () => {
          await refreshDeviceData()
          loadBackupHistory()
        }, 2000)
      } else {
        showNotification(`Ошибка бэкапа: ${result.error}`, 'error')
      }
    } else {
      showNotification('Ошибка при выполнении бэкапа', 'error')
    }
  } catch (error) {
    console.error('Error triggering manual backup:', error)
    showNotification('Ошибка соединения при выполнении бэкапа', 'error')
  } finally {
    backupLoading.value = false
  }
}

const triggerForcedBackup = async () => {
  forcedBackupLoading.value = true
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/backup/force`, {
      method: 'POST'
    })
    if (response.ok) {
      const result = await response.json()
      if (result.success) {
        showNotification(`Полный бэкап выполнен: ${result.changed_files} файлов сохранено`, 'success')
        setTimeout(async () => {
          await refreshDeviceData()
          loadBackupHistory()
        }, 2000)
      } else {
        showNotification(`Ошибка полного бэкапа: ${result.error}`, 'error')
      }
    } else {
      showNotification('Ошибка при выполнении полного бэкапа', 'error')
    }
  } catch (error) {
    console.error('Error triggering forced backup:', error)
    showNotification('Ошибка соединения при выполнении полного бэкапа', 'error')
  } finally {
    forcedBackupLoading.value = false
  }
}

const loadBackupHistory = async () => {
  loadingBackupHistory.value = true
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/backup/history`)
    if (response.ok) {
      const data = await response.json()
      backupHistory.value = data.history || []
    }
  } catch (error) {
    console.error('Error loading backup history:', error)
    backupHistory.value = []
  } finally {
    loadingBackupHistory.value = false
  }
}

// Методы для работы с логами
const triggerManualLogsExport = async () => {
  logsLoading.value = true
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/logs/export`, {
      method: 'POST'
    })
    if (response.ok) {
      const result = await response.json()
      if (result.success) {
        // Показываем уведомление об успехе
        showNotification('Экспорт логов успешно выполнен', 'success')
        // Обновляем данные устройства для статусов
        setTimeout(async () => {
          await refreshDeviceData()
          loadLogFiles()
        }, 2000)
      } else {
        showNotification(`Ошибка экспорта логов: ${result.error}`, 'error')
      }
    } else {
      showNotification('Ошибка при экспорте логов', 'error')
    }
  } catch (error) {
    console.error('Error triggering manual logs export:', error)
    showNotification('Ошибка соединения при экспорте логов', 'error')
  } finally {
    logsLoading.value = false
  }
}

const loadLogFiles = async () => {
  loadingLogFiles.value = true
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/logs/files`)
    if (response.ok) {
      const data = await response.json()
      logFiles.value = data.files || []
    }
  } catch (error) {
    console.error('Error loading log files:', error)
    logFiles.value = []
  } finally {
    loadingLogFiles.value = false
  }
}

const downloadLogFile = async (file) => {
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/logs/download/${file.name}`)
    if (response.ok) {
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = file.name
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      showNotification(`Файл ${file.name} успешно скачан`, 'success')
    } else {
      showNotification(`Ошибка скачивания файла ${file.name}`, 'error')
    }
  } catch (error) {
    console.error('Error downloading log file:', error)
    showNotification(`Ошибка соединения при скачивании файла ${file.name}`, 'error')
  }
}

const viewLogFile = async (file) => {
  selectedLogFile.value = file
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/logs/content/${file.name}`)
    if (response.ok) {
      const result = await response.json()
      if (result.success) {
        logFileContent.value = result.content
        showLogViewModal.value = true
      } else {
        logFileContent.value = `Ошибка: ${result.error}`
        showLogViewModal.value = true
        showNotification(`Ошибка загрузки файла: ${result.error}`, 'error')
      }
    } else {
      logFileContent.value = 'Ошибка загрузки содержимого файла'
      showLogViewModal.value = true
      showNotification(`Ошибка загрузки файла ${file.name}`, 'error')
    }
  } catch (error) {
    console.error('Error loading log file content:', error)
    logFileContent.value = 'Ошибка загрузки содержимого файла'
    showLogViewModal.value = true
    showNotification(`Ошибка соединения при загрузке файла ${file.name}`, 'error')
  }
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// Форматирование временной метки
const formatTimestamp = (timestamp) => {
  try {
    // Пробуем разные форматы даты
    let date
    if (timestamp.includes('T')) {
      // ISO формат: 2025-09-18T15:30:45.123456
      date = new Date(timestamp)
    } else if (timestamp.includes('-') && timestamp.includes(':')) {
      // Формат: 2025-09-18 15:30:45
      date = new Date(timestamp.replace(' ', 'T'))
    } else {
      // Другие форматы
      date = new Date(timestamp)
    }
    
    if (isNaN(date.getTime())) {
      return timestamp // Возвращаем как есть, если не удалось распарсить
    }
    
    // Форматируем в читаемый вид
    return date.toLocaleString('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch (error) {
    return timestamp // Возвращаем оригинал при ошибке
  }
}

// Методы для работы с backup.log файлом
const downloadBackupLog = async () => {
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/backup/download`)
    if (response.ok) {
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'backup.log'
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      showNotification('Файл backup.log успешно скачан', 'success')
    } else {
      showNotification('Ошибка скачивания файла backup.log', 'error')
    }
  } catch (error) {
    console.error('Error downloading backup.log:', error)
    showNotification('Ошибка соединения при скачивании backup.log', 'error')
  }
}

const viewBackupLog = async () => {
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/backup/content`)
    if (response.ok) {
      const result = await response.json()
      if (result.success) {
        selectedLogFile.value = { name: 'backup.log' }
        logFileContent.value = result.content
        showLogViewModal.value = true
      } else {
        showNotification(`Ошибка загрузки backup.log: ${result.error}`, 'error')
      }
    } else {
      showNotification('Ошибка загрузки файла backup.log', 'error')
    }
  } catch (error) {
    console.error('Error loading backup.log content:', error)
    showNotification('Ошибка соединения при загрузке backup.log', 'error')
  }
}

// Функция показа уведомлений
const showNotification = (text, color = 'success') => {
  snackbarText.value = text
  snackbarColor.value = color
  showSnackbar.value = true
}

// Локальные данные устройства для обновления статусов
const localDeviceData = ref({})

// Обновление данных устройства
const refreshDeviceData = async () => {
  try {
    // Запрашиваем обновленные данные устройства
    const response = await secureFetch(`/api/devices/${props.device.id}`)
    if (response.ok) {
      const updatedDevice = await response.json()
      // Обновляем локальные данные
      localDeviceData.value = updatedDevice
      // Эмитим событие для обновления родительского компонента
      emit('device-updated', updatedDevice)
    }
  } catch (error) {
    console.error('Error refreshing device data:', error)
  }
}

// Обработчики событий от дочерних компонентов
const handleConfigFileView = (data) => {
  viewConfigFile(data.filename, data.timestamp)
}

const handleConfigFileDownload = (data) => {
  downloadConfigFile(data.filename, data.timestamp)
}

const handleNotification = (notification) => {
  if (typeof notification === 'string') {
    showNotification(notification, 'info')
  } else if (typeof notification === 'object' && notification.text) {
    showNotification(notification.text, notification.color || 'info')
  } else {
    console.warn('Invalid notification format:', notification)
  }
}

// Методы для работы с файлами конфигурации из истории бэкапов
const viewConfigFile = async (filename, timestamp) => {
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/config/version/${filename}/${timestamp}`)
    if (response.ok) {
      const data = await response.json()
      if (data.success) {
        selectedLogFile.value = { name: `${filename} (${formatTimestamp(timestamp)})` }
        logFileContent.value = data.content
        showLogViewModal.value = true
      } else {
        showNotification(`Ошибка загрузки файла: ${data.error}`, 'error')
      }
    } else {
      showNotification(`Ошибка загрузки файла ${filename}`, 'error')
    }
  } catch (error) {
    console.error('Error viewing config file:', error)
    showNotification(`Ошибка соединения при загрузке файла ${filename}`, 'error')
  }
}

const downloadConfigFile = async (filename, timestamp) => {
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/config/download/${filename}/${timestamp}`)
    if (response.ok) {
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${filename}_${timestamp.replace(/[:\s]/g, '_')}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      showNotification(`Файл ${filename} успешно скачан`, 'success')
    } else {
      showNotification(`Ошибка скачивания файла ${filename}`, 'error')
    }
  } catch (error) {
    console.error('Error downloading config file:', error)
    showNotification(`Ошибка соединения при скачивании файла ${filename}`, 'error')
  }
}

// Новые методы для настройки портов
const handleUpdatePortParam = async (data) => {
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/port-param/${data.code}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data.updates)
    })
    
    if (response.ok) {
      showNotification('Параметры порта обновлены', 'success')
    } else {
      throw new Error('Ошибка обновления параметров')
    }
  } catch (error) {
    console.error('Error updating port param:', error)
    showNotification(`Ошибка обновления: ${error.message}`, 'error')
  }
}

const handleUpdateHASettings = async (settings) => {
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/ha-settings`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(settings)
    })
    
    if (response.ok) {
      showNotification('Настройки HA обновлены', 'success')
    } else {
      throw new Error('Ошибка обновления настроек HA')
    }
  } catch (error) {
    console.error('Error updating HA settings:', error)
    showNotification(`Ошибка обновления: ${error.message}`, 'error')
  }
}

const handleUpdateFavoritePorts = async (favoritePorts) => {
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/favorite-ports`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(favoritePorts)
    })
    
    if (response.ok) {
      showNotification('Избранные порты обновлены', 'success')
    } else {
      throw new Error('Ошибка обновления избранных портов')
    }
  } catch (error) {
    console.error('Error updating favorite ports:', error)
    showNotification(`Ошибка обновления: ${error.message}`, 'error')
  }
}

const handleUpdateLogsConfig = async (config) => {
  try {
    logsConfig.value = config
    showNotification('Конфигурация логов обновлена', 'success')
  } catch (error) {
    console.error('Error updating logs config:', error)
    showNotification(`Ошибка обновления: ${error.message}`, 'error')
  }
}

</script>


<style scoped>
.device-card {
  max-height: 600px;
  overflow-y: auto;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-width: 300px; /* Минимальная ширина для лучшего отображения портов */
}

.info-line {
  background-color: #f8f9fa;
}

.backup-history {
  max-height: 300px;
  overflow-y: auto;
}

.history-entry {
  padding: 8px 0;
  border-bottom: 1px solid #e0e0e0;
}

.history-entry:last-child {
  border-bottom: none;
}

.log-file-entry {
  border-bottom: 1px solid #e0e0e0;
}

.log-file-entry:last-child {
  border-bottom: none;
}

.log-content {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  background-color: #f5f5f5;
  padding: 16px;
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
}

.device-content {
  max-height: 500px;
  overflow-y: auto;
}

.group-container {
  border: none;
  background-color: transparent;
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

.group-content {
  margin-left: 16px;
  border-left: 2px solid #e0e0e0;
  padding-left: 12px;
}

.group-table {
  border: none;
  box-shadow: none;
}

.group-table .v-table__wrapper {
  border: none;
}

.port-row {
  border-bottom: 1px solid #f0f0f0;
}

.port-row:hover {
  background-color: #fafafa;
}

.table-view .group-table {
  background-color: #fafafa;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.table-view .group-table th {
  background-color: #f5f5f5;
  font-weight: 600;
  border-bottom: 2px solid #e0e0e0;
}

.table-view .group-table td {
  border-right: 1px solid #f0f0f0;
  border-bottom: 1px solid #f0f0f0;
}

.table-view .group-table td:last-child {
  border-right: none;
}

.default-view .group-table {
  background-color: transparent;
}

.file-list-view .group-table {
  background-color: #f8f9fa;
  border-radius: 4px;
}

.file-list-view .v-list-item {
  border-bottom: 1px solid #e0e0e0;
}

.file-list-view .v-list-item:hover {
  background-color: #f0f0f0;
}

.nav_bar_button {
  cursor: pointer;
  color: #2196F3;
  transition: color 0.2s;
}

.nav_bar_button:hover {
  color: #1a7b9c;
}

.backup-info-line {
  background-color: #f8f9fa;
  border-left: 3px solid #2196F3;
}

.backup-info-line .text-caption {
  font-size: 0.75rem;
  opacity: 0.8;
}

/* Врапперы для индикаторов обновления - фиксируют место */
.update-indicator-wrapper {
  display: inline-block;
  vertical-align: middle;
  position: relative;
}

.device-update-wrapper {
  width: 10px;
  height: 10px;
  margin-left: 8px;
  position: relative;
}

.group-update-wrapper {
  width: 6px;
  height: 6px;
  margin-left: 4px;
}

.port-update-wrapper {
  width: 6px;
  height: 6px;
  margin-left: 4px;
}

/* Стили для размеров индикаторов */
.device-update {
  width: 10px;
  height: 10px;
}

.group-update {
  width: 6px;
  height: 6px;
}

.port-update {
  width: 6px;
  height: 6px;
}



/* Адаптивные стили для мобильных устройств */
@media (max-width: 600px) {
  .device-card {
    max-height: 500px;
  }
  
  .device-content {
    max-height: 400px;
  }
  
  .group-header {
    padding: 6px 8px;
    font-size: 0.9rem;
  }
  
  .group-content {
    margin-left: 8px;
    padding-left: 8px;
  }
  
  .table-view .group-table th,
  .table-view .group-table td {
    padding: 4px 6px;
    font-size: 0.8rem;
  }
  
  .port-row td {
    padding: 4px 6px;
    font-size: 0.8rem;
  }
}

@media (max-width: 400px) {
  .device-card {
    max-height: 400px;
  }
  
  .device-content {
    max-height: 300px;
  }
  
  .group-header {
    padding: 4px 6px;
    font-size: 0.85rem;
  }
  
  .table-view .group-table th,
  .table-view .group-table td {
    padding: 2px 4px;
    font-size: 0.75rem;
  }
}

/* Стили для новой системы портов */
.new-ports-section {
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.02);
}

.new-ports-section .v-card-text {
  padding-top: 16px;
}

/* Адаптивные стили для устройств */
@media (max-width: 1400px) {
  .device-card {
    min-width: 280px;
  }
}

@media (max-width: 768px) {
  .device-card {
    min-width: 100%;
    max-height: none; /* Убираем ограничение высоты на мобильных */
  }
  
  .device-content {
    max-height: none;
  }
  
  /* Новая система портов на мобильных */
  .new-ports-section .v-card-text {
    padding: 8px 16px;
  }
}
</style>
