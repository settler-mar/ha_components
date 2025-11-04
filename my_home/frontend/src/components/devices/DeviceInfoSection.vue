<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-3">
      <div class="text-subtitle-1 font-weight-medium">Информация об устройстве</div>
      <v-btn
        icon
        size="small"
        variant="text"
        density="compact"
        @click="$emit('load-info')"
        :loading="loading"
      >
        <v-icon size="small">mdi-refresh</v-icon>
      </v-btn>
    </div>

    <v-card v-if="loading" variant="outlined" class="pa-3 text-center">
      <v-progress-circular indeterminate color="primary" size="24" width="2"></v-progress-circular>
      <div class="mt-2 text-caption text-medium-emphasis">Загрузка информации...</div>
    </v-card>

    <v-card v-else-if="!deviceInfo || deviceInfo.error" variant="outlined" class="pa-3">
      <v-alert type="warning" variant="tonal" density="compact" class="mb-0">
        <div v-if="deviceInfo?.error" class="text-caption">
          <strong>Ошибка:</strong> {{ deviceInfo.error }}
        </div>
        <div v-else class="text-caption">
          Информация недоступна. Убедитесь, что устройство подключено к сети.
        </div>
      </v-alert>
    </v-card>

    <div v-else>
      <!-- Основная информация в компактной таблице -->
      <v-card variant="outlined" class="mb-3">
        <v-card-text class="pa-2">
          <v-table density="compact" class="info-table">
            <tbody>
              <tr v-for="(value, key) in filteredInfo" :key="key" class="info-row">
                <td class="info-key">{{ formatKey(key) }}</td>
                <td class="info-value">{{ formatValue(value) }}</td>
              </tr>
            </tbody>
          </v-table>
        </v-card-text>
      </v-card>

      <!-- Полный JSON ответ (сворачиваемый) -->
      <v-card variant="outlined" v-if="hasRawData">
        <v-expansion-panels variant="accordion" density="compact">
          <v-expansion-panel>
            <v-expansion-panel-title class="text-caption">
              <v-icon size="small" class="me-2">mdi-code-tags</v-icon>
              Полный JSON ответ
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <pre class="code-block">{{ JSON.stringify(deviceInfo, null, 2) }}</pre>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  deviceInfo: {
    type: Object,
    default: () => null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['load-info'])

// Приоритетные поля для отображения первыми
const priorityFields = ['name', 'version', 'chip_id', 'mac', 'ssid', 'ip', 'config_name', 'flash_date']

// Фильтруем информацию, исключая технические поля и сортируем по приоритету
const filteredInfo = computed(() => {
  if (!props.deviceInfo || props.deviceInfo.error) return {}
  
  const excludeKeys = ['raw_response', 'error']
  const filtered = {}
  const priority = {}
  const other = {}
  
  for (const [key, value] of Object.entries(props.deviceInfo)) {
    if (!excludeKeys.includes(key) && value !== null && value !== undefined && value !== '') {
      if (priorityFields.includes(key)) {
        priority[key] = value
      } else {
        other[key] = value
      }
    }
  }
  
  // Сортируем приоритетные поля по порядку в массиве priorityFields
  const sortedPriority = {}
  priorityFields.forEach(key => {
    if (priority[key] !== undefined) {
      sortedPriority[key] = priority[key]
    }
  })
  
  return { ...sortedPriority, ...other }
})

// Проверяем, есть ли данные для отображения JSON
const hasRawData = computed(() => {
  return props.deviceInfo && Object.keys(props.deviceInfo).length > 0
})

const formatKey = (key) => {
  // Преобразуем ключи в читаемый формат
  const formatted = key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase())
  
  // Специальные переводы для часто встречающихся полей
  const translations = {
    'Chip Id': 'ID чипа',
    'Mac': 'MAC адрес',
    'Ssid': 'SSID',
    'Config Name': 'Модель',
    'Flash Date': 'Дата прошивки',
    'Flash Chip Revision': 'Ревизия чипа'
  }
  
  return translations[formatted] || formatted
}

const formatValue = (value) => {
  if (typeof value === 'object' && value !== null) {
    // Для объектов показываем краткое представление
    if (Array.isArray(value)) {
      return `[${value.length} элементов]`
    }
    return `{${Object.keys(value).length} полей}`
  }
  if (typeof value === 'boolean') {
    return value ? 'Да' : 'Нет'
  }
  const strValue = String(value)
  // Обрезаем длинные значения
  if (strValue.length > 100) {
    return strValue.substring(0, 100) + '...'
  }
  return strValue
}
</script>

<style scoped>
.info-table {
  font-size: 0.875rem;
}

.info-table :deep(tbody tr) {
  border-bottom: 1px solid rgba(var(--v-border-opacity), var(--v-border-opacity));
}

.info-table :deep(tbody tr:last-child) {
  border-bottom: none;
}

.info-key {
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.7);
  padding: 8px 12px !important;
  width: 40%;
  vertical-align: top;
}

.info-value {
  padding: 8px 12px !important;
  word-break: break-word;
  vertical-align: top;
}

.info-row:hover {
  background-color: rgba(var(--v-theme-primary), 0.04);
}

.code-block {
  background-color: rgba(var(--v-theme-surface), 1);
  padding: 12px;
  border-radius: 4px;
  font-family: 'Courier New', 'Consolas', monospace;
  font-size: 11px;
  line-height: 1.5;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  border: 1px solid rgba(var(--v-border-opacity), var(--v-border-opacity));
}
</style>
