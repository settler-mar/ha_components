<template>
  <div class="unified-ports-tab">
    <!-- Фильтры -->
    <div class="mb-2">
      <v-row dense>
        <v-col cols="12" md="3">
          <v-text-field
            v-model="searchQuery"
            prepend-inner-icon="mdi-magnify"
            label="Поиск портов"
            variant="outlined"
            density="compact"
            hide-details
            clearable
          ></v-text-field>
        </v-col>
        <v-col cols="6" md="2">
          <v-checkbox
            v-model="filters.favorites"
            label="Избранное"
            density="compact"
            hide-details
          ></v-checkbox>
        </v-col>
        <v-col cols="6" md="2">
          <v-select
            v-model="filters.type"
            :items="typeOptions"
            label="Тип"
            variant="outlined"
            density="compact"
            hide-details
            clearable
          ></v-select>
        </v-col>
        <v-col cols="6" md="2">
          <v-checkbox
            v-model="filters.logging"
            label="Логирование"
            density="compact"
            hide-details
          ></v-checkbox>
        </v-col>
        <v-col cols="6" md="3">
          <v-select
            v-if="filters.logging"
            v-model="filters.logFile"
            :items="logFileOptions"
            label="Файл лога"
            variant="outlined"
            density="compact"
            hide-details
            clearable
          ></v-select>
        </v-col>
      </v-row>
    </div>

    <!-- Настройки логирования в шапке -->
    <v-card variant="outlined" class="mb-2 logging-settings" v-if="logsConfigData">
      <div class="d-flex align-center flex-wrap gap-3 px-3 py-2">
        <div class="d-flex align-center">
          <v-icon size="18" class="me-2">mdi-file-document-multiple</v-icon>
          <span class="font-weight-medium">Логирование</span>
        </div>

        <div class="d-flex align-center flex-wrap gap-1">
          <v-chip
            v-for="file in logsConfigData.files || []"
            :key="file"
            size="x-small"
            variant="tonal"
            color="primary"
          >{{ file.replace('/logs/', '') }}</v-chip>
        </div>

        <v-spacer></v-spacer>

        <v-checkbox
          v-model="localLoggingSettings.enableLogging"
          label="Включено"
          density="compact"
          hide-details
        ></v-checkbox>
        <v-checkbox
          v-model="localLoggingSettings.saveLocally"
          label="Локально"
          density="compact"
          hide-details
        ></v-checkbox>

        <v-btn
          @click="refreshLogsConfig"
          :loading="loadingConfig"
          size="small"
          variant="text"
          icon="mdi-refresh"
          title="Обновить конфигурацию с устройства"
        ></v-btn>
      </div>
    </v-card>

    <!-- Таблица портов по группам -->
    <div v-for="group in filteredGroups" :key="group.title" class="mb-2">
      <v-card variant="outlined">
        <!-- Заголовок группы -->
        <v-card-title 
          @click="toggleGroupCollapse(group.title)"
          class="group-header cursor-pointer py-1 px-3"
        >
          <div class="d-flex align-center">
            <v-icon 
              :icon="isGroupCollapsed(group.title) ? 'mdi-chevron-right' : 'mdi-chevron-down'" 
              size="16" 
              class="me-2"
            ></v-icon>
            
            <v-icon :icon="getGroupIcon(group)" size="20" class="me-2"></v-icon>

            <span class="font-weight-medium">{{ group.title }}</span>

            <v-chip size="x-small" color="primary" variant="outlined" class="ms-2">
              {{ group.ports.length }}
            </v-chip>

            <v-icon
              v-if="group.ports.length && group.ports.every(isFavorite)"
              icon="mdi-star"
              color="amber"
              size="16"
              class="ms-1"
              title="Вся группа в избранном"
            ></v-icon>

            <v-icon
              v-if="group.ports.length && group.ports.every(isVirtualLinked)"
              icon="mdi-link-variant"
              color="purple"
              size="16"
              class="ms-1"
              title="Вся группа связана с виртуальными портами"
            ></v-icon>
          </div>
        </v-card-title>
        
        <!-- Таблица портов группы -->
        <v-expand-transition>
          <div v-show="!isGroupCollapsed(group.title)">
            <v-table density="compact" class="ports-compact-table">
              <thead>
                <tr>
                  <th style="width: 34px;"></th>
                  <th style="width: 28px;"></th>
                  <th class="text-left">Название</th>
                  <th class="text-left" style="width: 150px;">Код · тип</th>
                  <th class="text-right" style="width: 110px;">Значение</th>
                  <th class="text-left" style="width: 80px;">Ед.</th>
                  <th class="text-center" style="width: 160px;">Логирование</th>
                  <th style="width: 40px;"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="port in group.ports" :key="port.code" class="port-row">
                  <!-- Избранное -->
                  <td class="text-center">
                    <v-icon
                      :icon="isFavorite(port) ? 'mdi-star' : 'mdi-star-outline'"
                      :color="isFavorite(port) ? 'amber' : 'grey-lighten-1'"
                      size="18"
                      class="favorite-icon"
                      @click="toggleFavorite(port)"
                    ></v-icon>
                  </td>

                  <!-- Иконка типа + индикатор виртуального -->
                  <td class="text-center">
                    <v-tooltip location="top" :text="isVirtualLinked(port) ? 'Связан с виртуальным портом' : port.type || ''">
                      <template #activator="{ props: tp }">
                        <v-icon
                          v-bind="tp"
                          :color="isVirtualLinked(port) ? 'purple' : getPortIconColor(port)"
                          size="18"
                        >{{ isVirtualLinked(port) ? 'mdi-link-variant' : getPortIcon(port) }}</v-icon>
                      </template>
                    </v-tooltip>
                  </td>

                  <!-- Название (inline edit) -->
                  <td>
                    <v-text-field
                      :model-value="port.title"
                      @update:model-value="updatePortParam(port, 'title', $event)"
                      :placeholder="port.name || port.code"
                      variant="plain"
                      density="compact"
                      hide-details
                      single-line
                      class="inline-input inline-input--title"
                    ></v-text-field>
                  </td>

                  <!-- Код + тип -->
                  <td>
                    <div class="d-flex align-center">
                      <span class="text-caption text-grey text-truncate">{{ port.code }}</span>
                      <v-chip size="x-small" :color="getPortTypeColor(port.type)" variant="tonal" class="ms-1">
                        {{ port.type }}
                      </v-chip>
                    </div>
                  </td>

                  <!-- Значение (read-only) -->
                  <td class="text-right">
                    <span v-if="port.val !== undefined && port.val !== null" class="port-value">
                      {{ port.val }}
                    </span>
                    <span v-else class="text-grey">—</span>
                  </td>

                  <!-- Единица (inline edit) -->
                  <td>
                    <v-text-field
                      :model-value="port.unit"
                      @update:model-value="updatePortParam(port, 'unit', $event)"
                      placeholder="—"
                      variant="plain"
                      density="compact"
                      hide-details
                      single-line
                      class="inline-input inline-input--unit"
                    ></v-text-field>
                  </td>

                  <!-- Логирование -->
                  <td class="text-center">
                    <div v-if="getPortLogInfo(port)" class="d-flex align-center justify-center gap-1">
                      <v-checkbox
                        :model-value="getPortLogInfo(port).enabled"
                        @update:model-value="togglePortLogging(port, $event)"
                        hide-details
                        density="compact"
                        class="log-check"
                      ></v-checkbox>
                      <span class="text-caption text-grey text-truncate" :title="getPortLogInfo(port).fileName">
                        {{ getPortLogInfo(port).fileName }}
                      </span>
                    </div>
                    <span v-else class="text-grey">—</span>
                  </td>

                  <!-- Расширенное редактирование -->
                  <td class="text-center">
                    <v-btn
                      @click="editPortAdvanced(port)"
                      icon="mdi-dots-horizontal"
                      size="x-small"
                      variant="text"
                      title="Дополнительные параметры"
                    ></v-btn>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </div>
        </v-expand-transition>
      </v-card>
    </div>


    <!-- Кнопки сохранения -->
    <div class="d-flex gap-2">
      <v-btn 
        @click="saveAllSettings" 
        :loading="saving"
        color="primary"
        prepend-icon="mdi-content-save"
      >
        Сохранить все настройки
      </v-btn>
      
      <v-btn 
        @click="resetAllSettings" 
        variant="outlined"
        prepend-icon="mdi-restore"
      >
        Сбросить
      </v-btn>
    </div>

    <!-- Диалог дополнительных параметров порта -->
    <v-dialog v-model="showEditDialog" max-width="700px">
      <v-card>
        <v-card-title>
          <v-icon class="me-2">mdi-cog</v-icon>
          Дополнительные параметры: {{ editingPort?.title || editingPort?.code }}
        </v-card-title>
        
        <v-card-text>
          <div v-if="editingPort">
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="editingPort.title"
                  label="Название"
                  variant="outlined"
                  class="mb-3"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="editingPort.unit"
                  label="Единица измерения"
                  variant="outlined"
                  class="mb-3"
                ></v-text-field>
              </v-col>
            </v-row>

            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="editingPort.koef"
                  label="Коэффициент"
                  type="number"
                  step="0.01"
                  variant="outlined"
                  class="mb-3"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="editingPort.min_value"
                  label="Минимальное значение"
                  type="number"
                  variant="outlined"
                  class="mb-3"
                ></v-text-field>
              </v-col>
            </v-row>

            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="editingPort.max_value"
                  label="Максимальное значение"
                  type="number"
                  variant="outlined"
                  class="mb-3"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="editingPort.step"
                  label="Шаг изменения"
                  type="number"
                  step="0.01"
                  variant="outlined"
                  class="mb-3"
                ></v-text-field>
              </v-col>
            </v-row>

            <v-text-field
              v-model="editingPort.code"
              label="Код порта"
              variant="outlined"
              readonly
              class="mb-3"
            ></v-text-field>

            <v-textarea
              v-model="editingPort.description"
              label="Описание"
              variant="outlined"
              rows="3"
              class="mb-3"
            ></v-textarea>

          </div>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="showEditDialog = false">Отмена</v-btn>
          <v-btn @click="savePortEdit" color="primary" :loading="savingPort">
            Сохранить все
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const props = defineProps({
  deviceId: {
    type: Number,
    required: true
  },
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
  'update-port-param',
  'update-ha-settings',
  'update-favorite-ports',
  'notification'
])

