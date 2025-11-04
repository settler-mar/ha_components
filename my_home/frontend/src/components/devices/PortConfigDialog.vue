<template>
  <v-dialog v-model="show" max-width="600" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="me-2">mdi-cog</v-icon>
        Настройка порта
        <v-spacer></v-spacer>
        <v-btn
          icon
          variant="text"
          @click="close"
        >
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text v-if="port">
        <v-form>
          <!-- Основная информация -->
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="py-2">
              <v-icon class="me-2">mdi-information</v-icon>
              Основная информация
            </v-card-title>
            <v-card-text class="pt-0">
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="config.name"
                    label="Название в Home Assistant"
                    variant="outlined"
                    density="compact"
                    hint="Отображаемое название сущности"
                  ></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="config.entity_id"
                    label="Entity ID"
                    variant="outlined"
                    density="compact"
                    hint="Уникальный идентификатор сущности"
                    readonly
                  ></v-text-field>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Настройки типа -->
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="py-2">
              <v-icon class="me-2">mdi-cog-outline</v-icon>
              Настройки типа
            </v-card-title>
            <v-card-text class="pt-0">
              <v-row>
                <v-col cols="12" md="6">
                  <v-select
                    v-model="config.device_class"
                    :items="deviceClassOptions"
                    label="Device Class"
                    variant="outlined"
                    density="compact"
                    clearable
                    hint="Класс устройства для группировки"
                  ></v-select>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="config.unit_of_measurement"
                    label="Единица измерения"
                    variant="outlined"
                    density="compact"
                    hint="Единица измерения значения"
                  ></v-text-field>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" md="6">
                  <v-select
                    v-model="config.state_class"
                    :items="stateClassOptions"
                    label="State Class"
                    variant="outlined"
                    density="compact"
                    clearable
                    hint="Класс состояния для статистики"
                  ></v-select>
                </v-col>
                <v-col cols="12" md="6">
                  <v-select
                    v-model="config.entity_category"
                    :items="entityCategoryOptions"
                    label="Entity Category"
                    variant="outlined"
                    density="compact"
                    clearable
                    hint="Категория сущности"
                  ></v-select>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Дополнительные настройки -->
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="py-2">
              <v-icon class="me-2">mdi-tune</v-icon>
              Дополнительные настройки
            </v-card-title>
            <v-card-text class="pt-0">
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="config.icon"
                    label="Иконка"
                    variant="outlined"
                    density="compact"
                    hint="MDI иконка (например: mdi-lightbulb)"
                    prepend-inner-icon="mdi-palette"
                  ></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="config.suggested_display_precision"
                    label="Точность отображения"
                    variant="outlined"
                    density="compact"
                    type="number"
                    hint="Количество знаков после запятой"
                  ></v-text-field>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12">
                  <v-switch
                    v-model="config.enabled_by_default"
                    label="Включено по умолчанию"
                    color="primary"
                    density="compact"
                    hint="Показывать сущность в Home Assistant по умолчанию"
                  ></v-switch>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12">
                  <v-switch
                    v-model="config.force_update"
                    label="Принудительное обновление"
                    color="primary"
                    density="compact"
                    hint="Обновлять сущность даже если значение не изменилось"
                  ></v-switch>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Атрибуты -->
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="py-2">
              <v-icon class="me-2">mdi-code-json</v-icon>
              Дополнительные атрибуты
            </v-card-title>
            <v-card-text class="pt-0">
              <v-textarea
                v-model="attributesJson"
                label="JSON атрибуты"
                variant="outlined"
                density="compact"
                rows="4"
                hint="Дополнительные атрибуты в формате JSON"
                :error="attributesError"
                :error-messages="attributesError ? 'Неверный формат JSON' : ''"
              ></v-textarea>
            </v-card-text>
          </v-card>
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn
          variant="text"
          @click="close"
        >
          Отмена
        </v-btn>
        <v-btn
          color="primary"
          @click="save"
          :disabled="attributesError"
        >
          Сохранить
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, defineProps, defineEmits } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  port: {
    type: Object,
    default: null
  },
  device: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:show', 'save'])

// Конфигурация порта
const config = ref({
  name: '',
  entity_id: '',
  device_class: '',
  unit_of_measurement: '',
  state_class: '',
  entity_category: '',
  icon: '',
  suggested_display_precision: '',
  enabled_by_default: true,
  force_update: false,
  attributes: {}
})

// JSON атрибуты
const attributesJson = ref('')
const attributesError = ref(false)

