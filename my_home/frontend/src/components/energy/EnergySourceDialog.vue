<template>
  <v-dialog v-model="dialog" max-width="1000px" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <span>{{ source ? 'Редактировать источник' : 'Добавить источник' }}</span>
        <v-btn icon @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text>
        <v-progress-linear
          v-if="saving || loadingGroups"
          color="primary"
          height="4"
          indeterminate
          rounded
          class="mb-4"
        />

        <v-form ref="form" v-model="valid">
          <!-- Основные параметры -->
          <v-row>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="formData.name"
                label="Название источника"
                required
                :rules="[v => !!v || 'Название обязательно']"
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                v-model="formData.group"
                :items="energyGroups"
                item-title="name"
                item-value="id"
                label="Группа"
                required
                :rules="[v => !!v || 'Группа обязательна']"
                :loading="loadingGroups"
              >
                <template v-slot:item="{ props, item }">
                  <v-list-item v-bind="props">
                    <template v-slot:prepend>
                      <v-icon>{{ item.raw.icon }}</v-icon>
                    </template>
                  </v-list-item>
                </template>
              </v-select>
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12" md="4">
              <v-switch
                v-model="formData.active"
                label="Активен"
                color="success"
                hint="Можно временно отключать из обработки"
                persistent-hint
              />
            </v-col>
            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.priority"
                label="Приоритет"
                type="number"
                hint="Чем выше число, тем выше приоритет"
                persistent-hint
              />
            </v-col>
            <v-col v-if="formData.group === 'electric'" cols="12" md="4">
              <v-text-field
                v-model="formData.output_power"
                label="Выдаваемая мощность (W)"
                type="number"
                step="0.1"
              />
            </v-col>
          </v-row>

          <!-- Параметры для электричества -->
          <template v-if="formData.group === 'electric'">
            <v-row>
              <v-col cols="12" md="4">
              <EntitySelect
                v-model="formData.voltage_entity_id"
                label="Entity для напряжения"
                hint="Entity ID для отображения напряжения"
              />
              </v-col>
              <v-col cols="12" md="4">
              <EntitySelect
                v-model="formData.frequency_entity_id"
                label="Entity для частоты"
                hint="Entity ID для отображения частоты"
              />
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field
                  v-model="formData.color"
                  label="Цвет"
                  type="color"
                  hint="Выберите цвет для отображения источника"
                  persistent-hint
                />
              </v-col>
            </v-row>
          </template>

          <!-- Параметры для других групп -->
          <template v-else>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.other_color"
                  label="Цвет"
                  type="color"
                  hint="Выберите цвет для отображения источника"
                  persistent-hint
                />
              </v-col>
            </v-row>
          </template>

          <!-- Таблицы для электричества (мощность, онлайн, счетчик) -->
          <template v-if="formData.group === 'electric'">
            <!-- Таблица портов мощности -->
            <v-card class="mb-4" variant="outlined">
              <v-card-title class="text-subtitle-1">
                <v-icon class="me-2">mdi-lightning-bolt</v-icon>
                Порты мощности
              </v-card-title>
              <v-card-text>
                <v-table>
                  <thead>
                    <tr>
                      <th>Entity ID</th>
                      <th>Знак</th>
                      <th>Фильтр</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(port, index) in formData.power_ports" :key="index">
                      <td>
                        <EntitySelect
                          v-model="port.entity_id"
                          label="Entity"
                        />
                      </td>
                      <td>
                        <v-select
                          v-model="port.sign"
                          :items="[{ title: '+', value: '+' }, { title: '-', value: '-' }]"
                          variant="outlined"
                          density="compact"
                          hide-details
                        />
                      </td>
                      <td>
                        <v-select
                          :model-value="getFilterValue(port)"
                          :items="[
                            { title: 'Все значения', value: 'all' },
                            { title: 'Только положительные', value: 'positive' },
                            { title: 'Только отрицательные', value: 'negative' }
                          ]"
                          variant="outlined"
                          density="compact"
                          hide-details
                          @update:model-value="updateFilter(port, $event)"
                        />
                      </td>
                      <td>
                        <v-btn
                          icon
                          size="small"
                          color="error"
                          @click="removePowerPort(index)"
                        >
                          <v-icon>mdi-delete</v-icon>
                        </v-btn>
                      </td>
                    </tr>
                  </tbody>
                </v-table>
                <v-btn
                  color="primary"
                  variant="outlined"
                  prepend-icon="mdi-plus"
                  @click="addPowerPort"
                  class="mt-2"
                >
                  Добавить порт мощности
                </v-btn>
              </v-card-text>
            </v-card>

            <!-- Таблица портов онлайн -->
            <v-card class="mb-4" variant="outlined">
              <v-card-title class="text-subtitle-1">
                <v-icon class="me-2">mdi-network</v-icon>
                Порты онлайн
              </v-card-title>
              <v-card-text>
                <v-select
                  v-model="onlineLogic"
                  :items="[
                    { title: 'И (AND)', value: 'and' },
                    { title: 'ИЛИ (OR)', value: 'or' }
                  ]"
                  label="Логика"
                  class="mb-2"
                />
                <v-table>
                  <thead>
                    <tr>
                      <th>Entity ID</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(port, index) in formData.online_ports" :key="index">
                      <td>
                        <EntitySelect
                          v-model="port.entity_id"
                          label="Entity"
                        />
                      </td>
                      <td>
                        <v-btn
                          icon
                          size="small"
                          color="error"
                          @click="removeOnlinePort(index)"
                        >
                          <v-icon>mdi-delete</v-icon>
                        </v-btn>
                      </td>
                    </tr>
                  </tbody>
                </v-table>
                <v-btn
                  color="primary"
                  variant="outlined"
                  prepend-icon="mdi-plus"
                  @click="addOnlinePort"
                  class="mt-2"
                >
                  Добавить порт онлайн
                </v-btn>
              </v-card-text>
            </v-card>

            <!-- Таблица портов счетчика -->
            <v-card class="mb-4" variant="outlined">
              <v-card-title class="text-subtitle-1">
                <v-icon class="me-2">mdi-counter</v-icon>
                Порты счетчика
              </v-card-title>
              <v-card-text>
                <v-table>
                  <thead>
                    <tr>
                      <th>Entity ID</th>
                      <th>Знак</th>
                      <th>Фильтр</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(port, index) in formData.counter_ports" :key="index">
                      <td>
                        <EntitySelect
                          v-model="port.entity_id"
                          label="Entity"
                        />
                      </td>
                      <td>
                        <v-select
                          v-model="port.sign"
                          :items="[{ title: '+', value: '+' }, { title: '-', value: '-' }]"
                          variant="outlined"
                          density="compact"
                          hide-details
                        />
                      </td>
                      <td>
                        <v-select
                          :model-value="getFilterValue(port)"
                          :items="[
                            { title: 'Все значения', value: 'all' },
                            { title: 'Только положительные', value: 'positive' },
                            { title: 'Только отрицательные', value: 'negative' }
                          ]"
                          variant="outlined"
                          density="compact"
                          hide-details
                          @update:model-value="updateFilter(port, $event)"
                        />
                      </td>
                      <td>
                        <v-btn
                          icon
                          size="small"
                          color="error"
                          @click="removeCounterPort(index)"
                        >
                          <v-icon>mdi-delete</v-icon>
                        </v-btn>
                      </td>
                    </tr>
                  </tbody>
                </v-table>
                <v-btn
                  color="primary"
                  variant="outlined"
                  prepend-icon="mdi-plus"
                  @click="addCounterPort"
                  class="mt-2"
                >
                  Добавить порт счетчика
                </v-btn>
              </v-card-text>
            </v-card>
          </template>

          <!-- Таблица расходов для воды, осмоса, газа -->
          <template v-if="['water', 'reverse_osmosis', 'gas'].includes(formData.group)">
            <v-card class="mb-4" variant="outlined">
              <v-card-title class="text-subtitle-1">
                <v-icon class="me-2">mdi-water</v-icon>
                Порты расхода
              </v-card-title>
              <v-card-text>
                <v-table>
                  <thead>
                    <tr>
                      <th>Entity ID</th>
                      <th>Знак</th>
                      <th>Фильтр</th>
                      <th v-if="formData.group === 'reverse_osmosis'">Назначение</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(port, index) in formData.consumption_ports" :key="index">
                      <td>
                        <EntitySelect
                          v-model="port.entity_id"
                          label="Entity"
                        />
                      </td>
                      <td>
                        <v-select
                          v-model="port.sign"
                          :items="[{ title: '+', value: '+' }, { title: '-', value: '-' }]"
                          variant="outlined"
                          density="compact"
                          hide-details
                        />
                      </td>
                      <td>
                        <v-select
                          :model-value="getFilterValue(port)"
                          :items="[
                            { title: 'Все значения', value: 'all' },
                            { title: 'Только положительные', value: 'positive' },
                            { title: 'Только отрицательные', value: 'negative' }
                          ]"
                          variant="outlined"
                          density="compact"
                          hide-details
                          @update:model-value="updateFilter(port, $event)"
                        />
                      </td>
                      <td v-if="formData.group === 'reverse_osmosis'">
                        <v-select
                          v-model="port.purpose"
                          :items="[
                            { title: 'Вход', value: 'input' },
                            { title: 'Отход', value: 'waste' },
                            { title: 'Чистая', value: 'clean' }
                          ]"
                          variant="outlined"
                          density="compact"
                          hide-details
                        />
                      </td>
                      <td>
                        <v-btn
                          icon
                          size="small"
                          color="error"
                          @click="removeConsumptionPort(index)"
                        >
                          <v-icon>mdi-delete</v-icon>
                        </v-btn>
                      </td>
                    </tr>
                  </tbody>
                </v-table>
                <v-btn
                  color="primary"
                  variant="outlined"
                  prepend-icon="mdi-plus"
                  @click="addConsumptionPort"
                  class="mt-2"
                >
                  Добавить порт расхода
                </v-btn>
              </v-card-text>
            </v-card>

            <!-- Таблица параметров для воды -->
            <template v-if="formData.group === 'water'">
              <v-card class="mb-4" variant="outlined">
                <v-card-title class="text-subtitle-1">
                  <v-icon class="me-2">mdi-information</v-icon>
                  Параметры
                </v-card-title>
                <v-card-text>
                  <v-table>
                    <thead>
                      <tr>
                        <th>Параметр</th>
                        <th>Порт</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td><strong>Температура</strong></td>
                        <td>
                          <EntitySelect
                            v-model="formData.water_params.temperature_entity_id"
                            label="Порт температуры"
                            density="compact"
                            hide-details
                          />
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Давление</strong></td>
                        <td>
                          <EntitySelect
                            v-model="formData.water_params.pressure_entity_id"
                            label="Порт давления"
                            density="compact"
                            hide-details
                          />
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Жесткость</strong></td>
                        <td>
                          <EntitySelect
                            v-model="formData.water_params.hardness_entity_id"
                            label="Порт жесткости"
                            density="compact"
                            hide-details
                          />
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Ph</strong></td>
                        <td>
                          <EntitySelect
                            v-model="formData.water_params.ph_entity_id"
                            label="Порт Ph"
                            density="compact"
                            hide-details
                          />
                        </td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-card-text>
              </v-card>
            </template>

            <!-- Таблица параметров для осмоса -->
            <template v-if="formData.group === 'reverse_osmosis'">
              <v-card class="mb-4" variant="outlined">
                <v-card-title class="text-subtitle-1">
                  <v-icon class="me-2">mdi-information</v-icon>
                  Параметры
                </v-card-title>
                <v-card-text>
                  <v-table>
                    <thead>
                      <tr>
                        <th>Параметр</th>
                        <th>Вход</th>
                        <th>Отход</th>
                        <th>Чистая</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td><strong>Температура</strong></td>
                        <td>
                          <EntitySelect
                            v-model="formData.osmosis_params.temperature_input"
                            label="Температура вход"
                            density="compact"
                            hide-details
                          />
                        </td>
                        <td>
                          <EntitySelect
                            v-model="formData.osmosis_params.temperature_waste"
                            label="Температура отход"
                            density="compact"
                            hide-details
                          />
                        </td>
                        <td>
                          <EntitySelect
                            v-model="formData.osmosis_params.temperature_clean"
                            label="Температура чистая"
                            density="compact"
                            hide-details
                          />
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Давление</strong></td>
                        <td>
                          <EntitySelect
                            v-model="formData.osmosis_params.pressure_input"
                            label="Давление вход"
                            density="compact"
                            hide-details
                          />
                        </td>
                        <td>
                          <EntitySelect
                            v-model="formData.osmosis_params.pressure_waste"
                            label="Давление отход"
                            density="compact"
                            hide-details
                          />
                        </td>
                        <td>
                          <EntitySelect
                            v-model="formData.osmosis_params.pressure_clean"
                            label="Давление чистая"
                            density="compact"
                            hide-details
                          />
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Жесткость</strong></td>
                        <td>
                          <EntitySelect
                            v-model="formData.osmosis_params.hardness_input"
                            label="Жесткость вход"
                            density="compact"
                            hide-details
                          />
                        </td>
                        <td>
                          <EntitySelect
                            v-model="formData.osmosis_params.hardness_waste"
                            label="Жесткость отход"
                            density="compact"
                            hide-details
                          />
                        </td>
                        <td>
                          <EntitySelect
                            v-model="formData.osmosis_params.hardness_clean"
                            label="Жесткость чистая"
                            density="compact"
                            hide-details
                          />
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Ph</strong></td>
                        <td>
                          <EntitySelect
                            v-model="formData.osmosis_params.ph_input"
                            label="Ph вход"
                            density="compact"
                            hide-details
                          />
                        </td>
                        <td>
                          <EntitySelect
                            v-model="formData.osmosis_params.ph_waste"
                            label="Ph отход"
                            density="compact"
                            hide-details
                          />
                        </td>
                        <td>
                          <EntitySelect
                            v-model="formData.osmosis_params.ph_clean"
                            label="Ph чистая"
                            density="compact"
                            hide-details
                          />
                        </td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-card-text>
              </v-card>
            </template>
          </template>
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
          :disabled="!valid || saving"
        >
          Сохранить
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { secureFetch } from '@/services/fetch'
import useMessageStore from '@/store/messages'
import EntitySelect from '@/components/EntitySelect.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  source: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:show', 'saved'])

