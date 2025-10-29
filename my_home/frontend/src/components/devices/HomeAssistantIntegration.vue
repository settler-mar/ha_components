<template>
  <v-card class="ha-integration" v-if="showIntegration && integrationEnabled">
    <v-card-title class="d-flex align-center">
      <v-icon class="me-2">mdi-home-assistant</v-icon>
      Интеграция с Home Assistant
      <v-spacer></v-spacer>
      <v-chip size="small" color="primary" variant="outlined">
        {{ getTotalPublishedPorts() }} портов
      </v-chip>
      <!-- Индикатор изменений -->
      <div v-if="hasPendingChanges" class="d-flex align-center ms-2">
        <v-btn
          icon
          size="small"
          variant="text"
          @click="showChangesDialog = true"
          class="change-indicator-btn"
        >
          <v-badge
            :content="getTotalChangesCount()"
            color="primary"
            overlap
          >
            <v-icon color="primary">mdi-cog-outline</v-icon>
          </v-badge>
        </v-btn>
      </div>
      
      <!-- Кнопка синхронизации -->
      <v-btn
        icon
        size="small"
        variant="text"
        @click="syncStates"
        :loading="syncLoading"
        class="ms-2"
        title="Синхронизировать состояния с Home Assistant"
      >
        <v-icon color="success">mdi-sync</v-icon>
      </v-btn>
    </v-card-title>

    <v-card-text>
      <v-alert
        v-if="!isConnected"
        type="warning"
        variant="tonal"
        class="mb-4"
      >
        <v-alert-title>Нет подключения к Home Assistant</v-alert-title>
        Проверьте настройки подключения в конфигурации аддона.
      </v-alert>

      <v-alert
        v-else
        type="success"
        variant="tonal"
        class="mb-4"
      >
        <v-alert-title>Подключено к Home Assistant</v-alert-title>
        Данные передаются при изменении в реальном времени.
      </v-alert>

      <!-- Режим настройки интеграции -->
      <v-expansion-panels v-model="expandedPanels" multiple>
        <v-expansion-panel value="settings">
          <v-expansion-panel-title>
            <v-icon class="me-2">mdi-cog</v-icon>
            Настройки интеграции
            <v-spacer></v-spacer>
            <v-chip size="small" color="primary" variant="outlined">
              {{ getTotalPublishedPorts() }} портов
            </v-chip>
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-form>
              <div class="text-h6 mb-3">Выбор портов для публикации</div>
              <v-alert type="info" variant="tonal" class="mb-4">
                Включите чекбоксы для портов и групп, которые нужно публиковать в Home Assistant.
                Изменения будут применены после подтверждения.
              </v-alert>

              <!-- Фильтры -->
              <v-card variant="outlined" class="mb-4">
                <v-card-title class="py-2">
                  <v-icon class="me-2">mdi-filter</v-icon>
                  Фильтры
                </v-card-title>
                <v-card-text class="pt-0">
                  <v-row>
                    <v-col cols="12" md="6">
                      <v-text-field
                        v-model="filters.searchQuery"
                        label="Поиск портов"
                        prepend-inner-icon="mdi-magnify"
                        variant="outlined"
                        density="compact"
                        clearable
                      ></v-text-field>
                    </v-col>
                    <v-col cols="12" md="6">
                      <v-btn-toggle
                        v-model="filters"
                        multiple
                        variant="outlined"
                        density="compact"
                      >
                        <v-btn
                          :value="{ showAll: true, showPublished: false, showUnpublished: false }"
                          @click="filters.showAll = true; filters.showPublished = false; filters.showUnpublished = false"
                        >
                          Все
                        </v-btn>
                        <v-btn
                          :value="{ showPublished: true }"
                          @click="filters.showPublished = !filters.showPublished; filters.showAll = false"
                        >
                          Опубликованные
                        </v-btn>
                        <v-btn
                          :value="{ showUnpublished: true }"
                          @click="filters.showUnpublished = !filters.showUnpublished; filters.showAll = false"
                        >
                          Неопубликованные
                        </v-btn>
                      </v-btn-toggle>
                    </v-col>
                  </v-row>
                </v-card-text>
              </v-card>

              <!-- Группы портов -->
              <div v-for="group in filteredGroups" :key="group.title" class="mb-4">
                <v-card variant="outlined">
                  <v-card-title class="py-2">
                    <div class="d-flex align-center">
                      <v-checkbox
                        :model-value="group.haPublished"
                        @update:model-value="(value) => toggleGroupPublishing(group, value)"
                        class="me-2"
                        hide-details
                      ></v-checkbox>
                      <v-icon :icon="getGroupIcon(group)" class="me-2"></v-icon>
                      <span>{{ group.title }}</span>
                      <v-spacer></v-spacer>
                      <v-chip size="small" color="primary" variant="outlined">
                        {{ group.items.length }} портов
                      </v-chip>
                      <v-chip
                        v-if="getGroupPublishedCount(group) > 0"
                        size="small"
                        color="orange"
                        variant="outlined"
                        class="ms-2"
                      >
                        {{ getGroupPublishedCount(group) }} опубликовано
                      </v-chip>
                    </div>
                  </v-card-title>

                  <v-card-text v-if="group.items.length" class="pt-0">
                    <v-list density="compact">
                      <v-list-item
                        v-for="item in group.items"
                        :key="item.code"
                        class="px-0"
                      >
                        <template #prepend>
                          <v-checkbox
                            :model-value="item.haPublished"
                            @update:model-value="(value) => togglePortPublishing(item, value)"
                            hide-details
                            class="me-2"
                          ></v-checkbox>
                        </template>

                        <v-list-item-title>
                          <div class="d-flex align-center">
                            <v-icon
                              :icon="getPortIcon(item)"
                              size="16"
                              :color="getPortColor(item)"
                              class="me-2"
                            ></v-icon>
                            <span>{{ item.title || item.code }}</span>
                            <v-spacer></v-spacer>
                            <span class="text-caption text-grey me-2">
                              {{ formatValue(item) }}
                              <span v-if="item.unit">{{ item.unit }}</span>
                            </span>
                            <v-chip
                              v-if="item.published"
                              size="x-small"
                              color="orange"
                              variant="tonal"
                            >
                              HA
                            </v-chip>
                          </div>
                        </v-list-item-title>
                      </v-list-item>
                    </v-list>
                  </v-card-text>
                </v-card>
              </div>
            </v-form>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel value="entities">
          <v-expansion-panel-title>
            <v-icon class="me-2">mdi-view-grid</v-icon>
            Сущности в Home Assistant
            <v-spacer></v-spacer>
            <v-chip size="small" color="primary" variant="outlined">
              {{ publishedEntities.length }}
            </v-chip>
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-data-table
              :headers="entityHeaders"
              :items="publishedEntities"
              density="compact"
              :loading="isLoadingEntities"
            >
              <template #item.state="{ item }">
                <v-chip
                  :color="item.state === 'online' ? 'success' : 'error'"
                  size="small"
                  variant="tonal"
                >
                  {{ item.state }}
                </v-chip>
              </template>
              <template #item.last_seen="{ item }">
                {{ formatTime(item.last_seen) }}
              </template>
              <template #item.actions="{ item }">
                <v-btn
                  size="small"
                  variant="outlined"
                  @click="viewEntity(item)"
                >
                  <v-icon size="small">mdi-eye</v-icon>
                </v-btn>
              </template>
            </v-data-table>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card-text>

    <!-- Диалог настройки порта -->
    <PortConfigDialog
      v-model:show="showPortConfigDialog"
      :port="selectedPort"
      :device="device"
      @save="handlePortConfigSave"
    />

    <!-- Диалог подтверждения изменений -->
    <v-dialog v-model="showChangesDialog" max-width="800" scrollable>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="me-2">mdi-cog-outline</v-icon>
          Подтверждение изменений
          <v-spacer></v-spacer>
          <v-btn
            icon
            variant="text"
            @click="showChangesDialog = false"
          >
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>

        <v-card-text>
          <v-alert type="info" variant="tonal" class="mb-4">
            Подтвердите изменения в настройках публикации портов в Home Assistant.
          </v-alert>

          <!-- Порты для добавления -->
          <div v-if="portsToAdd.length > 0" class="mb-4">
            <h3 class="text-h6 mb-2 d-flex align-center">
              <v-icon class="me-2" color="success">mdi-plus</v-icon>
              Порты для добавления ({{ portsToAdd.length }})
            </h3>
            <v-card variant="outlined">
              <v-list density="compact">
                <template v-for="group in getGroupedChanges(portsToAdd)" :key="`add-${group.deviceId}`">
                  <v-list-subheader>{{ group.deviceName }}</v-list-subheader>
                  <v-list-item
                    v-for="port in group.ports"
                    :key="port.code"
                    class="px-4"
                  >
                    <template #prepend>
                      <v-checkbox
                        v-model="port.selected"
                        hide-details
                        color="success"
                      ></v-checkbox>
                    </template>
                    <v-list-item-title>
                      <div class="d-flex align-center">
                        <v-icon
                          :icon="getPortIcon(port)"
                          size="16"
                          :color="getPortColor(port)"
                          class="me-2"
                        ></v-icon>
                        <span>{{ port.title || port.code }}</span>
                        <v-spacer></v-spacer>
                        <v-btn
                          size="small"
                          variant="outlined"
                          @click="configurePort(port)"
                        >
                          <v-icon size="small">mdi-cog</v-icon>
                        </v-btn>
                      </div>
                    </v-list-item-title>
                  </v-list-item>
                </template>
              </v-list>
            </v-card>
          </div>

          <!-- Порты для удаления -->
          <div v-if="portsToRemove.length > 0" class="mb-4">
            <h3 class="text-h6 mb-2 d-flex align-center">
              <v-icon class="me-2" color="error">mdi-minus</v-icon>
              Порты для удаления ({{ portsToRemove.length }})
            </h3>
            <v-card variant="outlined">
              <v-list density="compact">
                <template v-for="group in getGroupedChanges(portsToRemove)" :key="`remove-${group.deviceId}`">
                  <v-list-subheader>{{ group.deviceName }}</v-list-subheader>
                  <v-list-item
                    v-for="port in group.ports"
                    :key="port.code"
                    class="px-4"
                  >
                    <template #prepend>
                      <v-checkbox
                        v-model="port.selected"
                        hide-details
                        color="error"
                      ></v-checkbox>
                    </template>
                    <v-list-item-title>
                      <div class="d-flex align-center">
                        <v-icon
                          :icon="getPortIcon(port)"
                          size="16"
                          :color="getPortColor(port)"
                          class="me-2"
                        ></v-icon>
                        <span>{{ port.title || port.code }}</span>
                        <v-spacer></v-spacer>
                        <v-chip size="x-small" color="orange" variant="tonal">
                          HA
                        </v-chip>
                      </div>
                    </v-list-item-title>
                  </v-list-item>
                </template>
              </v-list>
            </v-card>
          </div>

          <!-- Если нет изменений -->
          <v-alert v-if="!hasPendingChanges" type="info" variant="tonal">
            Нет изменений для применения.
          </v-alert>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            variant="text"
            @click="discardAllChanges"
            :disabled="!hasPendingChanges"
          >
            Отменить все
          </v-btn>
          <v-btn
            color="primary"
            @click="applyChanges"
            :loading="isSaving"
            :disabled="!hasSelectedChanges"
          >
            Применить изменения
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import {ref, computed, onMounted, watch} from 'vue'
import {secureFetch} from '@/services/fetch'
import PortConfigDialog from './PortConfigDialog.vue'

