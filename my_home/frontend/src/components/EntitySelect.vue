<template>
  <v-autocomplete
    v-model="selectedValue"
    :items="filteredItems"
    :loading="loading"
    :search="searchText"
    @update:search="searchText = $event"
    item-title="displayText"
    item-value="value"
    :label="label"
    :hint="hint"
    :persistent-hint="!!hint"
    :variant="variant"
    :density="density"
    :hide-details="hideDetails"
    clearable
  >
    <!-- Секция фильтров внутри выпадающего списка -->
    <template v-slot:prepend-item>
      <v-list-item class="pa-0" @click.stop>
        <v-expansion-panels variant="accordion" class="entity-filter-panels" @click.stop>
          <v-expansion-panel @click.stop>
            <v-expansion-panel-title @click.stop>
              <div class="d-flex align-center">
                <v-icon class="me-2">mdi-filter</v-icon>
                <span>Фильтры</span>
                <v-badge
                  v-if="hasActiveFilters"
                  color="primary"
                  dot
                  class="ms-2"
                />
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text @click.stop>
              <div class="py-2" @click.stop>
                <!-- Фильтр по типу источника -->
                <v-select
                  v-model="filters.sourceType"
                  :items="[
                    { title: 'Все', value: 'all' },
                    { title: 'Home Assistant', value: 'ha' },
                    { title: 'MYHOME', value: 'myhome' }
                  ]"
                  label="Тип источника"
                  variant="outlined"
                  density="compact"
                  hide-details
                  class="mb-3"
                  :menu-props="{ closeOnContentClick: false }"
                  @click.stop
                />
                
                <!-- Фильтр по домену для HA -->
                <v-select
                  v-if="filters.sourceType === 'all' || filters.sourceType === 'ha'"
                  v-model="filters.haDomain"
                  :items="haDomains"
                  label="Домен HA"
                  variant="outlined"
                  density="compact"
                  hide-details
                  clearable
                  class="mb-3"
                  :menu-props="{ closeOnContentClick: false }"
                  @click.stop
                />
                
                <!-- Фильтр по device_class для HA -->
                <v-select
                  v-if="filters.sourceType === 'all' || filters.sourceType === 'ha'"
                  v-model="filters.haDeviceClass"
                  :items="haDeviceClasses"
                  label="Класс устройства HA"
                  variant="outlined"
                  density="compact"
                  hide-details
                  clearable
                  class="mb-3"
                  :menu-props="{ closeOnContentClick: false }"
                  @click.stop
                />
                
                <!-- Фильтр по типу порта для MYHOME -->
                <v-select
                  v-if="filters.sourceType === 'all' || filters.sourceType === 'myhome'"
                  v-model="filters.myhomePortType"
                  :items="myhomePortTypes"
                  label="Тип порта MYHOME"
                  variant="outlined"
                  density="compact"
                  hide-details
                  clearable
                  class="mb-3"
                  :menu-props="{ closeOnContentClick: false }"
                  @click.stop
                />
                
                <!-- Фильтр по устройству для MYHOME -->
                <v-select
                  v-if="filters.sourceType === 'all' || filters.sourceType === 'myhome'"
                  v-model="filters.myhomeDevice"
                  :items="myhomeDevices"
                  label="Устройство MYHOME"
                  variant="outlined"
                  density="compact"
                  hide-details
                  clearable
                  class="mb-3"
                  :menu-props="{ closeOnContentClick: false }"
                  @click.stop
                />
                
                <!-- Кнопка сброса фильтров -->
                <v-btn
                  v-if="hasActiveFilters"
                  color="primary"
                  variant="outlined"
                  block
                  size="small"
                  @click.stop="clearFilters"
                >
                  <v-icon start>mdi-filter-off</v-icon>
                  Сбросить фильтры
                </v-btn>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-list-item>
      <v-divider></v-divider>
    </template>
    <template v-slot:item="{ props, item }">
      <v-list-item v-bind="props">
        <template v-slot:prepend>
          <v-icon :color="item.raw.type === 'ha' ? 'primary' : 'success'">
            {{ item.raw.type === 'ha' ? 'mdi-home-assistant' : 'mdi-devices' }}
          </v-icon>
        </template>
        <v-list-item-title>
          <div class="d-flex align-center">
            <span class="font-weight-medium">{{ item.raw.title }}</span>
            <v-chip
              size="x-small"
              :color="item.raw.type === 'ha' ? 'primary' : 'success'"
              variant="tonal"
              class="ms-2"
            >
              {{ item.raw.type === 'ha' ? 'HA' : 'MYHOME' }}
            </v-chip>
          </div>
        </v-list-item-title>
        <v-list-item-subtitle>
          <div class="d-flex flex-column">
            <span v-if="item.raw.device" class="text-body-2 mb-1">
              <strong>Устройство:</strong> {{ item.raw.device }}
            </span>
            <span v-if="item.raw.entityId || item.raw.value || item.raw.code" class="text-caption text-grey mb-1">
              <strong>ID:</strong> {{ item.raw.entityId || item.raw.value || item.raw.code }}
            </span>
            <div v-if="item.raw.state || item.raw.unit || item.raw.portType" class="d-flex flex-wrap align-center gap-2 mt-1">
              <span v-if="item.raw.state !== undefined && item.raw.state !== ''" class="text-caption">
                <strong>Значение:</strong> {{ item.raw.state }}
                <span v-if="item.raw.unit">{{ item.raw.unit }}</span>
              </span>
              <span v-if="item.raw.portType" class="text-caption text-grey">
                <strong>Тип:</strong> {{ item.raw.portType }}
              </span>
            </div>
          </div>
        </v-list-item-subtitle>
      </v-list-item>
    </template>
    <template v-slot:selection="{ item }">
      <div class="d-flex align-center">
        <v-icon size="small" :color="item.raw.type === 'ha' ? 'primary' : 'success'" class="me-2">
          {{ item.raw.type === 'ha' ? 'mdi-home-assistant' : 'mdi-devices' }}
        </v-icon>
        <span>{{ item.raw.title }}</span>
      </div>
    </template>
  </v-autocomplete>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { secureFetch } from '@/services/fetch'