const messageStore = useMessageStore()
const form = ref(null)
const valid = ref(false)
const saving = ref(false)
const loadingGroups = ref(false)

const energyGroups = ref([])
const onlineLogic = ref('and')

const formData = ref({
  name: '',
  group: 'electric',
  active: true,
  priority: 0,
  output_power: 0.0,
  // Электричество
  power_ports: [],
  voltage_entity_id: null,
  frequency_entity_id: null,
  online_ports: [],
  counter_ports: [],
  color: null, // Для электричества
  // Вода, осмос, газ (расходы)
  consumption_ports: [],
  water_params: {
    temperature_entity_id: null,
    pressure_entity_id: null,
    hardness_entity_id: null,
    ph_entity_id: null
  },
  osmosis_params: {
    temperature_input: null,
    temperature_waste: null,
    temperature_clean: null,
    pressure_input: null,
    pressure_waste: null,
    pressure_clean: null,
    hardness_input: null,
    hardness_waste: null,
    hardness_clean: null,
    ph_input: null,
    ph_waste: null,
    ph_clean: null
  },
  // Другие группы
  other_color: '#1976d2'
})

const dialog = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val)
})

const loadGroups = async () => {
  loadingGroups.value = true
  try {
    const response = await secureFetch('/api/energy/groups')
    if (response.ok) {
      const data = await response.json()
      energyGroups.value = data.groups || []
    }
  } catch (err) {
    console.error('Error loading groups:', err)
  } finally {
    loadingGroups.value = false
  }
}