// Reactive data
const searchQuery = ref('')
const showEditDialog = ref(false)
const showHAConfigDialog = ref(false)
const editingPort = ref(null)
const haConfigPort = ref(null)
const saving = ref(false)
const savingPort = ref(false)
const savingHA = ref(false)
const loadingConfig = ref(false)

// Фильтры
const filters = ref({
  favorites: false,
  type: '',
  logging: false,
  logFile: ''
})

// Локальные настройки
const favoritePorts = ref([])
const publishedToHA = ref(new Set())
const collapsedGroups = ref(new Set())
const logsConfigData = ref(null)
const localLoggingSettings = ref({
  enableLogging: false,
  saveLocally: false
})

// HA конфигурация
const haConfig = ref({
  name: '',
  prefix: 'my_home',
  deviceClass: '',
  icon: ''
})

// Опции для фильтров
const typeOptions = computed(() => {
  const types = new Set()
  props.portsData.forEach(port => {
    if (port.type) {
      types.add(port.type)
    }
  })
  return Array.from(types).map(type => ({ title: type, value: type }))
})

const logFileOptions = computed(() => {
  if (!logsConfigData.value?.files) return []
  return logsConfigData.value.files.map(file => ({
    title: file.replace('/logs/', ''),
    value: file.replace('/logs/', '').replace('.txt', '')
  }))
})

