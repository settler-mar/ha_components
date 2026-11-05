<template>
  <v-dialog v-model="dialog" max-width="800" persistent>
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <span>{{ port ? 'Редактировать виртуальный порт' : 'Создать виртуальный порт' }}</span>
        <v-btn icon variant="text" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text>
        <v-form ref="form">
          <!-- Основные параметры -->
          <v-row>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="formData.name"
                label="Название порта"
                :rules="[v => !!v || 'Название обязательно']"
                required
                variant="outlined"
                density="compact"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                v-model="formData.icon"
                :items="icons"
                label="Иконка"
                variant="outlined"
                density="compact"
                item-title="title"
                item-value="value"
                clearable
              />
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12">
              <v-textarea
                v-model="formData.description"
                label="Описание"
                rows="2"
                variant="outlined"
                density="compact"
              />
            </v-col>
          </v-row>

          <v-divider class="my-4" />
          <div class="text-subtitle-2 mb-2">Физический источник (необязательно)</div>
          <v-select
            v-model="bindingValue"
            :items="physicalParameters"
            item-title="label"
            item-value="value"
            label="Связать с параметром платы"
            clearable
            variant="outlined"
            density="compact"
            hint="Без привязки порт остаётся полностью виртуальным"
            persistent-hint
          />

          <!-- Тип порта и параметры для HA -->
          <v-row>
            <v-col cols="12" md="6">
              <v-select
                v-model="formData.type"
                label="Тип entity"
                :items="entityTypes"
                item-title="label"
                item-value="value"
                variant="outlined"
                density="compact"
                required
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                v-model="formData.device_class"
                :items="deviceClasses"
                label="Класс устройства"
                variant="outlined"
                density="compact"
                item-title="title"
                item-value="value"
                clearable
              />
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12" md="6">
              <v-select
                v-model="formData.unit_of_measurement"
                :items="unitsOfMeasurement"
                label="Единица измерения"
                variant="outlined"
                density="compact"
                item-title="title"
                item-value="value"
                clearable
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                v-model="formData.state_class"
                :items="stateClasses"
                label="Класс состояния"
                variant="outlined"
                density="compact"
                item-title="title"
                item-value="value"
                clearable
              />
            </v-col>
          </v-row>

          <!-- Параметры для number/input_number -->
          <v-row v-if="formData.type === 'number' || formData.type === 'input_number'">
            <v-col cols="12" md="4">
              <v-text-field
                v-model.number="formData.min_value"
                label="Минимальное значение"
                type="number"
                variant="outlined"
                density="compact"
              />
            </v-col>
            <v-col cols="12" md="4">
              <v-text-field
                v-model.number="formData.max_value"
                label="Максимальное значение"
                type="number"
                variant="outlined"
                density="compact"
              />
            </v-col>
            <v-col cols="12" md="4">
              <v-text-field
                v-model.number="formData.step"
                label="Шаг изменения"
                type="number"
                variant="outlined"
                density="compact"
              />
            </v-col>
          </v-row>

          <!-- Режим для input_number -->
          <v-row v-if="formData.type === 'input_number'">
            <v-col cols="12" md="6">
              <v-select
                v-model="formData.mode"
                label="Режим отображения"
                :items="modes"
                item-title="label"
                item-value="value"
                variant="outlined"
                density="compact"
              />
            </v-col>
          </v-row>

          <!-- Опции для input_select -->
          <v-row v-if="formData.type === 'input_select'">
            <v-col cols="12">
              <v-textarea
                v-model="optionsText"
                label="Опции (по одной на строку)"
                hint="Каждая строка - отдельная опция"
                persistent-hint
                rows="4"
                variant="outlined"
                density="compact"
                @update:model-value="updateOptions"
              />
            </v-col>
          </v-row>

          <!-- Начальное значение -->
          <v-row>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="formData.initial_value"
                label="Начальное значение"
                variant="outlined"
                density="compact"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                v-model="formData.entity_category"
                :items="entityCategories"
                label="Категория сущности"
                variant="outlined"
                density="compact"
                item-title="title"
                item-value="value"
                clearable
              />
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12">
              <v-switch
                v-model="formData.enabled_by_default"
                label="Включен по умолчанию"
                color="primary"
              />
            </v-col>
          </v-row>
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn variant="text" @click="close" :disabled="saving">
          Отмена
        </v-btn>
        <v-btn
          color="primary"
          @click="save"
          :loading="saving"
          :disabled="!formData.name"
        >
          Сохранить
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { secureFetch } from '@/services/fetch'
import useMessageStore from '@/store/messages'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  port: {
    type: Object,
    default: null
  },
  virtualDeviceId: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const messageStore = useMessageStore()