watch(() => props.show, (newVal) => {
  if (newVal && energyGroups.value.length === 0) {
    loadGroups()
  }
})

watch(() => props.source, (newSource) => {
  if (newSource) {
    // Миграция: если есть counter_entity_id, но нет counter_ports, преобразуем
    let counter_ports = newSource.counter_ports ? [...newSource.counter_ports] : []
    if (counter_ports.length === 0 && newSource.counter_entity_id) {
      counter_ports = [{
        entity_id: newSource.counter_entity_id,
        sign: '+',
        filter_positive: false,
        filter_negative: false
      }]
    }
    
    formData.value = {
      name: newSource.name || '',
      group: newSource.group || 'electric',
      active: newSource.active !== undefined ? newSource.active : true,
      priority: newSource.priority || 0,
      output_power: newSource.output_power || 0.0,
      power_ports: newSource.power_ports ? [...newSource.power_ports] : [],
      voltage_entity_id: newSource.voltage_entity_id || null,
      frequency_entity_id: newSource.frequency_entity_id || null,
      online_ports: newSource.online_ports ? [...newSource.online_ports] : [],
      counter_ports: counter_ports,
      color: newSource.color || (newSource.group === 'electric' ? getDefaultColorForGroup(newSource.group || 'electric') : null),
      consumption_ports: newSource.consumption_ports ? [...newSource.consumption_ports] : [],
      water_params: newSource.water_params ? { ...newSource.water_params } : {
        temperature_entity_id: null,
        pressure_entity_id: null,
        hardness_entity_id: null,
        ph_entity_id: null
      },
      osmosis_params: newSource.osmosis_params ? { ...newSource.osmosis_params } : {
        temperature_input: null,
        temperature_waste: null,
        temperature_clean: null,
        pressure_input: null,
        pressure_waste: null,
        pressure_clean: null,
        hardness_input: null,
        hardness_waste: null,
        hardness_clean: null,
        ph_input: null,
        ph_waste: null,
        ph_clean: null
      },
      other_color: newSource.other_color || newSource.color || getDefaultColorForGroup(newSource.group || 'electric')
    }
    onlineLogic.value = formData.value.online_ports.length > 0 
      ? formData.value.online_ports[0].logic || 'and'
      : 'and'
  } else {
    formData.value = {
      name: '',
      group: 'electric',
      active: true,
      priority: 0,
      output_power: 0.0,
      power_ports: [],
      voltage_entity_id: null,
      frequency_entity_id: null,
      online_ports: [],
      counter_ports: [],
      color: getDefaultColorForGroup('electric'),
      consumption_ports: [],
      water_params: {
        temperature_entity_id: null,
        pressure_entity_id: null,
        hardness_entity_id: null,
        ph_entity_id: null
      },
      osmosis_params: {
        temperature_input: null,
        temperature_waste: null,
        temperature_clean: null,
        pressure_input: null,
        pressure_waste: null,
        pressure_clean: null,
        hardness_input: null,
        hardness_waste: null,
        hardness_clean: null,
        ph_input: null,
        ph_waste: null,
        ph_clean: null
      },
      other_color: getDefaultColorForGroup('electric')
    }
    onlineLogic.value = 'and'
  }
}, { immediate: true })