// Опции для HA
const deviceClassOptions = [
  { title: 'Температура', value: 'temperature' },
  { title: 'Влажность', value: 'humidity' },
  { title: 'Давление', value: 'pressure' },
  { title: 'Освещенность', value: 'illuminance' },
  { title: 'Энергия', value: 'energy' },
  { title: 'Мощность', value: 'power' },
  { title: 'Напряжение', value: 'voltage' },
  { title: 'Ток', value: 'current' },
  { title: 'Переключатель', value: 'switch' },
  { title: 'Свет', value: 'light' },
  { title: 'Датчик', value: 'sensor' }
]

// Computed
const filteredGroups = computed(() => {
  // Группируем порты по группам
  const groupsMap = new Map()
  
  let filteredPorts = props.portsData
  
  // Фильтр по поиску
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filteredPorts = filteredPorts.filter(port => {
      const title = (port.title || '').toLowerCase()
      const name = (port.name || '').toLowerCase()
      const code = (port.code || '').toLowerCase()
      const type = (port.type || '').toLowerCase()
      
      return title.includes(query) || 
             name.includes(query) || 
             code.includes(query) || 
             type.includes(query)
    })
  }
  
  // Фильтр по избранному
  if (filters.value.favorites) {
    filteredPorts = filteredPorts.filter(port => isFavorite(port))
  }
  
  // Фильтр по типу
  if (filters.value.type) {
    filteredPorts = filteredPorts.filter(port => port.type === filters.value.type)
  }
  
  // Фильтр по логированию
  if (filters.value.logging) {
    filteredPorts = filteredPorts.filter(port => {
      const logInfo = getPortLogInfo(port)
      if (!logInfo) return false
      
      // Если выбран конкретный файл лога
      if (filters.value.logFile) {
        return logInfo.fileName === filters.value.logFile
      }
      
      return logInfo.enabled
    })
  }
  
  // Группируем отфильтрованные порты
  filteredPorts.forEach(port => {
    const groupName = port.group || 'Без группы'
    
    if (!groupsMap.has(groupName)) {
      groupsMap.set(groupName, {
        title: groupName,
        ports: []
      })
    }
    
    groupsMap.get(groupName).ports.push(port)
  })
  
  return Array.from(groupsMap.values()).sort((a, b) => a.title.localeCompare(b.title))
})

