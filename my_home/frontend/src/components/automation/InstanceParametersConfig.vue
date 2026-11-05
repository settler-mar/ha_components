<template>
  <div>
    <div v-for="param in parameters" :key="param.name" class="mb-4">
      <div class="text-body-2 font-weight-medium mb-1">
        {{ param.name }}
        <v-chip v-if="param.required" size="x-small" color="error" variant="tonal" class="ms-1">
          Обязательный
        </v-chip>
        <v-chip v-if="param.type" size="x-small" variant="outlined" class="ms-1">
          {{ param.type }}
        </v-chip>
      </div>
      <div v-if="param.description" class="text-caption text-grey mb-2">
        {{ param.description }}
      </div>
      
      <!-- Поле 1: Тип значения -->
      <v-select
        v-model="paramData[param.name].valueType"
        :items="getValueTypeOptions(param)"
        label="Тип"
        density="compact"
        variant="outlined"
        class="mb-2"
        @update:model-value="onValueTypeChange(param)"
      >
        <template v-slot:item="{ props, item }">
          <v-list-item v-bind="props">
            <template v-slot:prepend>
              <v-icon>{{ getValueTypeIcon(item.value) }}</v-icon>
            </template>
          </v-list-item>
        </template>
      </v-select>
      
      <!-- Поле 2: Значение/Entity -->
      <!-- Для фиксированного значения -->
      <div v-if="paramData[param.name].valueType === 'fixed'">
        <v-text-field
          v-if="param.type === 'str'"
          v-model="paramData[param.name].value"
          label="Значение"
          variant="outlined"
          density="compact"
          @update:model-value="updateValue"
        />
        <v-switch
          v-else-if="param.type === 'bool'"
          v-model="paramData[param.name].value"
          label="Значение"
          density="compact"
          @update:model-value="updateValue"
        />
        <v-text-field
          v-else
          v-model.number="paramData[param.name].value"
          label="Значение"
          :type="param.type === 'int' ? 'number' : 'number'"
          :step="param.type === 'float' ? '0.1' : '1'"
          variant="outlined"
          density="compact"
          @update:model-value="updateValue"
        />
      </div>
      
      <!-- Для динамичного значения - универсальный компонент выбора -->
      <!-- Если доступен только виртуальный порт (без HA/MYHOME) - показываем выбор виртуального порта -->
      <v-select
        v-else-if="hasOnlyVirtualPort(param)"
        v-model="paramData[param.name].value"
        :items="virtualPorts"
        item-title="name"
        item-value="entity_id"
        label="Entity"
        variant="outlined"
        density="compact"
        @update:model-value="updateValue"
      >
        <template v-slot:prepend-inner>
          <v-icon>mdi-link-variant</v-icon>
        </template>
        <template v-slot:item="{ props, item }">
          <v-list-item v-bind="props">
            <template v-slot:prepend>
              <v-icon>{{ item.raw.icon || 'mdi-link-variant' }}</v-icon>
            </template>
            <v-list-item-title>{{ item.raw.name }}</v-list-item-title>
            <v-list-item-subtitle>{{ item.raw.entity_id }} ({{ item.raw.type }})</v-list-item-subtitle>
          </v-list-item>
        </template>
      </v-select>
      
      <!-- Если доступны только HA и/или MYHOME (без virtual) - используем EntitySelect -->
      <EntitySelect
        v-else-if="hasOnlyHAOrMYHOME(param)"
        v-model="paramData[param.name].value"
        label="Entity"
        :source-filter="getFirstDynamicSource(param)"
        @update:model-value="updateValue"
      />
      
      <!-- Если доступны несколько типов (HA/MYHOME + virtual) или все источники - показываем EntitySelect с возможностью выбора типа -->
      <EntitySelect
        v-else
        v-model="paramData[param.name].value"
        label="Entity"
        @update:model-value="updateValue"
      />
    </div>
    <div v-if="parameters.length === 0" class="text-caption text-grey">
      Нет параметров
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import EntitySelect from '@/components/EntitySelect.vue'
import { secureFetch } from '@/services/fetch'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({})
  },
  parameters: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue'])

// Структура данных параметра: { source: "fixed"|"ha"|"myhome"|"virtual", value: any }
const paramData = ref({})