watch(() => onlineLogic.value, (newVal) => {
  formData.value.online_ports.forEach(port => {
    port.logic = newVal
  })
})

const addPowerPort = () => {
  formData.value.power_ports.push({
    entity_id: '',
    sign: '+',
    filter_positive: false,
    filter_negative: false
  })
}

const removePowerPort = (index) => {
  formData.value.power_ports.splice(index, 1)
}

const addOnlinePort = () => {
  formData.value.online_ports.push({
    entity_id: '',
    logic: onlineLogic.value
  })
}

const removeOnlinePort = (index) => {
  formData.value.online_ports.splice(index, 1)
}

const addConsumptionPort = () => {
  formData.value.consumption_ports.push({
    entity_id: '',
    sign: '+',
    filter_positive: false,
    filter_negative: false,
    purpose: null // Для осмоса
  })
}

const removeConsumptionPort = (index) => {
  formData.value.consumption_ports.splice(index, 1)
}

const addCounterPort = () => {
  formData.value.counter_ports.push({
    entity_id: '',
    sign: '+',
    filter_positive: false,
    filter_negative: false
  })
}

const removeCounterPort = (index) => {
  formData.value.counter_ports.splice(index, 1)
}

const getFilterValue = (port) => {
  if (port.filter_positive) return 'positive'
  if (port.filter_negative) return 'negative'
  return 'all'
}