// Methods
const getPortIcon = (port) => {
  const type = port.type || ''
  if (type.includes('analog')) return 'mdi-gauge'
  if (type.includes('digital') || type.includes('didgi')) return 'mdi-toggle-switch'
  if (type.includes('color')) return 'mdi-palette'
  if (type.includes('list')) return 'mdi-format-list-bulleted'
  return 'mdi-circle-outline'
}

const getPortIconColor = (port) => {
  const type = port.type || ''
  if (type.includes('analog')) return 'blue'
  if (type.includes('digital') || type.includes('didgi')) return 'green'
  if (type.includes('color')) return 'purple'
  if (type.includes('list')) return 'orange'
  return 'grey'
}

const getPortTypeColor = (type) => {
  if (!type) return 'grey'
  if (type.includes('in.')) return 'primary'
  if (type.includes('out.')) return 'success'
  return 'secondary'
}

const isFavorite = (port) => {
  return favoritePorts.value.some(fav => fav.code === port.code)
}

const isVirtualLinked = (port) => {
  return Array.isArray(port.virtual_usage) && port.virtual_usage.length > 0
}

const isPublishedToHA = (port) => {
  return publishedToHA.value.has(port.code)
}

// Методы для групп
const getGroupIcon = (group) => {
  const title = group.title.toLowerCase()
  if (title.includes('sensor') || title.includes('датчик')) return 'mdi-eye'
  if (title.includes('light') || title.includes('свет')) return 'mdi-lightbulb'
  if (title.includes('switch') || title.includes('переключ')) return 'mdi-toggle-switch'
  if (title.includes('climate') || title.includes('климат')) return 'mdi-thermostat'
  if (title.includes('power') || title.includes('энерг')) return 'mdi-lightning-bolt'
  return 'mdi-folder'
}

const toggleGroupCollapse = (groupTitle) => {
  if (collapsedGroups.value.has(groupTitle)) {
    collapsedGroups.value.delete(groupTitle)
  } else {
    collapsedGroups.value.add(groupTitle)
  }
}

const isGroupCollapsed = (groupTitle) => {
  return collapsedGroups.value.has(groupTitle)
}

// Методы для логирования
const getPortLogInfo = (port) => {
  if (!logsConfigData.value?.out) return null
  
  const index = logsConfigData.value.out.findIndex(code => code === port.code)
  if (index === -1) return null
  
  return {
    enabled: logsConfigData.value.out_gs?.[index] === 1,
    fileName: logsConfigData.value.out_file_name?.[index] || '',
    saveLocally: localLoggingSettings.value.saveLocally
  }
}