const form = ref(null)
const saving = ref(false)
const physicalParameters = ref([])
const bindingValue = ref(null)

const dialog = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const entityTypes = [
  { label: 'Sensor', value: 'sensor' },
  { label: 'Switch', value: 'switch' },
  { label: 'Number', value: 'number' },
  { label: 'Input Number', value: 'input_number' },
  { label: 'Input Boolean', value: 'input_boolean' },
  { label: 'Input Text', value: 'input_text' },
  { label: 'Input Select', value: 'input_select' }
]

const stateClasses = [
  { title: 'Измерение', value: 'measurement' },
  { title: 'Общее', value: 'total' },
  { title: 'Общее нарастающее', value: 'total_increasing' }
]

const modes = [
  { label: 'Box', value: 'box' },
  { label: 'Slider', value: 'slider' }
]

const entityCategories = [
  { title: 'Конфигурация', value: 'config' },
  { title: 'Диагностика', value: 'diagnostic' }
]

const optionsText = ref('')

const loadPhysicalParameters = async () => {
  try {
    const response = await secureFetch('/api/virtual-devices/physical-parameters')
    const data = await response.json()
    physicalParameters.value = (data.parameters || []).map(item => ({
      value: `${item.device_id}|${item.code}`,
      label: `${item.device_name} · ${item.title || item.name || item.code} · ${item.code}`,
      item
    }))
  } catch (error) {
    physicalParameters.value = []
  }
}

const formData = ref({
  name: '',
  description: '',
  icon: 'mdi-network',
  type: 'sensor',
  device_class: '',
  unit_of_measurement: '',
  state_class: '',
  min_value: null,
  max_value: null,
  step: null,
  mode: 'box',
  initial_value: '',
  options: [],
  entity_category: '',
  enabled_by_default: true
})

const portNames = [
  { title: 'Температура', value: 'temperature' },
  { title: 'Влажность', value: 'humidity' },
  { title: 'Давление', value: 'pressure' },
  { title: 'Освещенность', value: 'light' },
  { title: 'Движение', value: 'motion' },
  { title: 'Дверь', value: 'door' },
  { title: 'Окно', value: 'window' },
  { title: 'Дым', value: 'smoke' },
  { title: 'Газ', value: 'gas' },
  { title: 'Вода', value: 'water' },
  { title: 'Электроэнергия', value: 'power' },
  { title: 'Энергия', value: 'energy' },
  { title: 'Напряжение', value: 'voltage' },
  { title: 'Ток', value: 'current' },
  { title: 'Частота', value: 'frequency' },
  { title: 'Сигнал', value: 'signal_strength' },
  { title: 'Батарея', value: 'battery' },
  { title: 'Временная метка', value: 'timestamp' },
  { title: 'Дата', value: 'date' },
  { title: 'Длительность', value: 'duration' },
  { title: 'Расстояние', value: 'distance' },
  { title: 'Скорость', value: 'speed' },
  { title: 'Вес', value: 'weight' },
  { title: 'Объем', value: 'volume' },
  { title: 'Площадь', value: 'area' },
  { title: 'Длина', value: 'length' },
  { title: 'Масса', value: 'mass' },
  { title: 'Счетчик', value: 'counter' },
  { title: 'Деньги', value: 'money' },
  { title: 'Размер данных', value: 'data_size' },
  { title: 'Скорость данных', value: 'data_rate' },
  { title: 'УФ-индекс', value: 'irradiance' },
  { title: 'Осадки', value: 'precipitation' },
  { title: 'Интенсивность осадков', value: 'precipitation_intensity' },
  { title: 'Концентрация', value: 'concentration' },
  { title: 'Проводимость', value: 'conductivity' },
  { title: 'pH', value: 'ph' },
  { title: 'Кислород', value: 'oxygen' },
  { title: 'Реактивная мощность', value: 'reactive_power' },
  { title: 'Полная мощность', value: 'apparent_power' },
  { title: 'Стоимость', value: 'cost' },
  { title: 'Потребление газа', value: 'gas_consumption' },
  { title: 'Потребление воды', value: 'water_consumption' }
]