const props = defineProps({
  device: {
    type: Object,
    required: true
  },
  ports: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['settings-updated'])

// Состояние компонента
const integrationEnabled = ref(false)
const isConnected = ref(false)
const isLoading = ref(false)
const isSaving = ref(false)
const isLoadingEntities = ref(false)
const syncLoading = ref(false)
const expandedPanels = ref(['settings'])
const showChangesDialog = ref(false)
const showPortConfigDialog = ref(false)
const selectedPort = ref(null)

// Настройки
const settings = ref({
  publishedPorts: [],
  publishedGroups: []
})

// Данные
const publishedEntities = ref([])
const processedGroups = ref([])

// Отслеживание изменений
const portsToAdd = ref([])
const portsToRemove = ref([])

// Фильтры
const filters = ref({
  showAll: true,
  showPublished: false,
  showUnpublished: false,
  searchQuery: ''
})

// Заголовки таблицы сущностей
const entityHeaders = [
  {title: 'Entity ID', key: 'entity_id'},
  {title: 'Название', key: 'name'},
  {title: 'Тип', key: 'type'},
  {title: 'Состояние', key: 'state'},
  {title: 'Последнее обновление', key: 'last_seen'},
  {title: 'Действия', key: 'actions', sortable: false}
]

// Computed properties
const showIntegration = computed(() => {
  return true // Всегда показываем, но содержимое зависит от integrationEnabled
})

// Отслеживание изменений
const hasPendingChanges = computed(() => {
  return portsToAdd.value.length > 0 || portsToRemove.value.length > 0
})

const hasSelectedChanges = computed(() => {
  const selectedToAdd = portsToAdd.value.filter(p => p.selected).length
  const selectedToRemove = portsToRemove.value.filter(p => p.selected).length
  return selectedToAdd > 0 || selectedToRemove > 0
})

// Фильтрованные группы
const filteredGroups = computed(() => {
  if (filters.value.showAll) {
    return processedGroups.value
  }

  return processedGroups.value.map(group => {
    const filteredItems = group.items.filter(item => {
      // Фильтр по статусу публикации
      if (filters.value.showPublished && !item.haPublished) return false
      if (filters.value.showUnpublished && item.haPublished) return false
      
      // Фильтр по поисковому запросу
      if (filters.value.searchQuery) {
        const query = filters.value.searchQuery.toLowerCase()
        const title = (item.title || item.name || item.code || '').toLowerCase()
        const code = (item.code || '').toLowerCase()
        return title.includes(query) || code.includes(query)
      }
      
      return true
    })

    return {
      ...group,
      items: filteredItems
    }
  }).filter(group => group.items.length > 0)
})

// Функции для работы с группами
function getGroupIcon(group) {
  const title = group.title.toLowerCase()
  if (title.includes('clock') || title.includes('время')) return 'mdi-clock'
  if (title.includes('light') || title.includes('свет')) return 'mdi-lightbulb'
  if (title.includes('ws-') || title.includes('led')) return 'mdi-led-strip'
  if (title.includes('wifi') || title.includes('сеть')) return 'mdi-wifi'
  if (title.includes('sensor') || title.includes('датчик')) return 'mdi-eye'
  if (title.includes('основные')) return 'mdi-cog'
  return 'mdi-folder'
}

function getPortIcon(item) {
  if (item.type) {
    if (item.type.includes('temp')) return 'mdi-thermometer'
    if (item.type.includes('humidity')) return 'mdi-water-percent'
    if (item.type.includes('pressure')) return 'mdi-gauge'
    if (item.type.includes('voltage') || item.type.includes('current') || item.type.includes('power')) return 'mdi-lightning-bolt'
    if (item.type.includes('energy')) return 'mdi-battery'
    if (item.type.includes('switch') || item.type.includes('button')) return 'mdi-toggle-switch'
    if (item.type.includes('sensor')) return 'mdi-eye'
    if (item.type.includes('out.')) return 'mdi-cog'
  }
  return 'mdi-circle-outline'
}

function getPortColor(item) {
  if (item.type) {
    if (item.type.includes('temp')) return 'orange'
    if (item.type.includes('humidity')) return 'blue'
    if (item.type.includes('pressure')) return 'purple'
    if (item.type.includes('voltage') || item.type.includes('current') || item.type.includes('power')) return 'red'
    if (item.type.includes('energy')) return 'green'
    if (item.type.includes('switch') || item.type.includes('button')) return 'primary'
    if (item.type.includes('sensor')) return 'teal'
    if (item.type.includes('out.')) return 'grey'
  }
  return 'grey'
}

function formatValue(item) {
  if (item.val !== undefined && item.val !== null) {
    if (item.type === 'out.list' && item.list) {
      return item.list[item.val] || item.val
    }
    return item.val
  }
  return '-'
}

function formatTime(timestamp) {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString()
}

// Функции для работы с публикацией
function getTotalPublishedPorts() {
  let count = 0
  processedGroups.value.forEach(group => {
    if (group.published) {
      count += group.items.length
    } else {
      count += group.items.filter(item => item.haPublished).length
    }
  })
  return count
}

function getGroupPublishedCount(group) {
  if (group.published) {
    return group.items.length
  }
  return group.items.filter(item => item.haPublished).length
}

function toggleGroupPublishing(group, value) {
  // Если группа включена, включаем все порты
  // Если выключена, выключаем все порты
  group.haPublished = value
  group.items.forEach(item => {
    item.haPublished = value
  })
  updateChangesTracking()
}

function togglePortPublishing(item, value) {
  // При изменении порта проверяем состояние группы
  item.haPublished = value
  const group = processedGroups.value.find(g => g.items.includes(item))
  if (group) {
    const publishedCount = group.items.filter(i => i.haPublished).length
    if (publishedCount === 0) {
      group.haPublished = false
    } else if (publishedCount === group.items.length) {
      group.haPublished = true
    }
    // Если частично - оставляем группу как есть
  }
  updateChangesTracking()
}

// API функции
async function loadSettings() {
  try {
    // Получаем настройки из params устройства
    const haSettings = props.device.params?.ha_integration || {}
    integrationEnabled.value = haSettings.enabled ?? true

    settings.value = {
      publishedPorts: haSettings.publishedPorts || [],
      publishedGroups: haSettings.publishedGroups || []
    }

    // Применяем настройки к группам
    applySettingsToGroups()
  } catch (error) {
    console.warn('Failed to load HA settings:', error)
    integrationEnabled.value = true
  }
}

// Функции для отслеживания изменений
function updateChangesTracking() {
  portsToAdd.value = []
  portsToRemove.value = []

  processedGroups.value.forEach(group => {
    group.items.forEach(item => {
      const wasPublished = item.published
      const willBePublished = item.haPublished

      if (!wasPublished && willBePublished) {
        // Порт добавляется
        portsToAdd.value.push({
          ...item,
          deviceId: props.device.id,
          deviceName: props.device.name || props.device.code,
          selected: true
        })
      } else if (wasPublished && !willBePublished) {
        // Порт удаляется
        portsToRemove.value.push({
          ...item,
          deviceId: props.device.id,
          deviceName: props.device.name || props.device.code,
          selected: true
        })
      }
    })
  })
}

function getTotalChangesCount() {
  return portsToAdd.value.length + portsToRemove.value.length
}

function getGroupedChanges(ports) {
  const grouped = {}
  ports.forEach(port => {
    if (!grouped[port.deviceId]) {
      grouped[port.deviceId] = {
        deviceId: port.deviceId,
        deviceName: port.deviceName,
        ports: []
      }
    }
    grouped[port.deviceId].ports.push(port)
  })
  return Object.values(grouped)
}

function configurePort(port) {
  selectedPort.value = port
  showPortConfigDialog.value = true
}

function handlePortConfigSave(data) {
  // Сохраняем конфигурацию порта
  const { port, config } = data
  
  // Находим порт в списке и сохраняем его конфигурацию
  processedGroups.value.forEach(group => {
    group.items.forEach(item => {
      if (item.code === port.code) {
        item.haConfig = config
      }
    })
  })
  
  console.log('Port configuration saved:', data)
}

function discardAllChanges() {
  // Отменяем все изменения
  processedGroups.value.forEach(group => {
    group.haPublished = group.published
    group.items.forEach(item => {
      item.haPublished = item.published
    })
  })
  portsToAdd.value = []
  portsToRemove.value = []
  showChangesDialog.value = false
}

async function applyChanges() {
  isSaving.value = true
  try {
    // Применяем только выбранные изменения
    const selectedToAdd = portsToAdd.value.filter(p => p.selected)
    const selectedToRemove = portsToRemove.value.filter(p => p.selected)

    // Обновляем состояние портов
    selectedToAdd.forEach(port => {
      const group = processedGroups.value.find(g => g.items.some(i => i.code === port.code))
      if (group) {
        const item = group.items.find(i => i.code === port.code)
        if (item) {
          item.published = true
          item.haPublished = true
        }
      }
    })

    selectedToRemove.forEach(port => {
      const group = processedGroups.value.find(g => g.items.some(i => i.code === port.code))
      if (group) {
        const item = group.items.find(i => i.code === port.code)
        if (item) {
          item.published = false
          item.haPublished = false
        }
      }
    })

    // Сохраняем настройки
    const publishedPorts = []
    const publishedGroups = []

    processedGroups.value.forEach(group => {
      if (group.published) {
        publishedGroups.push(group.title)
      } else {
        group.items.forEach(item => {
          if (item.published) {
            publishedPorts.push(item.code)
          }
        })
      }
    })

    const response = await secureFetch(`/api/devices/${props.device.id}/ha-settings`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: {
        settings: {
          publishedPorts,
          publishedGroups
        }
      }
    })

    if (response.ok) {
      // Очищаем отслеживание изменений
      portsToAdd.value = []
      portsToRemove.value = []
      showChangesDialog.value = false
      emit('settings-updated')
    }
  } catch (error) {
    console.error('Failed to save HA settings:', error)
  } finally {
    isSaving.value = false
  }
}