const togglePortLogging = (port, enabled) => {
  if (!logsConfigData.value?.out) return
  
  const index = logsConfigData.value.out.findIndex(code => code === port.code)
  if (index === -1) return
  
  if (!logsConfigData.value.out_gs) logsConfigData.value.out_gs = []
  while (logsConfigData.value.out_gs.length <= index) {
    logsConfigData.value.out_gs.push(0)
  }
  
  logsConfigData.value.out_gs[index] = enabled ? 1 : 0
}

const togglePortLocalSave = (port, saveLocally) => {
  // Это локальная настройка, обновляем для всех портов
  localLoggingSettings.value.saveLocally = saveLocally
}

const refreshLogsConfig = async () => {
  loadingConfig.value = true
  try {
    const response = await fetch(`/api/devices/${props.deviceId}/logs-config?refresh=true`)
    if (response.ok) {
      logsConfigData.value = await response.json()
      emit('notification', {
        text: 'Конфигурация логов обновлена с устройства',
        color: 'success'
      })
    } else {
      throw new Error('Ошибка загрузки конфигурации')
    }
  } catch (error) {
    emit('notification', {
      text: `Ошибка загрузки конфигурации: ${error.message}`,
      color: 'error'
    })
  } finally {
    loadingConfig.value = false
  }
}

// Методы для inline редактирования
const updatePortParam = async (port, param, value) => {
  try {
    // Обновляем локально
    port[param] = value
    
    // Отправляем на сервер
    emit('update-port-param', {
      code: port.code,
      updates: { [param]: value }
    })
  } catch (error) {
    emit('notification', {
      text: `Ошибка обновления ${param}: ${error.message}`,
      color: 'error'
    })
  }
}

const getHAName = (port) => {
  // Получаем текущее название HA для порта
  return port.haName || port.title || port.name || port.code
}

const updateHAName = async (port, name) => {
  try {
    // Обновляем локально
    port.haName = name
    
    // Сохраняем настройки HA
    emit('update-ha-settings', {
      publishedPorts: Array.from(publishedToHA.value),
      portSettings: {
        [port.code]: {
          name: name,
          prefix: 'my_home',
          deviceClass: getDefaultDeviceClass(port),
          icon: getDefaultIcon(port)
        }
      }
    })
  } catch (error) {
    emit('notification', {
      text: `Ошибка обновления HA: ${error.message}`,
      color: 'error'
    })
  }
}

// Методы для HA
const configureHA = (port) => {
  haConfigPort.value = port
  haConfig.value = {
    name: port.title || port.name || port.code,
    prefix: 'my_home',
    deviceClass: getDefaultDeviceClass(port),
    icon: getDefaultIcon(port)
  }
  showHAConfigDialog.value = true
}

const getDefaultDeviceClass = (port) => {
  const type = (port.type || '').toLowerCase()
  if (type.includes('temperature')) return 'temperature'
  if (type.includes('humidity')) return 'humidity'
  if (type.includes('pressure')) return 'pressure'
  if (type.includes('power')) return 'power'
  if (type.includes('energy')) return 'energy'
  if (type.includes('voltage')) return 'voltage'
  if (type.includes('current')) return 'current'
  if (type.includes('switch')) return 'switch'
  if (type.includes('light')) return 'light'
  return 'sensor'
}

const getDefaultIcon = (port) => {
  const type = (port.type || '').toLowerCase()
  if (type.includes('temperature')) return 'mdi-thermometer'
  if (type.includes('humidity')) return 'mdi-water-percent'
  if (type.includes('pressure')) return 'mdi-gauge'
  if (type.includes('power')) return 'mdi-lightning-bolt'
  if (type.includes('energy')) return 'mdi-flash'
  if (type.includes('voltage')) return 'mdi-sine-wave'
  if (type.includes('current')) return 'mdi-current-ac'
  if (type.includes('switch')) return 'mdi-toggle-switch'
  if (type.includes('light')) return 'mdi-lightbulb'
  return 'mdi-eye'
}

