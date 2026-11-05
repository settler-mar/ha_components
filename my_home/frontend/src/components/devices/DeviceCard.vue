<template>
  <v-card class="mb-2 device-card" elevation="1">
    <header class="device-header" :class="{ 'device-header--offline': !isDeviceOnline }">
      <!-- Строка 1: идентификация + основные действия -->
      <div class="device-header__row device-header__row--identity">
        <div class="device-header__identity" :title="device.name">
          <span class="device-header__chip-icon" aria-hidden="true">
            <v-icon size="18">mdi-chip</v-icon>
          </span>
          <span class="device-header__name">{{ device.name }}</span>
          <v-tooltip location="top">
            <template v-slot:activator="{ props }">
              <button
                v-bind="props"
                type="button"
                class="device-header__id"
                @click="copyDeviceIP"
              >
                id:&nbsp;{{ device.id }}
              </button>
            </template>
            <span>IP: {{ deviceIP || 'N/A' }} · нажмите, чтобы скопировать</span>
          </v-tooltip>
          <span
            class="device-header__pulse update-indicator-wrapper"
            title="Данные обновлены"
            aria-hidden="true"
          >
            <UpdateIndicator :show="deviceUpdated" :duration="1000" class="device-update" />
          </span>
        </div>

        <div v-if="!readonly" class="device-header__actions">
          <v-btn
            icon
            variant="text"
            size="small"
            density="comfortable"
            :color="virtualConfigMode ? 'orange' : undefined"
            title="Интерактивное добавление в виртуальные устройства"
            aria-label="Добавить в виртуальное устройство"
            @click="virtualConfigMode = !virtualConfigMode"
          >
            <v-icon size="18">mdi-source-branch</v-icon>
          </v-btn>

          <ActionHandler
            :actions="actions"
            :params="{device_id: device.id, ...device, ...(device?.params || {})}"
          >
            <v-btn
              icon
              variant="text"
              size="small"
              density="comfortable"
              @click="refreshDeviceData"
              :loading="refreshingDeviceData"
              title="Перезапросить текущие порты"
              aria-label="Обновить данные устройства"
            >
              <v-icon size="18" icon="mdi-refresh" />
            </v-btn>
          </ActionHandler>

          <v-btn
            icon
            variant="text"
            size="small"
            density="comfortable"
            color="error"
            title="Удалить устройство"
            aria-label="Удалить устройство"
            @click="deleteDevice"
          >
            <v-icon size="18" icon="mdi-delete" />
          </v-btn>
        </div>
      </div>

      <!-- Строка 2: статусы + сервисные показатели + «Детали» -->
      <div class="device-header__row device-header__row--status">
        <div class="device-header__status" aria-label="Состояние устройства">
          <v-chip
            density="compact"
            size="x-small"
            :color="isDeviceOnline ? 'success' : 'error'"
            variant="tonal"
            :title="isDeviceOnline ? 'Устройство в сети' : 'Устройство недоступно'"
            class="device-status-chip"
          >
            <v-icon size="13" start aria-hidden="true">
              {{ isDeviceOnline ? 'mdi-check-circle' : 'mdi-close-circle' }}
            </v-icon>
            {{ isDeviceOnline ? 'online' : 'offline' }}
          </v-chip>

          <v-chip
            v-if="syncState.status"
            density="compact"
            size="x-small"
            :color="syncState.color"
            variant="outlined"
            :title="syncState.title"
            class="device-status-chip"
          >
            <v-icon size="12" start>mdi-sync</v-icon>
            {{ syncState.label }}
          </v-chip>

          <v-badge
            v-if="hasPendingHAChanges"
            :content="haChangesStore.getDeviceChangesCount(props.device.id)"
            color="primary"
            location="top right"
            overlap
            class="device-ha-badge"
          >
            <v-chip
              density="compact"
              size="x-small"
              color="warning"
              variant="tonal"
              title="Есть изменения для Home Assistant"
              class="device-status-chip"
            >
              <v-icon size="12" start>mdi-home-assistant</v-icon>
              HA
            </v-chip>
          </v-badge>
          <v-chip
            v-else-if="virtualPublishedCount > 0"
            density="compact"
            size="x-small"
            color="success"
            variant="outlined"
            :title="`Виртуальных портов опубликовано: ${virtualPublishedCount}`"
            class="device-status-chip"
          >
            <v-icon size="12" start>mdi-home-assistant</v-icon>
            HA · {{ virtualPublishedCount }}
          </v-chip>
        </div>

        <div class="device-header__meta">
          <button
            type="button"
            class="device-header__metric"
            :class="`device-header__metric--${backupStatusColor}`"
            :title="`Последний бэкап: ${backupStatusText}. Нажмите, чтобы запустить сейчас`"
            :disabled="backupLoading"
            @click="triggerManualBackup"
          >
            <v-progress-circular
              v-if="backupLoading"
              size="14"
              width="2"
              indeterminate
            />
            <v-icon v-else size="14">mdi-backup-restore</v-icon>
            <span>{{ backupStatusText }}</span>
          </button>

          <button
            v-if="hasLogsModule"
            type="button"
            class="device-header__metric"
            :class="`device-header__metric--${logsStatusColor}`"
            :title="`Экспорт логов: ${logsStatusText}. Нажмите, чтобы запустить сейчас`"
            :disabled="logsLoading"
            @click="triggerManualLogsExport"
          >
            <v-progress-circular
              v-if="logsLoading"
              size="14"
              width="2"
              indeterminate
            />
            <v-icon v-else size="14">mdi-file-document-outline</v-icon>
            <span>{{ logsStatusText }}</span>
          </button>

          <v-btn
            class="device-header__details"
            size="small"
            variant="tonal"
            density="comfortable"
            prepend-icon="mdi-information-outline"
            @click="showDetailsModal = true"
          >
            Детали
          </v-btn>
        </div>
      </div>
    </header>

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
      <div v-if="virtualConfigMode" class="virtual-selection-toolbar mb-2">
        <v-icon size="18" color="orange" class="me-2">mdi-source-branch</v-icon>
        <span class="text-body-2 font-weight-medium me-3">Добавление в виртуальное устройство</span>
        <v-text-field
          v-model="virtualFilter"
          label="Имя"
          placeholder="Фильтр по имени"
          prepend-inner-icon="mdi-magnify"
          variant="outlined"
          density="compact"
          hide-details
          clearable
          class="virtual-filter"
        />
        <v-checkbox
          v-model="hideVirtualPublished"
          label="Скрыть уже в HA"
          density="compact"
          hide-details
          class="ms-3"
        />
        <v-chip size="small" color="primary" variant="tonal" class="ms-auto">
          Выбрано: {{ selectedVirtualCodes.length }}
        </v-chip>
        <v-btn
          size="small"
          variant="text"
          prepend-icon="mdi-restore"
          :disabled="!selectedVirtualCodes.length"
          @click="resetVirtualSelection"
        >
          Сбросить
        </v-btn>
        <v-btn
          size="small"
          color="primary"
          variant="flat"
          prepend-icon="mdi-arrow-right"
          :disabled="!selectedVirtualCodes.length"
          :loading="virtualDraftLoading"
          @click="continueVirtualSelection"
        >
          Продолжить
        </v-btn>
      </div>

      <v-row v-if="device.description">
        <v-col cols="12">
          {{ device.description }}
        </v-col>
      </v-row>

      <!-- Система отображения портов -->
      <div>
        <!-- Обработка разных типов групп -->
        <template v-for="group in visibleProcessedGroups" :key="group.title">
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
            :device_id="device.id"
            :group-icon="getGroupIcon(group)"
            :collapsible="true"
            :show-ha-checkboxes="virtualConfigMode && haIntegrationEnabled"
            :show-group-update="updatedGroups.has(group.title)"
            :updated-ports="updatedPorts"
            @update="handlePortUpdate"
            class="mb-2"
          />
          <!-- Обычные порты -->
          <PortsTable
            v-else
            :title="group.title"
            :ports="group.items"
            :device_id="device.id"
            :group-icon="getGroupIcon(group)"
            :collapsible="true"
            :show-ha-checkboxes="virtualConfigMode && haIntegrationEnabled"
            :show-edit-buttons="false"
            :show-group-update="updatedGroups.has(group.title)"
            :updated-ports="updatedPorts"
            :favorite-codes="favoriteCodes"
            :favorites-filter="favoritesFilter"
            @update="handlePortUpdate"
            @favorite-toggle="handleFavoriteToggle"
            @favorites-filter="favoritesFilter = !favoritesFilter"
            class="mb-2"
          />
        </template>
      </div>

      <v-dialog v-model="virtualDraftDialog" max-width="980px" scrollable>
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="me-2" color="primary">mdi-source-branch</v-icon>
            Конфигурация виртуального устройства
          </v-card-title>
          <v-card-text>
            <v-combobox
              v-model="virtualDraftName"
              :items="existingVirtualDeviceNames"
              label="Имя виртуального устройства"
              hint="Новое имя создаст устройство, существующее имя расширит его"
              persistent-hint
              variant="outlined"
              density="compact"
              class="mb-3"
            />
            <v-alert v-if="virtualTargetDevice" type="info" variant="tonal" density="compact" class="mb-3">
              Будет расширено существующее виртуальное устройство «{{ virtualTargetDevice.name }}».
            </v-alert>
            <div class="mb-3">
              <TagsInput v-model="virtualDraftTags" :items="availableVirtualTags" :autoload="false" />
            </div>
            <v-alert type="info" variant="tonal" density="compact" class="mb-3">
              Выбрано параметров: {{ virtualDraft?.ports?.length || selectedVirtualCodes.length }}
            </v-alert>
            <div v-if="virtualDraft?.ports?.length" class="virtual-port-settings-list">
              <div v-for="port in virtualDraft.ports" :key="port.physical_code" class="virtual-port-settings">
                <div class="d-flex align-center mb-2">
                  <v-icon size="18" color="primary" class="me-2">mdi-tune-variant</v-icon>
                  <div>
                    <div class="text-body-2 font-weight-medium">{{ port.physical_code }}</div>
                    <div class="text-caption text-grey">Привязка к параметру платы</div>
                  </div>
                </div>
                <v-row dense>
                  <v-col cols="12" md="4">
                    <v-text-field v-model="port.name" label="Имя порта" variant="outlined" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" md="2">
                    <v-select v-model="port.type" :items="virtualPortTypeOptions" label="Тип HA" variant="outlined" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" md="2">
                    <v-text-field v-model="port.unit_of_measurement" label="Единица" variant="outlined" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" md="2">
                    <v-text-field v-model="port.device_class" label="Класс устройства" variant="outlined" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" md="2">
                    <v-text-field v-model="port.icon" label="Иконка" placeholder="mdi-..." variant="outlined" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12">
                    <v-text-field v-model="port.description" label="Описание" variant="outlined" density="compact" hide-details />
                  </v-col>
                </v-row>
              </div>
            </div>
            <v-alert v-if="virtualDraftDiff" type="success" variant="tonal" density="compact" class="mt-3">
              Новых параметров: {{ virtualDraftDiff.ports_to_add?.length || 0 }};
              уже существующих: {{ virtualDraftDiff.ports_existing?.length || 0 }}.
            </v-alert>
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="virtualDraftDialog = false">Отмена</v-btn>
            <v-btn color="primary" @click="saveVirtualDraft" :loading="virtualDraftSaving">
              Сохранить модель
            </v-btn>
            <v-btn color="success" @click="publishVirtualDraft" :loading="virtualDraftSaving">
              Сохранить и опубликовать
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-card-text>



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
      :log-files="logFiles"
      :device-data="currentDeviceData"
      :ports-data="flattenedPorts"
      :logs-config="logsConfig"
      :device-info="deviceInfo"
      :loading-device-info="loadingDeviceInfo"
      :device="device"
      :custom-params="props.customParams"
      @close="showDetailsModal = false"
      @load-device-info="loadDeviceInfo"
      @trigger-backup="triggerManualBackup"
      @trigger-forced-backup="triggerForcedBackup"
      @refresh-backup-history="loadBackupHistory"
      @download-backup-log="downloadBackupLog"
      @view-backup-log="viewBackupLog"
      @delete-backup="deleteBackup"
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
      @device-updated="handleDeviceUpdate"
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

    <!-- Изменения физической конфигурации платы -->
    <v-dialog v-model="showPortChangesDialog" max-width="760" scrollable>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="me-2" color="info">mdi-sync-alert</v-icon>
          <div class="d-flex flex-column">
            <span>Изменения портов платы</span>
            <span class="text-caption text-medium-emphasis">
              {{ device.name }} · id {{ device.id }}<span v-if="device.params?.ip"> · {{ device.params.ip }}</span>
            </span>
          </div>
          <v-spacer></v-spacer>
          <v-btn
            v-if="getDeviceBaseUrl()"
            :href="getDeviceBaseUrl()"
            target="_blank"
            rel="noopener"
            variant="outlined"
            size="small"
            class="me-2"
            prepend-icon="mdi-open-in-new"
          >
            Конфиг устройства
          </v-btn>
          <v-btn icon variant="text" @click="showPortChangesDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>

        <v-card-text>
          <v-alert type="info" variant="tonal" class="mb-4">
            Получена новая физическая конфигурация платы. Home Assistant пока не изменялся.
            Проверьте изменения и выполните пересинхронизацию вручную.
          </v-alert>

          <template v-if="portRefreshChanges">
            <div v-if="portRefreshChanges.added?.length" class="mb-4">
              <div class="text-subtitle-1 text-success mb-2">
                Добавлены ({{ portRefreshChanges.added.length }})
              </div>
              <v-chip
                v-for="port in portRefreshChanges.added"
                :key="`added-${port.code}-${port.direction}`"
                class="ma-1"
                color="success"
                variant="tonal"
              >
                {{ port.title || port.name || port.code }}
              </v-chip>
            </div>

            <div v-if="portRefreshChanges.removed?.length" class="mb-4">
              <div class="text-subtitle-1 text-error mb-2">
                Удалены ({{ portRefreshChanges.removed.length }})
              </div>
              <v-chip
                v-for="port in portRefreshChanges.removed"
                :key="`removed-${port.code}-${port.direction}`"
                class="ma-1"
                color="error"
                variant="tonal"
              >
                {{ port.title || port.name || port.code }}
              </v-chip>
            </div>

            <div v-if="meaningfulChangedPorts.length" class="mb-2">
              <div class="text-subtitle-1 text-warning mb-2">
                Изменены ({{ meaningfulChangedPorts.length }})
              </div>
              <v-expansion-panels variant="accordion" multiple>
                <v-expansion-panel
                  v-for="change in meaningfulChangedPorts"
                  :key="`changed-${change.after.code}`"
                >
                  <v-expansion-panel-title>
                    <div class="d-flex flex-column">
                      <span>{{ change.after.title || change.before.title || change.after.code }}</span>
                      <span class="text-caption text-medium-emphasis">
                        {{ change.after.code }}
                        <template v-if="(change.changed_fields || []).length">
                          · изменено:
                          {{ (change.changed_fields || []).map(portFieldLabel).join(', ') }}
                        </template>
                        <template v-else>
                          · изменились служебные поля
                        </template>
                      </span>
                    </div>
                  </v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <div
                      v-for="field in portChangedFieldsFor(change)"
                      :key="field"
                      class="mb-1"
                    >
                      <strong>{{ portFieldLabel(field) }}:</strong>
                      <span class="text-medium-emphasis">{{ formatPortFieldValue(change.before[field]) }}</span>
                      →
                      <span>{{ formatPortFieldValue(change.after[field]) }}</span>
                    </div>
                    <div class="mt-2 d-flex ga-2 flex-wrap">
                      <v-btn
                        v-if="portConfigUrl(change.after) || portConfigUrl(change.before)"
                        :href="portConfigUrl(change.after) || portConfigUrl(change.before)"
                        target="_blank"
                        rel="noopener"
                        size="small"
                        variant="outlined"
                        prepend-icon="mdi-open-in-new"
                      >
                        Открыть порт на плате
                      </v-btn>
                      <v-btn
                        size="small"
                        variant="text"
                        prepend-icon="mdi-code-json"
                        @click="change._showRaw = !change._showRaw"
                      >
                        {{ change._showRaw ? 'Скрыть JSON' : 'Показать JSON' }}
                      </v-btn>
                    </div>
                    <pre v-if="change._showRaw" class="mt-2 pa-2 text-caption" style="background: rgba(0,0,0,0.04); border-radius: 4px; overflow-x: auto;">{{ JSON.stringify({ before: change.before, after: change.after }, null, 2) }}</pre>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </div>

            <v-alert
              v-if="!hasMeaningfulChanges"
              type="success"
              variant="tonal"
            >
              Изменений в физической конфигурации не найдено.
            </v-alert>
          </template>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showPortChangesDialog = false">Закрыть</v-btn>
          <v-btn
            v-if="hasMeaningfulChanges"
            color="primary"
            variant="outlined"
            @click="openHAIntegrationAfterPortRefresh"
          >
            Перейти к пересинхронизации HA
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

  </v-card>
