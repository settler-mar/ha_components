<template>
  <v-card class="ha-integration" v-if="showIntegration && integrationEnabled">
    <v-card-title class="d-flex align-center">
      <v-icon class="me-2">mdi-home-assistant</v-icon>
      Интеграция с Home Assistant
      <v-spacer></v-spacer>
      <v-chip size="small" color="primary" variant="outlined">
        {{ getTotalPublishedPorts() }} портов
      </v-chip>
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
                Данные будут передаваться при изменении в реальном времени.
              </v-alert>

              <!-- Группы портов -->
              <div v-for="group in processedGroups" :key="group.title" class="mb-4">
                <v-card variant="outlined">
                  <v-card-title class="py-2">
                    <div class="d-flex align-center">
                      <v-checkbox
                        v-model="group.published"
                        @change="toggleGroupPublishing(group)"
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
                            v-model="item.published"
                            @change="togglePortPublishing(item)"
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

              <v-divider class="my-4"></v-divider>
              
              <div class="d-flex justify-end">
                <v-btn
                  color="primary"
                  @click="saveSettings"
                  :loading="isSaving"
                >
                  Сохранить настройки
                </v-btn>
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
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { secureFetch } from '@/services/fetch'

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
const expandedPanels = ref(['settings'])

// Настройки
const settings = ref({
  publishedPorts: [],
  publishedGroups: []
})

// Данные
const publishedEntities = ref([])
const processedGroups = ref([])

// Заголовки таблицы сущностей
const entityHeaders = [
  { title: 'Entity ID', key: 'entity_id' },
  { title: 'Название', key: 'name' },
  { title: 'Тип', key: 'type' },
  { title: 'Состояние', key: 'state' },
  { title: 'Последнее обновление', key: 'last_seen' },
  { title: 'Действия', key: 'actions', sortable: false }
]

// Computed properties
const showIntegration = computed(() => {
  return true // Всегда показываем, но содержимое зависит от integrationEnabled
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
      count += group.items.filter(item => item.published).length
    }
  })
  return count
}

function getGroupPublishedCount(group) {
  if (group.published) {
    return group.items.length
  }
  return group.items.filter(item => item.published).length
}

function toggleGroupPublishing(group) {
  // Если группа включена, включаем все порты
  // Если выключена, выключаем все порты
  group.items.forEach(item => {
    item.published = group.published
  })
}

function togglePortPublishing(item) {
  // При изменении порта проверяем состояние группы
  const group = processedGroups.value.find(g => g.items.includes(item))
  if (group) {
    const publishedCount = group.items.filter(i => i.published).length
    if (publishedCount === 0) {
      group.published = false
    } else if (publishedCount === group.items.length) {
      group.published = true
    }
    // Если частично - оставляем группу как есть
  }
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

async function saveSettings() {
  isSaving.value = true
  try {
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        settings: {
          publishedPorts,
          publishedGroups
        }
      })
    })
    
    if (response.ok) {
      emit('settings-updated')
    }
  } catch (error) {
    console.error('Failed to save HA settings:', error)
  } finally {
    isSaving.value = false
  }
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
          published: false
        })),
        published: false
      }
    } else {
      // Это отдельный элемент
      const groupKey = 'Основные'
      if (!groups[groupKey]) {
        groups[groupKey] = {
          title: groupKey,
          items: [],
          published: false
        }
      }
      groups[groupKey].items.push({
        ...item,
        published: false
      })
    }
  })
  
  processedGroups.value = Object.values(groups)
}

function applySettingsToGroups() {
  processedGroups.value.forEach(group => {
    // Проверяем, опубликована ли вся группа
    group.published = settings.value.publishedGroups.includes(group.title)
    
    // Применяем настройки к портам
    group.items.forEach(item => {
      item.published = group.published || settings.value.publishedPorts.includes(item.code)
    })
  })
}

// Watchers
watch(() => props.ports, () => {
  processPortsData()
  applySettingsToGroups()
}, { immediate: true, deep: true })

watch(() => props.device, () => {
  loadSettings()
}, { immediate: true, deep: true })

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
</style>