const saveHAConfig = async () => {
  savingHA.value = true
  try {
    // Здесь будет сохранение конфигурации HA для порта
    emit('notification', {
      text: 'Настройки HA сохранены',
      color: 'success'
    })
    showHAConfigDialog.value = false
  } catch (error) {
    emit('notification', {
      text: `Ошибка сохранения: ${error.message}`,
      color: 'error'
    })
  } finally {
    savingHA.value = false
  }
}

const toggleFavorite = (port) => {
  if (isFavorite(port)) {
    const index = favoritePorts.value.findIndex(fav => fav.code === port.code)
    if (index > -1) {
      favoritePorts.value.splice(index, 1)
    }
  } else {
    favoritePorts.value.push(port)
  }
}

const toggleHA = (port) => {
  if (publishedToHA.value.has(port.code)) {
    publishedToHA.value.delete(port.code)
  } else {
    publishedToHA.value.add(port.code)
  }
}

const removeFavorite = (port) => {
  const index = favoritePorts.value.findIndex(fav => fav.code === port.code)
  if (index > -1) {
    favoritePorts.value.splice(index, 1)
  }
}

const moveFavoriteUp = (index) => {
  if (index > 0) {
    const temp = favoritePorts.value[index]
    favoritePorts.value[index] = favoritePorts.value[index - 1]
    favoritePorts.value[index - 1] = temp
  }
}

const moveFavoriteDown = (index) => {
  if (index < favoritePorts.value.length - 1) {
    const temp = favoritePorts.value[index]
    favoritePorts.value[index] = favoritePorts.value[index + 1]
    favoritePorts.value[index + 1] = temp
  }
}


const editPort = (port) => {
  editingPort.value = { ...port }
  showEditDialog.value = true
}

const editPortAdvanced = (port) => {
  editingPort.value = { ...port }
  showEditDialog.value = true
}

const savePortEdit = async () => {
  if (!editingPort.value) return
  
  savingPort.value = true
  try {
    // Сохраняем параметры порта
    emit('update-port-param', {
      code: editingPort.value.code,
      updates: {
        title: editingPort.value.title,
        unit: editingPort.value.unit,
        koef: editingPort.value.koef,
        min_value: editingPort.value.min_value,
        max_value: editingPort.value.max_value,
        step: editingPort.value.step,
        description: editingPort.value.description
      }
    })
    
    // Сохраняем настройки HA если порт опубликован
    if (isPublishedToHA(editingPort.value)) {
      emit('update-ha-settings', {
        publishedPorts: Array.from(publishedToHA.value),
        portSettings: {
          [editingPort.value.code]: {
            name: editingPort.value.haName,
            prefix: editingPort.value.haPrefix || 'my_home',
            deviceClass: editingPort.value.haDeviceClass,
            icon: editingPort.value.haIcon
          }
        }
      })
    }
    
    // Обновляем локальные данные
    const originalPort = props.portsData.find(p => p.code === editingPort.value.code)
    if (originalPort) {
      Object.assign(originalPort, editingPort.value)
    }
    
    emit('notification', {
      text: 'Параметры порта сохранены',
      color: 'success'
    })
    
    showEditDialog.value = false
    editingPort.value = null
  } catch (error) {
    emit('notification', {
      text: `Ошибка сохранения: ${error.message}`,
      color: 'error'
    })
  } finally {
    savingPort.value = false
  }
}

const publishToHA = async () => {
  publishing.value = true
  try {
    // Здесь будет логика публикации в HA
    emit('notification', {
      text: 'Публикация в Home Assistant выполнена',
      color: 'success'
    })
  } catch (error) {
    emit('notification', {
      text: `Ошибка публикации: ${error.message}`,
      color: 'error'
    })
  } finally {
    publishing.value = false
  }
}

const saveAllSettings = async () => {
  saving.value = true
  try {
    // Сохраняем избранные порты
    emit('update-favorite-ports', favoritePorts.value)
    
    // Сохраняем настройки HA
    emit('update-ha-settings', {
      publishedPorts: Array.from(publishedToHA.value)
    })
    
    emit('notification', {
      text: 'Все настройки сохранены',
      color: 'success'
    })
  } catch (error) {
    emit('notification', {
      text: `Ошибка сохранения: ${error.message}`,
      color: 'error'
    })
  } finally {
    saving.value = false
  }
}