const updateFilter = (port, value) => {
  if (value === 'positive') {
    port.filter_positive = true
    port.filter_negative = false
  } else if (value === 'negative') {
    port.filter_positive = false
    port.filter_negative = true
  } else {
    port.filter_positive = false
    port.filter_negative = false
  }
}

const getPurposeLabel = (purpose) => {
  const labels = {
    'input': 'Вход',
    'waste': 'Отход',
    'clean': 'Чистая'
  }
  return labels[purpose] || purpose
}

const getDefaultColorForGroup = (group) => {
  // Сначала проверяем загруженные группы
  if (energyGroups.value.length > 0) {
    const groupData = energyGroups.value.find(g => g.id === group)
    if (groupData && groupData.default_color) {
      return groupData.default_color
    }
  }
  // Дефолтные цвета по группам (fallback)
  const defaultColors = {
    'electric': '#FFC107',  // Желтый/янтарный
    'gas': '#FF5722',       // Оранжево-красный
    'heat': '#F44336',      // Красный
    'water': '#2196F3',     // Синий
    'reverse_osmosis': '#00BCD4'  // Голубой/бирюзовый
  }
  return defaultColors[group] || '#1976d2'
}

// Автоматически устанавливаем дефолтный цвет при изменении группы
watch(() => formData.value.group, (newGroup, oldGroup) => {
  // Устанавливаем цвет только если группа действительно изменилась и это новое создание или цвет не был установлен
  if (!newGroup || newGroup === oldGroup) return
  
  const defaultColor = getDefaultColorForGroup(newGroup)
  
  if (newGroup === 'electric') {
    // Для электричества цвет в отдельном поле
    // Устанавливаем только если цвет не был явно задан пользователем
    if (!formData.value.color || formData.value.color === '#1976d2' || formData.value.color === getDefaultColorForGroup(oldGroup || 'electric')) {
      formData.value.color = defaultColor
    }
  } else {
    // Для других групп цвет в other_color
    // Устанавливаем только если цвет не был явно задан пользователем
    if (!formData.value.other_color || formData.value.other_color === '#1976d2' || (oldGroup && formData.value.other_color === getDefaultColorForGroup(oldGroup))) {
      formData.value.other_color = defaultColor
    }
  }
})

const close = () => {
  dialog.value = false
}

const save = async () => {
  if (!form.value) return
  if (!form.value.validate()) return

  saving.value = true

  try {
    const url = props.source
      ? `/api/energy/sources/${props.source.id}`
      : '/api/energy/sources'
    
    const method = props.source ? 'PUT' : 'POST'

    const response = await secureFetch(url, {
      method,
      body: JSON.stringify(formData.value)
    })

    if (response.ok) {
      messageStore.showSuccess('Источник сохранен')
      emit('saved')
      close()
    } else {
      const error = await response.json()
      messageStore.showError(error.detail || error.message || 'Ошибка сохранения источника')
    }
  } catch (err) {
    console.error('Error saving source:', err)
    messageStore.showError('Ошибка сохранения источника')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadGroups()
})
</script>

<style scoped>
</style>
