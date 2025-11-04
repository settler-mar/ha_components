<template>
  <div class="device-settings-section">
    <div class="section-header mb-4">
      <h3 class="text-h6 mb-2">
        <v-icon class="me-2">mdi-cog</v-icon>
        Настройки устройства
      </h3>
      <p class="text-body-2 text-grey">
        Изменение параметров устройства и настроек интеграции с Home Assistant
      </p>
    </div>

    <v-progress-linear
      v-if="loading"
      color="primary"
      height="4"
      indeterminate
      rounded
      class="mb-4"
    />

    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      class="mb-4"
    >
      {{ error }}
    </v-alert>

    <v-form ref="form" v-model="valid">
      <v-container>
        <v-row>
          <v-col
            cols="12"
            sm="6"
            v-for="field in mergedFields"
            :key="field.name"
          >
            <MyFormField
              v-model="formData[field.name]"
              :field="field"
              :required="requiredFields.includes(field.name)"
              :readonly="loading || (field.readonly && !['name', 'description', 'location_id'].includes(field.name))"
            />
          </v-col>
        </v-row>
      </v-container>
    </v-form>

    <v-card-actions class="px-0 mt-4">
      <v-spacer></v-spacer>
      <v-btn
        variant="text"
        @click="resetForm"
        :disabled="loading || saving"
      >
        Отмена
      </v-btn>
      <v-btn
        color="primary"
        @click="save"
        :loading="saving"
        :disabled="!valid || loading || saving"
      >
        Сохранить
      </v-btn>
    </v-card-actions>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useTableStore } from '@/store/tables'
import useMessageStore from '@/store/messages'
import MyFormField from '@/components/form_elements/MyFormField.vue'
import { objectToFlat } from '@/utils/array'

const props = defineProps({
  deviceId: {
    type: Number,
    required: true
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

const emit = defineEmits(['saved', 'device-updated'])

const tableStore = useTableStore()
const messageStore = useMessageStore()

const form = ref(null)
const valid = ref(false)
const loading = ref(false)
const saving = ref(false)
const error = ref(null)
const formData = ref({})

const structure = computed(() => tableStore.tables.devices?.structure || [])

const excludeFields = ['id', 'params', 'created_at', 'created_by', 'updated_at', 'updated_by', 'code', 'model', 'vendor', 'type']
const onlyShowFields = ['created_at', 'created_by', 'updated_at', 'updated_by']

const structureToShow = computed(() => {
  return structure.value.filter(field => {
    if (excludeFields.includes(field.name)) return false
    if (field.name === 'connection_id') return false
    return true
  })
})

const mergedFields = computed(() => {
  const tableFields = structureToShow.value
  let customFields = [...tableFields]
  let params = {...props.customParams}

  for (const index in tableFields) {
    const field = tableFields[index]
    if (field.name in params) {
      customFields[index] = {...field, ...params[field.name]}
      delete params[field.name]
    }
  }

  for (const key in params) {
    customFields.push({
      name: key,
      ...params[key]
    })
  }

  return customFields
})

const requiredFields = computed(() => {
  return mergedFields.value.filter(field => 
    !onlyShowFields.includes(field.name) && 
    (field.required || !field.nullable)
  )
})

// Загрузка данных устройства
const loadDevice = async () => {
  loading.value = true
  error.value = null

  try {
    // Получаем устройство из таблицы
    const device = tableStore.tables.devices?.items.find(d => d.id === props.deviceId) || props.device
    
    if (!device) {
      error.value = 'Устройство не найдено'
      return
    }

    // Преобразуем объект в плоскую структуру
    formData.value = {...objectToFlat(device)}
    if (!formData.value.params) formData.value.params = {}

    // Инициализируем custom_params если не установлены
    for (const key in props.customParams) {
      if (!(key in formData.value)) {
        formData.value[key] = props.customParams[key].default ?? null
      }
    }

    // Обрабатываем HA настройки
    const haSettings = device.params?.ha_integration || {}
    formData.value.ha_integration_enabled = haSettings.enabled ?? true
    formData.value.ha_entity_prefix = haSettings.entityPrefix || device.name || 'device'
    formData.value.ha_publish_device_online = haSettings.publishDeviceOnline ?? true
  } catch (err) {
    console.error('Error loading device:', err)
    error.value = 'Ошибка загрузки данных устройства'
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  loadDevice()
}

const save = async () => {
  if (!form.value) return
  if (!form.value.validate()) return

  // Проверка обязательных полей
  let has_no_required = false
  for (const field of requiredFields.value) {
    if (formData.value[field.name]) continue
    if (field.type === 'bool' && formData.value[field.name] === false) continue
    has_no_required = true
    messageStore.showError(`Поле ${field.description || field.name} обязательно для заполнения`)
  }

  if (has_no_required) return

  saving.value = true

  try {
    // Получаем устройство для получения исходных значений
    const device = tableStore.tables.devices?.items.find(d => d.id === props.deviceId) || props.device
    
    // Формируем данные для сохранения
    const dataToSend = {}
    
    // Добавляем ID устройства
    if (props.deviceId) {
      dataToSend.id = props.deviceId
    }
    
    for (let key in formData.value) {
      if (onlyShowFields.includes(key)) continue

      let value = formData.value[key]
      if (excludeFields.includes(key) || key === 'connection_id') {
        // Используем значение из исходного устройства
        if (device && device[key] !== undefined) {
          value = device[key]
        }
      }

      key = key.split('.')
      if (!structure.value.map(f => f.name).includes(key[0])) continue
      
      if (key.length > 1) {
        dataToSend[key[0]] = dataToSend[key[0]] || {}
        dataToSend[key[0]][key[1]] = value
      } else {
        if (dataToSend[key[0]]) continue
        dataToSend[key[0]] = value
      }
    }

    // Обрабатываем HA настройки
    if (formData.value.ha_integration_enabled !== undefined ||
        formData.value.ha_entity_prefix !== undefined ||
        formData.value.ha_publish_device_online !== undefined) {
      
      dataToSend.params = dataToSend.params || {}
      dataToSend.params.ha_integration = {
        enabled: formData.value.ha_integration_enabled ?? true,
        entityPrefix: formData.value.ha_entity_prefix || formData.value.name || 'device',
        publishDeviceOnline: formData.value.ha_publish_device_online ?? true
      }
    }

    const success = await tableStore.saveItem('devices', dataToSend)
    
    if (success) {
      messageStore.showSuccess('Устройство успешно обновлено')
      await tableStore.reloadTableData('devices')
      emit('saved')
      emit('device-updated', dataToSend)
    }
  } catch (err) {
    console.error('Error saving device:', err)
    messageStore.showError('Ошибка сохранения устройства')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadDevice()
})

watch(() => props.deviceId, () => {
  loadDevice()
})
</script>

<style scoped>
.device-settings-section {
  padding: 16px 0;
}

.section-header {
  border-bottom: 1px solid #e0e0e0;
  padding-bottom: 16px;
}

.section-header h3 {
  color: #1976d2;
  font-weight: 500;
}

.section-header p {
  margin: 0;
}
</style>