</template>

<script setup>
import {ref, computed, onMounted, watch} from 'vue'
import ActionHandler from '@/components/devices/ActionHandler.vue'
import {useTableStore} from '@/store/tables'
import MyFormField from '@/components/form_elements/MyFormField.vue'
import TagsInput from '@/components/form_elements/TagsInput.vue'
import {usePortsStore} from '@/store/portsStore'
import {useHAChangesStore} from '@/store/haChangesStore'
import useMessageStore from '@/store/messages'
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
  },
  customParams: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['device-updated', 'deleted'])

const virtualConfigMode = ref(false)
const virtualFilter = ref('')
const hideVirtualPublished = ref(false)
const virtualOverview = ref([])
const virtualDraftDialog = ref(false)
const virtualDraftLoading = ref(false)
const virtualDraftSaving = ref(false)
const virtualDraftName = ref('')
const existingVirtualDevices = ref([])
const virtualDraftTags = ref([])
const availableVirtualTags = ref([])
const virtualDraft = ref(null)
const virtualDraftDiff = ref(null)
const virtualPortTypeOptions = ['sensor', 'switch', 'number', 'input_boolean', 'input_text', 'input_select', 'input_button']
const existingVirtualDeviceNames = computed(() => existingVirtualDevices.value.map(device => device.name))
const virtualTargetDevice = computed(() => {
  const name = virtualDraftName.value.trim().toLowerCase()
  return existingVirtualDevices.value.find(device => device.name.trim().toLowerCase() === name) || null
})