const deviceClasses = [
  // Температура и влажность
  { title: 'Температура', value: 'temperature' },
  { title: 'Влажность', value: 'humidity' },
  { title: 'Давление', value: 'pressure' },
  { title: 'Дифференциал температуры', value: 'temperature_differential' },

  // Освещение и свет
  { title: 'Освещенность', value: 'light' },
  { title: 'Иллюминация', value: 'irradiance' },

  // Движение и присутствие
  { title: 'Движение', value: 'motion' },
  { title: 'Занятость', value: 'occupancy' },
  { title: 'Присутствие', value: 'presence' },

  // Двери и окна
  { title: 'Дверь', value: 'door' },
  { title: 'Окно', value: 'window' },
  { title: 'Гаражная дверь', value: 'garage_door' },
  { title: 'Открытие', value: 'opening' },

  // Газ и дым
  { title: 'Дым', value: 'smoke' },
  { title: 'Газ', value: 'gas' },
  { title: 'Угарный газ', value: 'carbon_monoxide' },
  { title: 'Углекислый газ', value: 'carbon_dioxide' },

  // Электричество и энергия
  { title: 'Мощность', value: 'power' },
  { title: 'Энергия', value: 'energy' },
  { title: 'Напряжение', value: 'voltage' },
  { title: 'Ток', value: 'current' },
  { title: 'Частота', value: 'frequency' },
  { title: 'Реактивная мощность', value: 'reactive_power' },
  { title: 'Полная мощность', value: 'apparent_power' },

  // Вода и жидкости
  { title: 'Вода', value: 'water' },
  { title: 'Водопотребление', value: 'water_consumption' },

  // Газ
  { title: 'Газопотребление', value: 'gas_consumption' },

  // Батарея и заряд
  { title: 'Батарея', value: 'battery' },

  // Сигнал и связь
  { title: 'Сила сигнала', value: 'signal_strength' },
  { title: 'Подключение', value: 'connectivity' },

  // Безопасность
  { title: 'Проблема', value: 'problem' },
  { title: 'Безопасность', value: 'safety' },
  { title: 'Тампер', value: 'tamper' },
  { title: 'Обновление', value: 'update' },

  // Время и дата
  { title: 'Время', value: 'timestamp' },
  { title: 'Дата', value: 'date' },
  { title: 'Длительность', value: 'duration' },

  // Измерения
  { title: 'Расстояние', value: 'distance' },
  { title: 'Скорость', value: 'speed' },
  { title: 'Вес', value: 'weight' },
  { title: 'Объем', value: 'volume' },
  { title: 'Площадь', value: 'area' },
  { title: 'Длина', value: 'length' },
  { title: 'Масса', value: 'mass' },

  // Качество воздуха
  { title: 'PM1', value: 'pm1' },
  { title: 'PM2.5', value: 'pm25' },
  { title: 'PM10', value: 'pm10' },
  { title: 'Летучие органические соединения', value: 'volatile_organic_compounds' },
  { title: 'Кислород', value: 'oxygen' },
  { title: 'Азот', value: 'nitrogen' },
  { title: 'Озон', value: 'ozone' },
  { title: 'Аммиак', value: 'ammonia' },
  { title: 'Сероводород', value: 'hydrogen_sulfide' },
  { title: 'Сульфид', value: 'sulphide' },
  { title: 'Оксид азота', value: 'nitrogen_oxide' },
  { title: 'Диоксид серы', value: 'sulphur_dioxide' },

  // Разное
  { title: 'Счетчик', value: 'count' },
  { title: 'Деньги', value: 'money' },
  { title: 'Стоимость', value: 'cost' },
  { title: 'Размер данных', value: 'data_size' },
  { title: 'Скорость данных', value: 'data_rate' },
  { title: 'Концентрация', value: 'concentration' },
  { title: 'Проводимость', value: 'conductivity' },
  { title: 'pH', value: 'ph' },
  { title: 'Влажность почвы', value: 'moisture' },
  { title: 'Вибрация', value: 'vibration' },
  { title: 'Звук', value: 'sound' }
]