const props = defineProps({
  modelValue: {
    type: String,
    default: null
  },
  label: {
    type: String,
    default: 'Выберите entity'
  },
  hint: {
    type: String,
    default: ''
  },
  variant: {
    type: String,
    default: 'outlined'
  },
  density: {
    type: String,
    default: 'compact'
  },
  hideDetails: {
    type: Boolean,
    default: true
  },
  sourceFilter: {
    type: String,
    default: 'all', // 'all', 'ha', 'myhome'
    validator: (value) => ['all', 'ha', 'myhome'].includes(value)
  }
})

const emit = defineEmits(['update:modelValue'])

const selectedValue = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const loading = ref(false)
const searchText = ref('')
const haEntities = ref([])
const myhomePorts = ref([])

const filters = ref({
  sourceType: props.sourceFilter, // Используем prop для начального значения // all, ha, myhome
  haDomain: null,
  haDeviceClass: null,
  myhomePortType: null,
  myhomeDevice: null
})

const allItems = computed(() => {
  const items = []
  
  // Добавляем HA entities
  haEntities.value.forEach(entity => {
    const domain = entity.domain || (entity.entity_id ? entity.entity_id.split('.')[0] : '')
    items.push({
      type: 'ha',
      value: entity.entity_id,
      title: entity.friendly_name || entity.entity_id,
      device: `${domain.toUpperCase()}${entity.device_class ? ` - ${entity.device_class}` : ''}`,
      entityId: entity.entity_id,
      domain: domain,
      state: entity.state,
      unit: entity.unit_of_measurement,
      icon: entity.icon,
      deviceClass: entity.device_class,
      displayText: `${entity.friendly_name || entity.entity_id} (HA)`
    })
  })
  
  // Добавляем MYHOME ports
  myhomePorts.value.forEach(port => {
    const deviceName = port.device_name || port.device?.name || 'Unknown'
    const portName = port.name || port.label || port.code || 'Unknown'
    const entityId = port.entity_id || `${port.device_id}_${port.code}`
    const deviceInfo = port.device_name
      ? `${port.device_name}${port.device_model ? ` (${port.device_model})` : ''}`
      : 'Unknown Device'
    
    items.push({
      type: 'myhome',
      value: `myhome:${entityId}`,
      title: `${deviceName} - ${portName}`,
      device: deviceInfo,
      deviceName: deviceName, // Для фильтрации
      state: port.val || port.value || '',
      unit: port.unit || port.unit_of_measurement || '',
      code: port.code,
      portType: port.type || port.kind || '',
      displayText: `${deviceName} - ${portName} (MYHOME)`
    })
  })
  
  return items
})

// Получаем уникальные значения для фильтров
const haDomains = computed(() => {
  const domains = new Set()
  haEntities.value.forEach(entity => {
    if (entity.domain) {
      domains.add(entity.domain)
    }
  })
  return Array.from(domains).sort().map(d => ({ title: d, value: d }))
})

const haDeviceClasses = computed(() => {
  const classes = new Set()
  haEntities.value.forEach(entity => {
    if (entity.device_class) {
      classes.add(entity.device_class)
    }
  })
  return Array.from(classes).sort().map(c => ({ title: c, value: c }))
})

const myhomePortTypes = computed(() => {
  const types = new Set()
  myhomePorts.value.forEach(port => {
    const type = port.type || port.kind
    if (type) {
      types.add(type)
    }
  })
  return Array.from(types).sort().map(t => ({ title: t, value: t }))
})