async function saveSettings() {
  // Старая функция сохранения (теперь не используется напрямую)
  await applyChanges()
}


async function testConnection() {
  try {
    const response = await secureFetch('/api/ha/test-connection')
    const data = await response.json()
    isConnected.value = data.connected || false
  } catch (error) {
    console.warn('Failed to test HA connection:', error)
    isConnected.value = false
  }
}

async function loadEntities() {
  isLoadingEntities.value = true
  try {
    const response = await secureFetch(`/api/devices/${props.device.id}/ha-entities`)
    const data = await response.json()
    publishedEntities.value = data.entities || []
  } catch (error) {
    console.warn('Failed to load HA entities:', error)
    publishedEntities.value = []
  } finally {
    isLoadingEntities.value = false
  }
}

async function syncStates() {
  syncLoading.value = true
  try {
    const response = await secureFetch(`/api/ha/sync-states`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        device_id: props.device.id
      })
    })
    
    const data = await response.json()
    
    if (data.success) {
      // Показываем уведомление об успешной синхронизации
      console.log(`Синхронизировано ${data.synced_count} из ${data.total_states} состояний`)
      
      // Обновляем данные портов
      await loadSettings()
    } else {
      console.error('Ошибка синхронизации:', data.error)
    }
  } catch (error) {
    console.error('Error syncing states:', error)
  } finally {
    syncLoading.value = false
  }
}