const unitsOfMeasurement = [
  // Температура
  { title: 'Градусы Цельсия (°C)', value: '°C' },
  { title: 'Градусы Фаренгейта (°F)', value: '°F' },
  { title: 'Кельвины (K)', value: 'K' },

  // Давление
  { title: 'Паскали (Pa)', value: 'Pa' },
  { title: 'Килопаскали (kPa)', value: 'kPa' },
  { title: 'Бары (bar)', value: 'bar' },
  { title: 'Миллиметры ртутного столба (mmHg)', value: 'mmHg' },

  // Влажность
  { title: 'Процент (%)', value: '%' },

  // Освещенность
  { title: 'Люксы (lx)', value: 'lx' },

  // Электричество
  { title: 'Ватты (W)', value: 'W' },
  { title: 'Киловатты (kW)', value: 'kW' },
  { title: 'Ватт-часы (Wh)', value: 'Wh' },
  { title: 'Киловатт-часы (kWh)', value: 'kWh' },
  { title: 'Вольты (V)', value: 'V' },
  { title: 'Амперы (A)', value: 'A' },
  { title: 'Герцы (Hz)', value: 'Hz' },
  { title: 'Вольт-амперы (VA)', value: 'VA' },
  { title: 'Вар (VAR)', value: 'VAR' },

  // Газ и вода
  { title: 'Кубические метры (m³)', value: 'm³' },
  { title: 'Литры (L)', value: 'L' },
  { title: 'Кубические футы (ft³)', value: 'ft³' },

  // Вес и масса
  { title: 'Граммы (g)', value: 'g' },
  { title: 'Килограммы (kg)', value: 'kg' },
  { title: 'Фунты (lb)', value: 'lb' },
  { title: 'Тонны (t)', value: 't' },

  // Расстояние
  { title: 'Метры (m)', value: 'm' },
  { title: 'Километры (km)', value: 'km' },
  { title: 'Мили (mi)', value: 'mi' },
  { title: 'Футы (ft)', value: 'ft' },

  // Скорость
  { title: 'Метры в секунду (m/s)', value: 'm/s' },
  { title: 'Километры в час (km/h)', value: 'km/h' },
  { title: 'Мили в час (mph)', value: 'mph' },

  // Площадь
  { title: 'Квадратные метры (m²)', value: 'm²' },

  // Время
  { title: 'Секунды (s)', value: 's' },
  { title: 'Минуты (min)', value: 'min' },
  { title: 'Часы (h)', value: 'h' },
  { title: 'Дни (d)', value: 'd' },

  // Качество воздуха
  { title: 'Микрограммы на кубический метр (μg/m³)', value: 'μg/m³' },
  { title: 'Частицы на миллион (ppm)', value: 'ppm' },

  // Размер данных
  { title: 'Байты (B)', value: 'B' },
  { title: 'Килобайты (KB)', value: 'KB' },
  { title: 'Мегабайты (MB)', value: 'MB' },
  { title: 'Гигабайты (GB)', value: 'GB' },

  // Скорость данных
  { title: 'Бит в секунду (bit/s)', value: 'bit/s' },
  { title: 'Килобит в секунду (Kbit/s)', value: 'Kbit/s' },
  { title: 'Мегабит в секунду (Mbit/s)', value: 'Mbit/s' },
  { title: 'Гигабит в секунду (Gbit/s)', value: 'Gbit/s' },

  // Другие
  { title: 'Количество (шт)', value: 'шт' },
  { title: 'Денежная единица', value: 'руб' }
]

const icons = [
  // Температура
  { title: '🌡️ Термометр', value: 'mdi:thermometer' },
  { title: '🌡️ Термометр (линии)', value: 'mdi:thermometer-lines' },

  // Влажность
  { title: '💧 Влажность', value: 'mdi:water-percent' },

  // Давление
  { title: '📊 Давление', value: 'mdi:gauge' },

  // Освещение
  { title: '💡 Свет', value: 'mdi:lightbulb' },
  { title: '🌞 Солнце', value: 'mdi:white-balance-sunny' },

  // Движение
  { title: '🏃 Движение', value: 'mdi:run' },
  { title: '👁️ Вид', value: 'mdi:eye' },

  // Двери и окна
  { title: '🚪 Дверь', value: 'mdi:door' },
  { title: '🪟 Окно', value: 'mdi:window-open' },

  // Газ и дым
  { title: '💨 Газ', value: 'mdi:gas-cylinder' },
  { title: '🔥 Огонь', value: 'mdi:fire' },
  { title: '💨 Дым', value: 'mdi:smoke-detector' },

  // Электричество
  { title: '⚡ Молния', value: 'mdi:flash' },
  { title: '🔌 Розетка', value: 'mdi:power-plug' },
  { title: '🔋 Батарея', value: 'mdi:battery' },

  // Вода
  { title: '🚿 Душ', value: 'mdi:shower' },
  { title: '💧 Капля', value: 'mdi:water' },

  // Погода
  { title: '🌧️ Дождь', value: 'mdi:weather-rainy' },
  { title: '🌤️ Облачно', value: 'mdi:weather-cloudy' },

  // Безопасность
  { title: '🛡️ Щит', value: 'mdi:shield' },
  { title: '🚨 Сигнал тревоги', value: 'mdi:alarm-light' },

  // Датчики
  { title: '📡 Антенна', value: 'mdi:antenna' },
  { title: '📶 Сигнал', value: 'mdi:signal' },

  // Время
  { title: '🕐 Часы', value: 'mdi:clock' },
  { title: '📅 Календарь', value: 'mdi:calendar' },

  // Вес и масса
  { title: '⚖️ Весы', value: 'mdi:scale' },

  // Расстояние
  { title: '📏 Линейка', value: 'mdi:ruler' },

  // Скорость
  { title: '🚗 Машина', value: 'mdi:car' },
  { title: '🚀 Ракета', value: 'mdi:rocket' },

  // Деньги
  { title: '💰 Деньги', value: 'mdi:cash' },
  { title: '💳 Карта', value: 'mdi:credit-card' },

  // Данные
  { title: '💾 Диск', value: 'mdi:harddisk' },
  { title: '🌐 Интернет', value: 'mdi:web' },

  // Разное
  { title: '📊 График', value: 'mdi:chart-line' },
  { title: '🔢 Счетчик', value: 'mdi:counter' },
  { title: '📦 Коробка', value: 'mdi:package' }
]