const myhomeDevices = computed(() => {
  const devices = new Set()
  myhomePorts.value.forEach(port => {
    const deviceName = port.device_name || 'Unknown'
    if (deviceName) {
      devices.add(deviceName)
    }
  })
  return Array.from(devices).sort().map(d => ({ title: d, value: d }))
})

const hasActiveFilters = computed(() => {
  return (
    filters.value.sourceType !== 'all' ||
    filters.value.haDomain !== null ||
    filters.value.haDeviceClass !== null ||
    filters.value.myhomePortType !== null ||
    filters.value.myhomeDevice !== null
  )
})

const filteredItems = computed(() => {
  let items = allItems.value
  
  // Фильтр по типу источника (используем prop если задан, иначе фильтр)
  const effectiveSourceType = props.sourceFilter !== 'all' ? props.sourceFilter : filters.value.sourceType
  if (effectiveSourceType !== 'all') {
    items = items.filter(item => item.type === effectiveSourceType)
  }
  
  // Фильтр по домену HA
  if (filters.value.haDomain) {
    items = items.filter(item => {
      if (item.type !== 'ha') return true
      return item.domain === filters.value.haDomain
    })
  }
  
  // Фильтр по device_class HA
  if (filters.value.haDeviceClass) {
    items = items.filter(item => {
      if (item.type !== 'ha') return true
      return item.deviceClass === filters.value.haDeviceClass
    })
  }
  
  // Фильтр по типу порта MYHOME
  if (filters.value.myhomePortType) {
    items = items.filter(item => {
      if (item.type !== 'myhome') return true
      return item.portType === filters.value.myhomePortType
    })
  }
  
  // Фильтр по устройству MYHOME
  if (filters.value.myhomeDevice) {
    items = items.filter(item => {
      if (item.type !== 'myhome') return true
      return item.deviceName === filters.value.myhomeDevice
    })
  }
  
  // Поиск по тексту
  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    items = items.filter(item => {
      return (
        item.title.toLowerCase().includes(search) ||
        item.device.toLowerCase().includes(search) ||
        item.value.toLowerCase().includes(search) ||
        (item.entityId && item.entityId.toLowerCase().includes(search)) ||
        (item.code && item.code.toLowerCase().includes(search)) ||
        (item.state && item.state.toString().toLowerCase().includes(search)) ||
        (item.portType && item.portType.toLowerCase().includes(search)) ||
        (item.deviceClass && item.deviceClass.toLowerCase().includes(search)) ||
        (item.unit && item.unit.toLowerCase().includes(search))
      )
    })
  }
  
  return items
})

const clearFilters = () => {
  filters.value = {
    sourceType: 'all',
    haDomain: null,
    haDeviceClass: null,
    myhomePortType: null,
    myhomeDevice: null
  }
}

const loadHAEntities = async () => {
  try {
    const response = await secureFetch('/api/ha/entities')
    if (response.ok) {
      const data = await response.json()
      haEntities.value = data.entities || []
    }
  } catch (err) {
    console.error('Error loading HA entities:', err)
  }
}

const loadMyhomePorts = async () => {
  try {
    const response = await secureFetch('/api/live/ports')
    if (response.ok) {
      const data = await response.json()
      // Преобразуем порты в нужный формат
      const ports = []
      if (data.ports && Array.isArray(data.ports)) {
        data.ports.forEach(port => {
          if (port.device_id && port.code) {
            const entityId = port.entity_id || `${port.device_id}_${port.code}`
            ports.push({
              ...port,
              entity_id: entityId,
              device: {
                id: port.device_id,
                name: port.device_name || 'Unknown',
                model: port.device_model,
                vendor: port.device_vendor
              }
            })
          }
        })
      }
      myhomePorts.value = ports
    }
  } catch (err) {
    console.error('Error loading MYHOME ports:', err)
  }
}

const loadAll = async () => {
  loading.value = true
  try {
    await Promise.all([loadHAEntities(), loadMyhomePorts()])
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAll()
})

// При загрузке данных проверяем, нужно ли перезагрузить порты
watch(() => props.modelValue, (newVal) => {
  // Если значение начинается с myhome: и портов еще нет, загружаем
  if (newVal && newVal.startsWith('myhome:') && myhomePorts.value.length === 0) {
    loadMyhomePorts()
  }
}, { immediate: true })
</script>

<style scoped>
.entity-filter-panels {
  box-shadow: none !important;
}

.entity-filter-panels :deep(.v-expansion-panel-title) {
  padding: 8px 16px;
  min-height: 48px;
}

.entity-filter-panels :deep(.v-expansion-panel-text__wrapper) {
  padding: 8px 16px;
}

/* Предотвращаем закрытие выпадающего списка при клике на фильтры */
.entity-filter-panels :deep(.v-expansion-panel),
.entity-filter-panels :deep(.v-expansion-panel-title),
.entity-filter-panels :deep(.v-expansion-panel-text),
.entity-filter-panels :deep(.v-select),
.entity-filter-panels :deep(.v-btn) {
  pointer-events: auto;
}
</style>