const loadExistingVirtualDevices = async () => {
  try {
    const response = await secureFetch('/api/virtual-devices')
    const data = await response.json()
    existingVirtualDevices.value = data.devices || []
  } catch (error) {
    console.warn('Failed to load existing virtual devices:', error)
  }
}

const normalizeTag = (value) => {
  const text = String(value || '').trim().replace(/^#+/, '')
  return text ? `#${text}` : ''
}

const inferPortPresentation = (port) => {
  const text = `${port.name || ''} ${port.title || ''} ${port.physical_code || ''} ${port.unit_of_measurement || ''}`.toLowerCase()
  let deviceClass = port.device_class || ''
  let icon = port.icon || ''
  if (!deviceClass) {
    if (/темпера|temperature|temp|°c|celsius/.test(text)) deviceClass = 'temperature'
    else if (/влаж|humid/.test(text)) deviceClass = 'humidity'
    else if (/давлен|pressure/.test(text)) deviceClass = 'pressure'
    else if (/мощн|power|ватт|watt/.test(text)) deviceClass = 'power'
    else if (/энерг|energy|квт|kwh/.test(text)) deviceClass = 'energy'
    else if (/напряж|voltage|volt|вольт/.test(text)) deviceClass = 'voltage'
    else if (/ток|current|ампер|amp/.test(text)) deviceClass = 'current'
    else if (/батар|battery/.test(text)) deviceClass = 'battery'
    else if (/rssi|signal|сигнал/.test(text)) deviceClass = 'signal_strength'
  }
  if (!icon) {
    if (deviceClass === 'temperature') icon = 'mdi-thermometer'
    else if (deviceClass === 'humidity') icon = 'mdi-water-percent'
    else if (deviceClass === 'pressure') icon = 'mdi-gauge'
    else if (deviceClass === 'power' || deviceClass === 'energy') icon = 'mdi-flash'
    else if (deviceClass === 'voltage') icon = 'mdi-sine-wave'
    else if (deviceClass === 'current') icon = 'mdi-current-ac'
    else if (deviceClass === 'battery') icon = 'mdi-battery'
    else if (deviceClass === 'signal_strength') icon = 'mdi-wifi'
    else if (port.type === 'switch') icon = 'mdi-toggle-switch'
    else icon = 'mdi-chart-line'
  }
  return { deviceClass, icon }
}

const loadVirtualTags = async () => {
  try {
    const response = await secureFetch('/api/virtual-devices')
    const data = await response.json()
    availableVirtualTags.value = (data.tags || []).map(normalizeTag).filter(Boolean)
  } catch (error) {
    console.warn('Failed to load virtual device tags:', error)
  }
}

const selectedVirtualCodes = computed(() => {
  const changes = haChangesStore.changes[props.device.id] || {}
  const codes = Object.entries(changes)
    .filter(([, action]) => action === 'add')
    .map(([code]) => code.startsWith('virtual-service:') ? code.slice('virtual-service:'.length) : code)
  return [...new Set(codes)]
})

const resetVirtualSelection = () => {
  haChangesStore.clearDeviceChanges(props.device.id)
}

const continueVirtualSelection = async () => {
  if (!selectedVirtualCodes.value.length) return
  virtualDraftLoading.value = true
  try {
    await loadVirtualTags()
    if (!virtualDraftName.value) {
      virtualDraftName.value = `${props.device.name} — виртуальное устройство`
    }
    await loadExistingVirtualDevices()
    const response = await secureFetch(`/api/myhome/device/${props.device.id}/ha/virtual-draft`, {
      method: 'POST',
      data: {
        source_type: 'port',
        selected_codes: selectedVirtualCodes.value,
        name: virtualDraftName.value,
        tags: virtualDraftTags.value,
        target_virtual_device_id: virtualTargetDevice.value?.id || null
      }
    })
    const data = await response.json()
    data.draft.ports = (data.draft.ports || []).map(port => {
      const presentation = inferPortPresentation(port)
      return {
        ...port,
        device_class: port.device_class || presentation.deviceClass,
        icon: port.icon || presentation.icon,
        entity_category: port.entity_category || 'diagnostic'
      }
    })
    virtualDraft.value = data.draft
    const previewResponse = await secureFetch(`/api/myhome/device/${props.device.id}/ha/virtual-draft/preview`, {
      method: 'POST',
      data: { draft: data.draft }
    })
    virtualDraftDiff.value = (await previewResponse.json()).diff
    virtualDraftDialog.value = true
  } catch (error) {
    console.error('Failed to create virtual device draft:', error)
    messageStore.showError('Не удалось сформировать конфигурацию виртуального устройства')
  } finally {
    virtualDraftLoading.value = false
  }
}

const refreshVirtualDraftPreview = async () => {
  if (!virtualDraft.value) return
  try {
    const response = await secureFetch(`/api/myhome/device/${props.device.id}/ha/virtual-draft/preview`, {
      method: 'POST',
      data: { draft: virtualDraft.value }
    })
    virtualDraftDiff.value = (await response.json()).diff
  } catch (error) {
    console.warn('Failed to refresh virtual draft preview:', error)
  }
}

watch(virtualDraftName, () => {
  if (!virtualDraftDialog.value) return
  syncVirtualDraftTarget()
  refreshVirtualDraftPreview()
})

watch(virtualDraftTags, () => {
  if (!virtualDraftDialog.value) return
  syncVirtualDraftTarget()
}, { deep: true })

const syncVirtualDraftTarget = () => {
  if (!virtualDraft.value) return
  const name = (virtualDraftName.value || '').trim()
  const existing = existingVirtualDevices.value.find(
    device => String(device.name || '').trim().toLowerCase() === name.toLowerCase()
  )
  virtualDraft.value.target = {
    ...(virtualDraft.value.target || {}),
    id: existing ? existing.id : null,
    name: name || virtualDraft.value.target?.name || '',
    tags: virtualDraftTags.value
  }
}

const saveVirtualDraft = async () => {
  if (!virtualDraft.value) return
  syncVirtualDraftTarget()
  virtualDraftSaving.value = true
  try {
    await secureFetch(`/api/myhome/device/${props.device.id}/ha/virtual-draft/apply`, {
      method: 'POST',
      data: { draft: virtualDraft.value, confirmed: true }
    })
    virtualDraftDialog.value = false
    resetVirtualSelection()
    await loadVirtualOverview()
    messageStore.showSuccess('Виртуальная модель сохранена')
  } catch (error) {
    console.error('Failed to save virtual device draft:', error)
    messageStore.showError('Не удалось сохранить виртуальную модель')
  } finally {
    virtualDraftSaving.value = false
  }
}

const publishVirtualDraft = async () => {
  if (!virtualDraft.value) return
  syncVirtualDraftTarget()
  virtualDraftSaving.value = true
  try {
    await secureFetch(`/api/myhome/device/${props.device.id}/ha/virtual-draft/publish`, {
      method: 'POST',
      data: { draft: virtualDraft.value, confirmed: true }
    })
    virtualDraftDialog.value = false
    resetVirtualSelection()
    await loadVirtualOverview()
    messageStore.showSuccess('Виртуальная модель опубликована в Home Assistant')
  } catch (error) {
    console.error('Failed to publish virtual device draft:', error)
    messageStore.showError('Не удалось опубликовать виртуальную модель')
  } finally {
    virtualDraftSaving.value = false
  }
}

const tableStore = useTableStore()
const portsStore = usePortsStore()
const haChangesStore = useHAChangesStore()
const messageStore = useMessageStore()

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
const showPortChangesDialog = ref(false)
const portRefreshChanges = ref(null)

const PORT_FIELD_LABELS = {
  title: 'название',
  direction: 'направление',
  kind: 'тип',
  type_raw: 'тип (raw)',
  unit: 'единица',
  group_title: 'группа',
  value_type: 'формат значения',
}

function portFieldLabel(field) {
  return PORT_FIELD_LABELS[field] || field
}

function formatPortFieldValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const PORT_DIFF_FALLBACK_FIELDS = [
  'title', 'direction', 'kind', 'type_raw', 'unit',
  'group_title', 'value_type', 'mqtt', 'href', 'block_id',
]

// Поля, меняющиеся при каждом опросе платы (значения датчиков, время),
// а не при изменении конфигурации — игнорируем в диффе.
const PORT_DIFF_IGNORED_FIELDS = new Set([
  'val', 'value', 'raw', 'extra', 'last_update', 'available',
  'ha_eligible', 'state',
])

function portChangedFieldsFor(change) {
  const listed = (change?.changed_fields || []).filter(f => !PORT_DIFF_IGNORED_FIELDS.has(f))
  if (listed.length) return listed
  const before = change?.before || {}
  const after = change?.after || {}
  const keys = new Set([
    ...PORT_DIFF_FALLBACK_FIELDS,
    ...Object.keys(before),
    ...Object.keys(after),
  ])
  const diff = []
  for (const key of keys) {
    if (PORT_DIFF_IGNORED_FIELDS.has(key)) continue
    const b = before[key]
    const a = after[key]
    if (JSON.stringify(b) !== JSON.stringify(a)) diff.push(key)
  }
  return diff
}

const meaningfulChangedPorts = computed(() => {
  const list = portRefreshChanges.value?.changed || []
  return list.filter(change => portChangedFieldsFor(change).length > 0)
})

const hasMeaningfulChanges = computed(() => {
  const c = portRefreshChanges.value
  if (!c) return false
  return Boolean(c.added?.length || c.removed?.length || meaningfulChangedPorts.value.length)
})

function portConfigUrl(port) {
  if (!port) return ''
  const base = getDeviceBaseUrl()
  if (!base) return ''
  const href = port.href || port.group_href
  if (!href) return base
  if (/^https?:\/\//i.test(href)) return href
  return `${base}${href.startsWith('/') ? '' : '/'}${href}`
}

// Проверка наличия модуля логов
const hasLogsModule = computed(() => {
  return processedGroups.value.some(group => group.title === 'LOGS' && group.type === 'file_list')
})

// Объединенные данные устройства (приоритет локальным данным)
const currentDeviceData = computed(() => {
  const baseData = Object.keys(localDeviceData.value).length > 0 ? localDeviceData.value : props.device
  
  // Добавляем HA статус из haStatus (реактивно)
  const haSettings = {
    publishedPorts: Object.keys(haStatus.value).filter(portCode => haStatus.value[portCode]?.ha_published)
  }
  
  return {
    ...baseData,
    haSettings
  }
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
const haStatus = ref({}) // Добавляем переменную для хранения HA статуса
const syncState = ref({})

const syncStateView = {
  not_started: { label: 'нет', color: 'grey' },
  loading: { label: 'загрузка', color: 'info' },
  synced: { label: 'актуально', color: 'success' },
  stale: { label: 'устарело', color: 'warning' },
  error: { label: 'ошибка', color: 'error' }
}

// Состояние для индикации обновлений
const updatedPorts = ref(new Set())
const updatedGroups = ref(new Set())
const deviceUpdated = ref(false)

// Проверка наличия ожидающих изменений HA для этого устройства
const hasPendingHAChanges = computed(() => {
  return haChangesStore.getDeviceChangesCount(props.device.id) > 0
})

const virtualPublishedCount = computed(() => {
  return virtualOverview.value.reduce(
    (total, port) => total + (port.virtual_usage || []).filter(item => item.published_to_ha).length,
    0
  )
})

// Функция для проверки статуса публикации порта в HA
const isPortPublishedToHA = (portCode) => {
  return haStatus.value[portCode]?.ha_published || false
}

// Функция для получения entity_id порта
const getPortEntityId = (portCode) => {
  return haStatus.value[portCode]?.entity_id || ''
}

// Функция для получения friendly_name порта
const getPortFriendlyName = (portCode) => {
  return haStatus.value[portCode]?.friendly_name || ''
}

// Computed property для проверки наличия информации о бэкапах

// Загрузка данных устройства из API
const loadDeviceData = async (refreshPorts = false) => {
  try {
    const url = `/api/myhome/device/${props.device.id}/ports`
    const response = refreshPorts
      ? await secureFetch(`${url}/refresh`, {method: 'POST'})
      : await secureFetch(url)
    const data = await response.json()
    const sync = data?.device?.sync || {}
    const syncView = syncStateView[sync.sync_status] || syncStateView.not_started
    syncState.value = {
      status: sync.sync_status,
      ...syncView,
      title: sync.last_error || sync.offline_reason || sync.snapshot_at || 'Состояние синхронизации'
    }

    if (data?.ports && Array.isArray(data.ports)) {
      deviceData.value = data.ports.map(port => ({
        ...port,
        ha: port.ha || {
          ha_published: port.ha_published || false,
          entity_id: port.entity_id || ''
        }
      }))
    } else if (Array.isArray(data)) {
      deviceData.value = data
    } else {
      deviceData.value = []
    }

    if (refreshPorts && data?.changes) {
      portRefreshChanges.value = data.changes
      // Открываем диалог только если есть смысловые изменения —
      // шум от телеметрии (raw.floor, last_update, …) не должен всплывать.
      showPortChangesDialog.value = hasMeaningfulChanges.value
    }

    return data
  } catch (error) {
    console.warn('Failed to load device data:', error)
    deviceData.value = []
    throw error
  }
}

const loadVirtualOverview = async () => {
  try {
    const response = await secureFetch(`/api/myhome/device/${props.device.id}/ha/virtual-overview`)
    const data = await response.json()
    virtualOverview.value = data.physical_ports || []
  } catch (error) {
    console.warn('Failed to load virtual overview:', error)
    virtualOverview.value = []
  }
}

watch(virtualConfigMode, (enabled) => {
  if (enabled) loadVirtualOverview()
})


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

// Избранные порты устройства
const favoritePorts = ref([])
const favoritesFilter = ref(false)

const favoriteCodes = computed(() => new Set(favoritePorts.value.map(p => p.code)))

const handleFavoriteToggle = async (port) => {
  const index = favoritePorts.value.findIndex(p => p.code === port.code)
  if (index >= 0) {
    favoritePorts.value.splice(index, 1)
  } else {
    favoritePorts.value.push({ code: port.code, title: port.title || port.name || port.code })
  }
  try {
    await secureFetch(`/api/devices/${props.device.id}/favorite-ports`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ favorite_ports: favoritePorts.value })
    })
  } catch (error) {
    console.error('Error updating favorite ports:', error)
  }
}

// Загрузка данных при монтировании
onMounted(async () => {
  favoritePorts.value = Array.isArray(props.device.params?.favoritePorts)
    ? [...props.device.params.favoritePorts]
    : []
  await loadDeviceData()
  await loadVirtualOverview()
  await loadHASettings()
  await loadDeviceInfo()
  subscribeToPortUpdates()
  subscribeToDeviceUpdates()
})

// Состояние сворачивания групп
const expandedGroups = ref(new Set())


// Обработка данных из API для группировки
const processedGroups = computed(() => {
  const groups = {}
  const virtualStatusByCode = new Map(
    virtualOverview.value.map(port => [String(port.code), port.virtual_status])
  )
  const virtualUsageByCode = new Map(
    virtualOverview.value.map(port => [String(port.code), port.virtual_usage || []])
  )
  const enrichPort = (port) => ({
    ...port,
    virtual_status: virtualStatusByCode.get(String(port.code)) || port.virtual_status,
    virtual_usage: virtualUsageByCode.get(String(port.code)) || [],
    // HA-публикация определяется только виртуальными портами.
    ha: {
      ...(port.ha || {}),
      ha_published: (virtualUsageByCode.get(String(port.code)) || []).some(item => item.published_to_ha),
      entity_id: (virtualUsageByCode.get(String(port.code)) || []).find(item => item.published_to_ha)?.entity_id || ''
    }
  })

  const getRootGroup = (item) => {
    const code = String(item.code || '').toLowerCase()
    const title = String(item.title || '').toLowerCase()
    if (item.group_title) return item.group_title
    if (item.block_id) {
      const blockTitles = {
        system: 'System',
        gpio_24: 'HKL-EA8 outputs',
        gpio_26: 'HKL-EA8 inputs',
        buzzer: 'HKL-EA8 buzzer',
        my_485: 'MY_485',
        my_home_link: 'MY_HOME Link',
        floor_heating: 'Floor Heating',
        boiler_ctrl: 'Boiler',
        status: 'status'
      }
      return blockTitles[item.block_id] || item.block_id
    }
    if (['millis', 'network_priority'].includes(code) || code.startsWith('status.')) {
      return 'System'
    }
    if (code.startsWith('floor_heating.') || title.includes('отоплен') || title.includes('котёл')) {
      return 'Floor Heating'
    }
    if (code.startsWith('boiler_ctrl.') || code.startsWith('boiler_transport.')) {
      return 'Boiler'
    }
    return 'Основные'
  }

  deviceData.value.forEach(item => {
    if (item.data && Array.isArray(item.data)) {
      // Это группа с подгруппами
      const groupKey = item.title || item.code || 'Группа'
      groups[groupKey] = {
        title: groupKey,
        items: item.data.map(port => ({
          ...enrichPort(port),
          title: getPortTitle(port),
          haPublished: (virtualUsageByCode.get(String(port.code)) || []).some(item => item.published_to_ha)
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
      const groupKey = getRootGroup(item)
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
        ...enrichPort(item),
        title: getPortTitle(item),
        haPublished: (virtualUsageByCode.get(String(item.code)) || []).some(item => item.published_to_ha)
      })
    }
  })

  // Правильно инициализируем состояние групп
  const result = Object.values(groups)
  result.forEach(group => {
    const publishedCount = group.items.filter(item => item.haPublished).length
    const totalCount = group.items.length

    if (publishedCount === 0) {
      group.haPublished = false
    } else if (publishedCount === totalCount) {
      group.haPublished = true
    } else {
      group.haPublished = null // Частично выделено
    }
  })

  if (virtualConfigMode.value) {
    const virtualPorts = [
      {
        id: `virtual-status-${props.device.id}`,
        code: 'virtual.connection_status',
        title: 'Статус подключения',
        description: 'Состояние связи с физическим устройством',
        type: 'in.text',
        direction: 'in',
        val: isDeviceOnline.value ? 'online' : 'offline',
        unit: '',
        virtual: true,
        haPublished: false
      }
    ]

    // Служебные параметры платы можно включать в виртуальное устройство
    // тем же способом, что и обычные физические параметры.
    const serviceDefinitions = [
      { label: 'Время работы', match: code => /(^millis$|status\.uptime|run[_ .]?time|uptime)/i.test(code) },
      { label: 'Качество связи', match: code => /(^rssi$|wifi.*rssi|signal)/i.test(code) },
      { label: 'Приоритет сети', match: code => /network[_ .]?priority/i.test(code) },
      { label: 'Состояние синхронизации', match: code => /sync|connection[_ .]?status/i.test(code) },
      { label: 'Версия прошивки', match: code => /firmware|fw[_ .]?version|software[_ .]?version/i.test(code) },
      { label: 'Имя конфигурации', match: code => /config(?:uration)?[_ .]?name/i.test(code) },
      { label: 'Хеш конфигурации', match: code => /config(?:uration)?.*(hash|checksum)|config[_ .]?hash/i.test(code) }
    ]
    const allDevicePorts = []
    deviceData.value.forEach(item => {
      if (Array.isArray(item.data)) allDevicePorts.push(...item.data)
      else if (item.code) allDevicePorts.push(item)
    })
    // Канонический набор одинаков для любой платы: по одному пункту на лейбл,
    // первый подходящий физический код становится источником данных.
    const addedServiceLabels = new Set()
    serviceDefinitions.forEach(definition => {
      if (addedServiceLabels.has(definition.label)) return
      const port = allDevicePorts.find(item => definition.match(String(item.code || '')))
      if (!port) return
      addedServiceLabels.add(definition.label)
      virtualPorts.push({
        ...port,
        id: `virtual-service-${definition.label}`,
        // Отдельный префикс, чтобы состояние чекбокса в «Виртуальном
        // представлении» не делилось со стором реального физического порта.
        code: `virtual-service:${port.code}`,
        physical_code: port.code,
        title: definition.label,
        description: `Служебный параметр платы: ${port.code}`,
        virtual: true,
        virtual_service: true,
        ha: port.ha || { ha_published: false, entity_id: '' },
        haPublished: port.ha?.ha_published || false
      })
    })

    result.unshift({
      title: 'Виртуальное представление',
      items: virtualPorts,
      hasSubgroups: false,
      tpl: 'default',
      type: 'virtual',
      haPublished: true
    })
  }

  return result
})

const visibleProcessedGroups = computed(() => {
  const query = virtualFilter.value.trim().toLowerCase()
  if (!virtualConfigMode.value || (!query && !hideVirtualPublished.value)) {
    return processedGroups.value
  }

  return processedGroups.value
    .map(group => ({
      ...group,
      items: (group.items || []).filter(port => {
        const name = `${port.title || ''} ${port.name || ''} ${port.code || ''}`.toLowerCase()
        const isPublished = Boolean(
          port.ha?.ha_published || port.haPublished || port.published || port.virtual_status === 'used'
        )
        return (!query || name.includes(query)) && (!hideVirtualPublished.value || !isPublished)
      })
    }))
    .filter(group => group.type === 'file_list' || group.items.length > 0)
})

function getPortTitle(item) {
  if (item.title || item.name || item.label) {
    return item.title || item.name || item.label
  }
  const code = String(item.code || '')
  const parts = code.split('.')
  const suffix = parts[parts.length - 1]
  if (suffix && /^\d+$/.test(suffix)) {
    return `${parts.slice(0, -1).join(' · ')} · Канал ${Number(suffix) + 1}`
  }
  return code || 'Без названия'
}

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

// Функции для работы с HA публикацией перенесены в PortsTable.vue


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

    const requestBody = {
      settings: {
        publishedPorts,
        publishedGroups
      }
    }

    console.log('[DeviceCard] Sending HA settings:', requestBody)

    const response = await secureFetch(`/api/devices/${props.device.id}/ha-settings`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: requestBody
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

// Функции для работы с индикацией изменений HA перенесены в PortsTable.vue

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

const handlePortUpdate = async (code, value) => {
  try {
    // Команда идёт через backend API: он нормализует 0/1 в 0/255 для
    // digital-портов и возвращает явный результат отправки на плату.
    const response = await secureFetch(`/api/myhome/device/${props.device.id}/command`, {
      method: 'POST',
      body: {code, value}
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      console.error('Device command was not sent:', error.error || response.status)
    }

  } catch (error) {
    console.error('Error sending command to device:', error)
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
        selectedLogFile.value = {name: 'backup.log'}
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

const deleteBackup = async (timestamp) => {
  if (!confirm(`Удалить бэкап от «${formatTimestamp(timestamp)}»?`)) return

  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/backup/${encodeURIComponent(timestamp)}`, {
      method: 'DELETE'
    })
    const result = await response.json().catch(() => ({}))
    if (!response.ok || result.success === false) {
      throw new Error(result.detail || result.error || 'Не удалось удалить бэкап')
    }

    showNotification(result.backup_deleted ? 'Бэкап удалён' : 'Запись из журнала удалена', 'success')
    await loadBackupHistory()
  } catch (error) {
    console.error('Error deleting backup:', error)
    showNotification(error.message || 'Ошибка удаления бэкапа', 'error')
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
const refreshingDeviceData = ref(false)
const deviceInfo = ref(null)

// IP адрес устройства
const deviceIP = computed(() => {
  const deviceData = Object.keys(localDeviceData.value).length > 0 ? localDeviceData.value : props.device
  return deviceData?.params?.ip || deviceData?.ip || null
})

// Функция копирования IP адреса
const copyDeviceIP = async () => {
  const ip = deviceIP.value
  if (!ip) {
    messageStore.showWarning('IP адрес устройства не найден')
    return
  }
  
  try {
    await navigator.clipboard.writeText(ip)
    messageStore.showSuccess(`IP адрес ${ip} скопирован в буфер обмена`)
  } catch (error) {
    console.error('Error copying IP:', error)
    messageStore.showError('Ошибка копирования IP адреса')
  }
}

const deleteDevice = async () => {
  if (!confirm(`Удалить устройство «${props.device.name}»?`)) return

  try {
    const response = await secureFetch(`/api/myhome/device/${props.device.id}`, {
      method: 'DELETE'
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.error || 'Не удалось удалить устройство')
    }
    messageStore.showSuccess('Устройство удалено')
    emit('deleted', props.device.id)
  } catch (error) {
    console.error('Error deleting device:', error)
    messageStore.showError(error.message || 'Ошибка удаления устройства')
  }
}

// Принудительная загрузка данных устройства
const refreshDeviceData = async () => {
  refreshingDeviceData.value = true
  try {
    // Перечитываем физическую конфигурацию и показываем diff.
    const refreshResult = await loadDeviceData(true)
    
    // Запрашиваем обновленные данные устройства из базы
    const response = await secureFetch(`/api/devices/${props.device.id}`)
    if (response.ok) {
      const updatedDevice = await response.json()
      // Обновляем локальные данные
      localDeviceData.value = updatedDevice
      // Эмитим событие для обновления родительского компонента
      emit('device-updated', updatedDevice)
      messageStore.showSuccess(
        refreshResult?.changes?.has_changes
          ? 'Порты обновлены. Найдены изменения конфигурации.'
          : 'Порты обновлены, изменений не найдено.'
      )
      showDeviceUpdate()
    }
  } catch (error) {
    console.error('Error refreshing device data:', error)
    messageStore.showError('Ошибка обновления данных устройства')
  } finally {
    refreshingDeviceData.value = false
  }
}

const openHAIntegrationAfterPortRefresh = () => {
  showPortChangesDialog.value = false
  showDetailsModal.value = true
  detailsTab.value = 'ports'
}

const loadingDeviceInfo = ref(false)

// Загрузка информации об устройстве с /info
const loadDeviceInfo = async () => {
  // Пробуем получить IP из разных источников
  let ip = deviceIP.value
  
  // Если IP не найден, пробуем получить из props.device
  if (!ip) {
    ip = props.device?.params?.ip || props.device?.ip || null
  }
  
  if (!ip) {
    deviceInfo.value = { error: 'IP адрес устройства не найден. Убедитесь, что устройство подключено к сети.' }
    loadingDeviceInfo.value = false
    return
  }
  
  loadingDeviceInfo.value = true
  try {
    const response = await secureFetch(`/api/live/${ip}/info`)
    if (response.ok) {
      const data = await response.json()
      deviceInfo.value = data
    } else {
      const errorData = await response.json().catch(() => ({}))
      deviceInfo.value = { error: errorData.error || 'Ошибка загрузки информации', ip: ip }
    }
  } catch (error) {
    console.error('Error loading device info:', error)
    deviceInfo.value = { error: error.message || 'Ошибка соединения', ip: ip }
  } finally {
    loadingDeviceInfo.value = false
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
        selectedLogFile.value = {name: `${filename} (${formatTimestamp(timestamp)})`}
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
      body: JSON.stringify({ favorite_ports: favoritePorts })
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

/* ============ Новая шапка карточки устройства ============ */
.device-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px 10px 15px;
  background: linear-gradient(
    180deg,
    rgba(var(--v-theme-primary), 0.08) 0%,
    rgba(var(--v-theme-primary), 0.03) 100%
  );
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  box-shadow: inset 0 -1px 0 rgba(0, 0, 0, 0.04);
  position: relative;
}

.device-header::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: rgb(var(--v-theme-success));
  transition: background-color 0.2s ease;
}

.device-header--offline::before {
  background: rgb(var(--v-theme-error));
}

.device-header--offline {
  background: linear-gradient(
    180deg,
    rgba(var(--v-theme-error), 0.08) 0%,
    rgba(var(--v-theme-error), 0.02) 100%
  );
}

.device-header__row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.device-header__row--identity {
  min-height: 32px;
}

.device-header__row--status {
  min-height: 28px;
  flex-wrap: wrap;
  row-gap: 6px;
}

/* --- Левая часть первой строки: иконка + имя + id --- */
.device-header__identity {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1 1 auto;
}

.device-header__chip-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
  flex-shrink: 0;
}

.device-header__name {
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: 0.1px;
  line-height: 1.2;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-header__id {
  all: unset;
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: 10px;
  background: rgba(var(--v-theme-info, 33, 150, 243), 0.12);
  color: rgb(var(--v-theme-info));
  font-size: 0.72rem;
  font-weight: 600;
  line-height: 1.4;
  cursor: pointer;
  transition: background-color 0.15s ease;
  flex-shrink: 0;
  white-space: nowrap;
}

.device-header__id:hover {
  background: rgba(var(--v-theme-info, 33, 150, 243), 0.22);
}

.device-header__pulse {
  display: inline-flex;
  width: 10px;
  height: 10px;
  margin-left: 2px;
  flex-shrink: 0;
}

/* --- Правая часть первой строки: кнопки действий --- */
.device-header__actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

/* --- Статусные чипы --- */
.device-header__status {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1 1 auto;
  min-width: 0;
  flex-wrap: wrap;
  row-gap: 6px;
}

.device-status-chip {
  white-space: nowrap;
}

.device-ha-badge {
  margin-right: 8px; /* чтобы «1»-бейдж не наезжал на соседа */
}

.device-ha-badge :deep(.v-badge__badge) {
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  font-size: 0.62rem;
  font-weight: 600;
}

/* --- Метрики (бэкап / логи) и кнопка «Детали» --- */
.device-header__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  margin-left: auto;
  padding-left: 8px;
}

.device-header__metric {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  background: transparent;
  color: rgba(var(--v-theme-on-surface), 0.72);
  font-size: 0.72rem;
  line-height: 1.2;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.device-header__metric:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.04);
  border-color: rgba(0, 0, 0, 0.2);
}

.device-header__metric:disabled {
  cursor: progress;
  opacity: 0.7;
}

.device-header__metric--success { color: rgb(var(--v-theme-success)); border-color: rgba(var(--v-theme-success), 0.35); }
.device-header__metric--warning { color: rgb(var(--v-theme-warning)); border-color: rgba(var(--v-theme-warning), 0.35); }
.device-header__metric--error   { color: rgb(var(--v-theme-error));   border-color: rgba(var(--v-theme-error), 0.35); }
.device-header__metric--grey    { color: rgba(var(--v-theme-on-surface), 0.55); }

.device-header__details {
  flex-shrink: 0;
}

@media (max-width: 600px) {
  .device-header {
    padding: 8px 10px;
  }
  .device-header__name {
    font-size: 0.9rem;
  }
  .device-header__meta {
    margin-left: 0;
    width: 100%;
    justify-content: flex-end;
  }
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
  .device-toolbar {
    min-height: 64px;
  }

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

.badge-number{
  margin: -25px 0 0 4px;
}

.virtual-selection-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 8px;
  border: 1px solid rgba(255, 152, 0, 0.45);
  border-radius: 4px;
  background: rgba(255, 152, 0, 0.06);
}

.virtual-filter {
  flex: 1 1 180px;
  max-width: 260px;
}

.virtual-selection-toolbar :deep(.v-selection-control) {
  min-height: 32px;
}

.virtual-port-settings-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.virtual-port-settings {
  padding: 10px;
  border: 1px solid rgba(0, 0, 0, 0.14);
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.02);
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