const updateOptions = () => {
  if (optionsText.value) {
    formData.value.options = optionsText.value.split('\n').filter(line => line.trim()).map(line => line.trim())
  } else {
    formData.value.options = []
  }
}

watch(() => props.port, (newPort) => {
  if (newPort) {
    formData.value = {
      name: newPort.name || '',
      description: newPort.description || '',
      icon: newPort.icon || 'mdi-network',
      type: newPort.type || 'sensor',
      device_class: newPort.device_class || '',
      unit_of_measurement: newPort.unit_of_measurement || newPort.unit || '',
      state_class: newPort.state_class || '',
      min_value: newPort.min_value || null,
      max_value: newPort.max_value || null,
      step: newPort.step || null,
      mode: newPort.mode || 'box',
      initial_value: newPort.initial_value || newPort.value || '',
      options: newPort.options || [],
      entity_category: newPort.entity_category || '',
      enabled_by_default: newPort.enabled_by_default !== undefined ? newPort.enabled_by_default : true
    }
    optionsText.value = newPort.options ? newPort.options.join('\n') : ''
    bindingValue.value = newPort.binding?.device_id != null && newPort.binding?.physical_code
      ? `${newPort.binding.device_id}|${newPort.binding.physical_code}` : null
  } else {
    formData.value = {
      name: '',
      description: '',
      icon: 'mdi-network',
      type: 'sensor',
      device_class: '',
      unit_of_measurement: '',
      state_class: '',
      min_value: null,
      max_value: null,
      step: null,
      mode: 'box',
      initial_value: '',
      options: [],
      entity_category: '',
      enabled_by_default: true
    }
    optionsText.value = ''
    bindingValue.value = null
  }
}, { immediate: true })

const close = () => {
  dialog.value = false
}

const save = async () => {
  if (!form.value) return
  
  const { valid } = await form.value.validate()
  if (!valid) return

  saving.value = true

  try {
    const url = props.port
      ? `/api/virtual-ports/${props.port.id}`
      : (props.virtualDeviceId ? `/api/virtual-devices/${props.virtualDeviceId}/ports` : '/api/virtual-ports')
    
    const method = props.port ? 'PUT' : 'POST'

    const payload = { ...formData.value }
    if (bindingValue.value) {
      const [deviceId, ...codeParts] = bindingValue.value.split('|')
      const selected = physicalParameters.value.find(item => item.value === bindingValue.value)?.item || {}
      payload.binding = { device_id: Number(deviceId), physical_code: codeParts.join('|'),
        signature: { direction: selected.direction, kind: selected.kind, value_type: selected.value_type } }
      payload.source = 'physical'
    } else {
      payload.binding = null
      payload.source = 'manual'
    }
    const response = await secureFetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })

    if (response.ok) {
      messageStore.showSuccess(props.port ? 'Порт обновлен' : 'Порт создан')
      emit('saved')
      close()
    } else {
      const errorData = await response.json()
      messageStore.showError(errorData.detail || 'Ошибка сохранения порта')
    }
  } catch (err) {
    console.error('Error saving virtual port:', err)
    messageStore.showError('Ошибка сохранения порта')
  } finally {
    saving.value = false
  }
}

loadPhysicalParameters()
</script>

<style scoped>
</style>