function viewEntity(entity) {
  // TODO: Реализовать просмотр сущности
  console.log('View entity:', entity)
}

// Обработка данных портов
function processPortsData() {
  const groups = {}

  props.ports.forEach(item => {
    if (item.data && Array.isArray(item.data)) {
      // Это группа с подгруппами
      const groupKey = item.title || item.code || 'Группа'
      groups[groupKey] = {
        title: groupKey,
        items: item.data.map(port => ({
          ...port,
          published: port.ha?.ha_published || false,
          haPublished: port.ha?.ha_published || false
        })),
        published: false,
        haPublished: false
      }
    } else {
      // Это отдельный элемент
      const groupKey = 'Основные'
      if (!groups[groupKey]) {
        groups[groupKey] = {
          title: groupKey,
          items: [],
          published: false,
          haPublished: false
        }
      }
      groups[groupKey].items.push({
        ...item,
        published: item.ha?.ha_published || false,
        haPublished: item.ha?.ha_published || false
      })
    }
  })

  processedGroups.value = Object.values(groups)
}

function applySettingsToGroups() {
  processedGroups.value.forEach(group => {
    // Проверяем, опубликована ли вся группа
    group.published = settings.value.publishedGroups.includes(group.title)
    group.haPublished = group.published

    // Применяем настройки к портам
    group.items.forEach(item => {
      // Используем данные из базы данных о публикации в HA
      const isPublishedInDB = item.ha?.ha_published || false
      const isPublishedInSettings = settings.value.publishedPorts.includes(item.code)
      
      item.published = group.published || isPublishedInSettings
      // haPublished должен отражать реальный статус из базы данных
      // В режиме редактирования показываем текущий статус из HA
      item.haPublished = isPublishedInDB
    })
  })
}

// Watchers
watch(() => props.ports, () => {
  processPortsData()
  applySettingsToGroups()
}, {immediate: true, deep: true})

watch(() => props.device, () => {
  loadSettings()
}, {immediate: true, deep: true})

// Lifecycle
onMounted(async () => {
  await loadSettings()
  await testConnection()
  if (integrationEnabled.value) {
    await loadEntities()
  }
})
</script>

<style scoped>
.ha-integration {
  margin-top: 16px;
}

.v-list-item {
  min-height: 40px;
}

.change-indicator-btn {
  position: relative;
}

.change-indicator-btn .v-badge {
  position: absolute;
  top: -8px;
  right: -8px;
}

.change-indicator-btn .v-badge .v-badge__badge {
  font-size: 0.7rem;
  min-width: 18px;
  height: 18px;
}
</style>