const resetAllSettings = () => {
  favoritePorts.value = []
  publishedToHA.value.clear()
  emit('notification', {
    text: 'Настройки сброшены',
    color: 'info'
  })
}

// Load settings on mount
onMounted(async () => {
  if (props.deviceData?.favoritePorts) {
    favoritePorts.value = [...props.deviceData.favoritePorts]
  }
  
  if (props.deviceData?.haSettings?.publishedPorts) {
    props.deviceData.haSettings.publishedPorts.forEach(code => {
      publishedToHA.value.add(code)
    })
  }
  
  if (props.logsConfig && Object.keys(props.logsConfig).length > 0) {
    if (props.logsConfig.files) {
      // Конфигурация с устройства
      logsConfigData.value = props.logsConfig
    } else {
      // Локальные настройки
      localLoggingSettings.value = { ...props.logsConfig }
    }
  }
  
  // Загружаем кешированную конфигурацию логов
  try {
    const response = await fetch(`/api/devices/${props.deviceId}/logs-config`)
    if (response.ok) {
      logsConfigData.value = await response.json()
    }
  } catch (error) {
    console.warn('Could not load logs config:', error)
  }
})
</script>

<style scoped>
.unified-ports-tab {
  padding: 4px 0;
}

.gap-1 {
  gap: 4px;
}

.gap-2 {
  gap: 8px;
}

.group-header {
  transition: background-color 0.2s;
}

.group-header:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.cursor-pointer {
  cursor: pointer;
}

.port-row {
  transition: background-color 0.2s;
}

.port-row:hover {
  background-color: rgba(0, 0, 0, 0.02);
}

.port-info-cell {
  min-width: 200px;
}

.v-table th {
  background-color: #f5f5f5;
  font-weight: 600;
}

.v-table td {
  vertical-align: top;
  padding: 4px 8px;
}

.v-table th {
  white-space: nowrap;
  padding: 4px 8px !important;
  font-size: 0.75rem;
}

.compact-card :deep(.v-btn) {
  min-width: 0;
}

.compact-card :deep(.v-col) {
  padding-top: 2px;
  padding-bottom: 2px;
}

/* Компактная таблица портов */
.ports-compact-table :deep(td),
.ports-compact-table :deep(th) {
  padding: 2px 6px !important;
  height: 34px !important;
}

.ports-compact-table :deep(th) {
  font-size: 0.7rem;
  color: rgba(0, 0, 0, 0.55);
  font-weight: 500;
}

.inline-input :deep(.v-field__input) {
  min-height: 24px !important;
  padding: 0 4px !important;
  font-size: 0.85rem;
}

.inline-input :deep(.v-field) {
  background: transparent;
  border-radius: 3px;
  transition: background-color 0.15s ease;
}

.inline-input :deep(.v-field:hover) {
  background: rgba(0, 0, 0, 0.04);
}

.inline-input :deep(.v-field--focused) {
  background: rgba(25, 118, 210, 0.06);
  box-shadow: inset 0 -1px 0 rgba(25, 118, 210, 0.6);
}

.inline-input--title :deep(.v-field__input) {
  font-weight: 500;
}

.inline-input--unit :deep(.v-field__input) {
  text-align: center;
}

.port-value {
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

.favorite-icon {
  cursor: pointer;
  transition: transform 0.15s ease;
}

.favorite-icon:hover {
  transform: scale(1.2);
}

.log-check :deep(.v-selection-control) {
  min-height: 20px !important;
}

.log-check :deep(.v-selection-control__wrapper) {
  height: 20px !important;
  width: 20px !important;
}

.port-row:hover {
  background-color: rgba(25, 118, 210, 0.04);
}

/* Стили для чекбоксов в таблице */
.unified-ports-tab :deep(.v-checkbox .v-selection-control) {
  min-height: 24px !important;
}

.unified-ports-tab :deep(.v-checkbox .v-label) {
  font-size: 0.7rem !important;
}

/* Адаптивные стили */
@media (max-width: 768px) {
  .ports-compact-table :deep(td),
  .ports-compact-table :deep(th) {
    padding: 2px 4px !important;
  }

  .inline-input :deep(.v-field__input) {
    font-size: 0.8rem;
  }
}
</style>