// Загружаем список виртуальных портов
const virtualPorts = ref([])

const loadVirtualPorts = async () => {
  try {
    // Пробуем загрузить виртуальные порты из API
    // Если endpoint не существует, используем пустой список
    const response = await secureFetch('/api/virtual-ports')
    if (response.ok) {
      const data = await response.json()
      virtualPorts.value = data.ports || data || []
    } else if (response.status === 404) {
      // Endpoint не существует - виртуальные порты не поддерживаются
      virtualPorts.value = []
    }
  } catch (err) {
    // Если ошибка - просто используем пустой список
    console.warn('Virtual ports endpoint not available:', err)
    virtualPorts.value = []
  }
}

// Инициализация параметров
const initializeParam = (param) => {
  if (!paramData.value[param.name]) {
    const existingValue = props.modelValue[param.name]
    
    // Если значение уже есть, пытаемся определить его структуру
    if (existingValue !== undefined && existingValue !== null) {
      if (typeof existingValue === 'object' && existingValue.source) {
        // Уже структурированное значение - это динамичный источник
        paramData.value[param.name] = {
          valueType: 'dynamic',
          source: existingValue.source,
          value: existingValue.value
        }
      } else {
        // Старое значение - это фиксированное
        paramData.value[param.name] = {
          valueType: 'fixed',
          source: null,
          value: existingValue
        }
      }
    } else {
      // Новый параметр - выбираем тип по умолчанию
      const hasFixed = !param.allowed_sources || param.allowed_sources.length === 0 || param.allowed_sources.includes('fixed')
      const hasDynamic = !param.allowed_sources || param.allowed_sources.length === 0 || 
        param.allowed_sources.some(s => ['ha', 'myhome', 'virtual'].includes(s))
      
      let valueType = 'fixed'
      let value = param.default !== undefined ? param.default : getDefaultValueForType(param.type)
      
      // Если есть только динамичные источники, выбираем динамичный
      if (!hasFixed && hasDynamic) {
        valueType = 'dynamic'
        value = null
      }
      
      paramData.value[param.name] = {
        valueType,
        source: null,
        value
      }
    }
  }
}

const getDefaultValueForType = (type) => {
  switch (type) {
    case 'int': return 0
    case 'float': return 0.0
    case 'bool': return false
    case 'str': return ''
    default: return null
  }
}

const getValueTypeOptions = (param) => {
  const hasFixed = !param.allowed_sources || param.allowed_sources.length === 0 || param.allowed_sources.includes('fixed')
  const hasDynamic = !param.allowed_sources || param.allowed_sources.length === 0 || 
    param.allowed_sources.some(s => ['ha', 'myhome', 'virtual'].includes(s))
  
  const options = []
  
  if (hasFixed) {
    options.push({ title: 'Фиксированный', value: 'fixed', icon: 'mdi-numeric' })
  }
  
  if (hasDynamic) {
    options.push({ title: 'Динамический', value: 'dynamic', icon: 'mdi-link-variant' })
  }
  
  return options
}

const getValueTypeIcon = (valueType) => {
  return valueType === 'fixed' ? 'mdi-numeric' : 'mdi-link-variant'
}

const onValueTypeChange = (param) => {
  const paramName = param.name
  const currentData = paramData.value[paramName]
  
  if (currentData.valueType === 'dynamic') {
    // Переключаемся на динамичный - сбрасываем значение
    currentData.value = null
    currentData.source = null
  } else {
    // Переключаемся на фиксированный - устанавливаем дефолтное значение если нужно
    currentData.source = null
    if (currentData.value === null || currentData.value === undefined) {
      currentData.value = param.default !== undefined ? param.default : getDefaultValueForType(param.type)
    }
  }
  
  updateValue()
}

const hasOnlyHAOrMYHOME = (param) => {
  if (!param.allowed_sources || param.allowed_sources.length === 0) {
    return false // По умолчанию доступны все источники, не только HA/MYHOME
  }
  const dynamicSources = param.allowed_sources.filter(s => ['ha', 'myhome'].includes(s))
  const hasVirtual = param.allowed_sources.includes('virtual')
  return dynamicSources.length > 0 && !hasVirtual
}