// Опции для селектов
const deviceClassOptions = [
  { title: 'Температура', value: 'temperature' },
  { title: 'Влажность', value: 'humidity' },
  { title: 'Давление', value: 'pressure' },
  { title: 'Освещенность', value: 'illuminance' },
  { title: 'Мощность', value: 'power' },
  { title: 'Энергия', value: 'energy' },
  { title: 'Напряжение', value: 'voltage' },
  { title: 'Ток', value: 'current' },
  { title: 'Частота', value: 'frequency' },
  { title: 'Время', value: 'timestamp' },
  { title: 'Переключатель', value: 'switch' },
  { title: 'Кнопка', value: 'button' },
  { title: 'Датчик движения', value: 'motion' },
  { title: 'Датчик открытия', value: 'opening' },
  { title: 'Датчик дыма', value: 'smoke' },
  { title: 'Датчик газа', value: 'gas' },
  { title: 'Датчик безопасности', value: 'safety' },
  { title: 'Датчик вибрации', value: 'vibration' },
  { title: 'Датчик влажности', value: 'moisture' },
  { title: 'Датчик освещенности', value: 'light' },
  { title: 'Датчик звука', value: 'sound' },
  { title: 'Датчик обновления', value: 'update' },
  { title: 'Датчик подключения', value: 'connectivity' },
  { title: 'Датчик батареи', value: 'battery' },
  { title: 'Датчик заряда', value: 'battery_charging' },
  { title: 'Датчик CO', value: 'carbon_monoxide' },
  { title: 'Датчик CO2', value: 'carbon_dioxide' },
  { title: 'Датчик PM2.5', value: 'pm25' },
  { title: 'Датчик PM10', value: 'pm10' },
  { title: 'Датчик озона', value: 'ozone' },
  { title: 'Датчик азота', value: 'nitrogen_dioxide' },
  { title: 'Датчик серы', value: 'sulphur_dioxide' },
  { title: 'Датчик сероводорода', value: 'sulphide' },
  { title: 'Датчик азота', value: 'nitric_oxide' },
  { title: 'Датчик летучих органических соединений', value: 'volatile_organic_compounds' },
  { title: 'Датчик формальдегида', value: 'formaldehyde' },
  { title: 'Датчик аэрозолей', value: 'aerosol' },
  { title: 'Датчик кислотности', value: 'acidity' },
  { title: 'Датчик щелочности', value: 'alkalinity' },
  { title: 'Датчик жесткости воды', value: 'water_hardness' },
  { title: 'Датчик окислительно-восстановительного потенциала', value: 'redox' },
  { title: 'Датчик проводимости', value: 'conductivity' },
  { title: 'Датчик сопротивления', value: 'resistance' },
  { title: 'Датчик индуктивности', value: 'inductance' },
  { title: 'Датчик емкости', value: 'capacitance' },
  { title: 'Датчик реактивной мощности', value: 'reactive_power' },
  { title: 'Датчик коэффициента мощности', value: 'power_factor' },
  { title: 'Датчик тока утечки', value: 'current' },
  { title: 'Датчик напряжения утечки', value: 'voltage' },
  { title: 'Датчик частоты сети', value: 'frequency' },
  { title: 'Датчик фазы', value: 'phase' },
  { title: 'Датчик коэффициента гармоник', value: 'thd' },
  { title: 'Датчик коэффициента нелинейных искажений', value: 'thd_voltage' },
  { title: 'Датчик коэффициента нелинейных искажений тока', value: 'thd_current' },
  { title: 'Датчик коэффициента нелинейных искажений мощности', value: 'thd_power' },
  { title: 'Датчик коэффициента нелинейных искажений энергии', value: 'thd_energy' },
  { title: 'Датчик коэффициента нелинейных искажений напряжения', value: 'thd_voltage' },
  { title: 'Датчик коэффициента нелинейных искажений тока', value: 'thd_current' },
  { title: 'Датчик коэффициента нелинейных искажений мощности', value: 'thd_power' },
  { title: 'Датчик коэффициента нелинейных искажений энергии', value: 'thd_energy' }
]

const stateClassOptions = [
  { title: 'Измерение', value: 'measurement' },
  { title: 'Общее', value: 'total' },
  { title: 'Общее увеличивающееся', value: 'total_increasing' },
  { title: 'Общее уменьшающееся', value: 'total_decreasing' }
]

const entityCategoryOptions = [
  { title: 'Конфигурация', value: 'config' },
  { title: 'Диагностика', value: 'diagnostic' },
  { title: 'Система', value: 'system' }
]

// Методы
const close = () => {
  emit('update:show', false)
}

const save = () => {
  if (attributesError.value) return

  const configData = {
    ...config.value,
    attributes: config.value.attributes
  }

  emit('save', {
    port: props.port,
    config: configData
  })

  close()
}

// Валидация JSON
const validateJson = (jsonString) => {
  if (!jsonString.trim()) {
    attributesError.value = false
    return {}
  }

  try {
    const parsed = JSON.parse(jsonString)
    attributesError.value = false
    return parsed
  } catch (e) {
    attributesError.value = true
    return {}
  }
}

// Инициализация конфигурации при изменении порта
watch(() => props.port, (newPort) => {
  if (newPort) {
    const haData = newPort.ha || {}
    
    config.value = {
      name: haData.name || newPort.title || newPort.name || newPort.code || '',
      entity_id: haData.entity_id || '',
      device_class: haData.device_class || '',
      unit_of_measurement: haData.unit_of_measurement || '',
      state_class: haData.state_class || '',
      entity_category: haData.entity_category || '',
      icon: haData.icon || '',
      suggested_display_precision: haData.suggested_display_precision || '',
      enabled_by_default: haData.enabled_by_default !== false,
      force_update: haData.force_update || false,
      attributes: haData.attributes || {}
    }

    attributesJson.value = JSON.stringify(config.value.attributes, null, 2)
  }
}, { immediate: true })

// Обновление атрибутов при изменении JSON
watch(attributesJson, (newValue) => {
  const parsed = validateJson(newValue)
  if (!attributesError.value) {
    config.value.attributes = parsed
  }
})
</script>

<style scoped>
.v-card-title {
  font-size: 1rem;
  font-weight: 600;
}

.v-card-text {
  padding-top: 16px;
}
</style>