const hasOnlyVirtualPort = (param) => {
  if (!param.allowed_sources || param.allowed_sources.length === 0) {
    return false // По умолчанию доступны все источники, не только virtual
  }
  const hasVirtual = param.allowed_sources.includes('virtual')
  const hasHAOrMYHOME = param.allowed_sources.some(s => ['ha', 'myhome'].includes(s))
  return hasVirtual && !hasHAOrMYHOME
}

const hasHAOrMYHOME = (param) => {
  if (!param.allowed_sources || param.allowed_sources.length === 0) {
    return true
  }
  return param.allowed_sources.some(s => ['ha', 'myhome'].includes(s))
}

const hasVirtualPort = (param) => {
  if (!param.allowed_sources || param.allowed_sources.length === 0) {
    return true
  }
  return param.allowed_sources.includes('virtual')
}

const getFirstDynamicSource = (param) => {
  if (!param.allowed_sources || param.allowed_sources.length === 0) {
    return 'all'
  }
  // Если есть HA, используем HA
  if (param.allowed_sources.includes('ha')) {
    return 'ha'
  }
  // Если есть MYHOME, используем MYHOME
  if (param.allowed_sources.includes('myhome')) {
    return 'myhome'
  }
  return 'all'
}

const getSourceIcon = (source) => {
  const icons = {
    'fixed': 'mdi-numeric',
    'ha': 'mdi-home-assistant',
    'myhome': 'mdi-home',
    'virtual': 'mdi-link-variant'
  }
  return icons[source] || 'mdi-cog'
}

watch(() => props.modelValue, (newVal) => {
  // Инициализируем параметры из modelValue
  if (newVal) {
    Object.keys(newVal).forEach(key => {
      const existingValue = newVal[key]
      const param = props.parameters.find(p => p.name === key)
      
      if (existingValue !== undefined && existingValue !== null) {
        if (typeof existingValue === 'object' && existingValue.source) {
          // Динамичное значение
          paramData.value[key] = {
            valueType: 'dynamic',
            source: existingValue.source,
            value: existingValue.value
          }
        } else {
          // Фиксированное значение
          paramData.value[key] = {
            valueType: 'fixed',
            source: null,
            value: existingValue
          }
        }
      } else if (param) {
        // Инициализируем параметр если его нет
        initializeParam(param)
      }
    })
  }
}, { immediate: true, deep: true })

watch(() => props.parameters, (newParams) => {
  // Инициализируем все параметры
  if (newParams && newParams.length > 0) {
    newParams.forEach(param => {
      initializeParam(param)
    })
    updateValue()
  }
}, { immediate: true })

// Загружаем виртуальные порты при монтировании
watch(() => props.parameters, () => {
  if (props.parameters.some(p => 
    (!p.allowed_sources || p.allowed_sources.length === 0 || p.allowed_sources.includes('virtual'))
  )) {
    loadVirtualPorts()
  }
}, { immediate: true })

const updateValue = () => {
  // Преобразуем paramData в формат для сохранения
  const result = {}
  Object.keys(paramData.value).forEach(key => {
    const param = paramData.value[key]
    if (param.valueType === 'fixed') {
      // Для фиксированных значений сохраняем только value
      result[key] = param.value
    } else {
      // Для динамичных нужно определить источник из значения
      // Если значение - это entity_id (строка), определяем источник автоматически
      // Или используем сохраненный source если он есть
      const source = param.source || determineSourceFromValue(param.value, key)
      result[key] = {
        source: source || 'ha', // По умолчанию HA
        value: param.value
      }
    }
  })
  emit('update:modelValue', result)
}

const determineSourceFromValue = (value, paramName) => {
  // Пытаемся определить источник из значения
  // Если это entity_id виртуального порта (начинается с virtual.)
  if (typeof value === 'string' && value.startsWith('virtual.')) {
    // Проверяем, есть ли такой порт в списке виртуальных портов
    const port = virtualPorts.value.find(p => p.entity_id === value)
    if (port) {
      return 'virtual'
    }
  }
  
  // Если это entity_id из HA (строка с точкой, но не virtual.)
  if (typeof value === 'string' && value.includes('.') && !value.startsWith('virtual.')) {
    // Можно попробовать определить по формату, но лучше использовать EntitySelect который уже знает источник
    return null // Будет определен позже
  }
  
  return null
}
</script>

<style scoped>
</style>

