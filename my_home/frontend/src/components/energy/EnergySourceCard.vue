<template>
  <v-card variant="outlined" elevation="1">
    <v-card-title class="d-flex align-center justify-space-between">
      <div class="d-flex align-center">
        <v-icon
          class="me-2"
          :color="getGroupColor()"
        >
          {{ getGroupIcon() }}
        </v-icon>
        <span>{{ source.name }}</span>
        <v-chip
          size="x-small"
          :color="source.active ? 'success' : 'grey'"
          variant="tonal"
          class="ms-2"
        >
          {{ source.active ? 'Активен' : 'Неактивен' }}
        </v-chip>
        <v-chip
          size="x-small"
          variant="outlined"
          class="ms-2"
        >
          {{ getGroupName() }}
        </v-chip>
      </div>
      <div>
        <v-btn
          icon
          size="small"
          @click="$emit('edit', source)"
          title="Редактировать"
        >
          <v-icon>mdi-pencil</v-icon>
        </v-btn>
        <v-btn
          icon
          size="small"
          color="error"
          @click="$emit('delete', source)"
          title="Удалить"
        >
          <v-icon>mdi-delete</v-icon>
        </v-btn>
      </div>
    </v-card-title>

    <v-card-text>
      <v-row>
        <v-col v-if="source.group === 'electric'" cols="12" sm="6" md="3">
          <div class="text-caption text-grey mb-1">Выдаваемая мощность</div>
          <div class="text-h6">{{ source.output_power || 0 }} W</div>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <div class="text-caption text-grey mb-1">Приоритет</div>
          <div class="text-h6">{{ source.priority || 0 }}</div>
        </v-col>
        <template v-if="source.group === 'electric'">
          <v-col cols="12" sm="6" md="3">
            <div class="text-caption text-grey mb-1">Напряжение</div>
            <div class="text-body-2">{{ source.voltage_entity_id || 'N/A' }}</div>
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <div class="text-caption text-grey mb-1">Частота</div>
            <div class="text-body-2">{{ source.frequency_entity_id || 'N/A' }}</div>
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <div class="text-caption text-grey mb-1">Цвет</div>
            <div class="d-flex align-center">
              <div
                class="color-preview"
                :style="{ backgroundColor: source.color || '#1976d2' }"
              ></div>
            </div>
          </v-col>
        </template>
        <template v-else>
          <v-col cols="12" sm="6" md="3">
            <div class="text-caption text-grey mb-1">Цвет</div>
            <div class="d-flex align-center">
              <div
                class="color-preview"
                :style="{ backgroundColor: source.other_color || source.color || '#1976d2' }"
              ></div>
            </div>
          </v-col>
        </template>
      </v-row>

      <!-- Параметры для электричества -->
      <template v-if="source.group === 'electric'">
        <v-divider class="my-2"></v-divider>

        <div class="text-caption text-grey mb-1">Порты мощности</div>
        <div class="d-flex flex-wrap gap-1 mb-2">
          <v-chip
            v-for="(port, index) in source.power_ports"
            :key="index"
            size="x-small"
            variant="outlined"
          >
            {{ port.entity_id }} ({{ port.sign }})
          </v-chip>
          <span v-if="!source.power_ports || source.power_ports.length === 0" class="text-caption text-grey">
            Нет портов мощности
          </span>
        </div>

        <div class="text-caption text-grey mb-1">Порты онлайн</div>
        <div class="d-flex flex-wrap gap-1 mb-2">
          <v-chip
            v-for="(port, index) in source.online_ports"
            :key="index"
            size="x-small"
            variant="outlined"
          >
            {{ port.entity_id }}
          </v-chip>
          <span v-if="!source.online_ports || source.online_ports.length === 0" class="text-caption text-grey">
            Нет портов онлайн
          </span>
        </div>

        <div class="text-caption text-grey mb-1">Порты счетчика</div>
        <div class="d-flex flex-wrap gap-1 mb-2">
          <template v-if="source.counter_ports && source.counter_ports.length > 0">
            <v-chip
              v-for="(port, index) in source.counter_ports"
              :key="index"
              size="x-small"
              variant="outlined"
            >
              {{ port.entity_id }} ({{ port.sign }})
            </v-chip>
          </template>
          <template v-else-if="source.counter_entity_id">
            <!-- Миграция: показываем старый counter_entity_id -->
            <v-chip
              size="x-small"
              variant="outlined"
            >
              {{ source.counter_entity_id }} (+)
            </v-chip>
          </template>
          <span v-else class="text-caption text-grey">
            Нет портов счетчика
          </span>
        </div>
      </template>

      <!-- Параметры для воды, осмоса, газа (расходы) -->
      <template v-if="['water', 'reverse_osmosis', 'gas'].includes(source.group)">
        <v-divider class="my-2"></v-divider>

        <div class="text-caption text-grey mb-1">Порты расхода</div>
        <div class="d-flex flex-wrap gap-1 mb-2">
          <v-chip
            v-for="(port, index) in source.consumption_ports"
            :key="index"
            size="x-small"
            variant="outlined"
          >
            {{ port.entity_id }} ({{ port.sign }})
            <span v-if="source.group === 'reverse_osmosis' && port.purpose" class="ms-1">
              - {{ getPurposeLabel(port.purpose) }}
            </span>
          </v-chip>
          <span v-if="!source.consumption_ports || source.consumption_ports.length === 0" class="text-caption text-grey">
            Нет портов расхода
          </span>
        </div>

        <!-- Параметры для воды -->
        <template v-if="source.group === 'water' && source.water_params">
          <v-divider class="my-2"></v-divider>
          <div class="text-caption text-grey mb-2">Параметры</div>
          <v-table density="compact">
            <thead>
              <tr>
                <th>Параметр</th>
                <th>Порт</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Температура</strong></td>
                <td>{{ source.water_params.temperature_entity_id || 'N/A' }}</td>
              </tr>
              <tr>
                <td><strong>Давление</strong></td>
                <td>{{ source.water_params.pressure_entity_id || 'N/A' }}</td>
              </tr>
              <tr>
                <td><strong>Жесткость</strong></td>
                <td>{{ source.water_params.hardness_entity_id || 'N/A' }}</td>
              </tr>
              <tr>
                <td><strong>Ph</strong></td>
                <td>{{ source.water_params.ph_entity_id || 'N/A' }}</td>
              </tr>
            </tbody>
          </v-table>
        </template>

        <!-- Параметры для осмоса -->
        <template v-if="source.group === 'reverse_osmosis' && source.osmosis_params">
          <v-divider class="my-2"></v-divider>
          <div class="text-caption text-grey mb-2">Параметры</div>
          <v-table density="compact">
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
                <td>{{ source.osmosis_params.temperature_input || 'N/A' }}</td>
                <td>{{ source.osmosis_params.temperature_waste || 'N/A' }}</td>
                <td>{{ source.osmosis_params.temperature_clean || 'N/A' }}</td>
              </tr>
              <tr>
                <td><strong>Давление</strong></td>
                <td>{{ source.osmosis_params.pressure_input || 'N/A' }}</td>
                <td>{{ source.osmosis_params.pressure_waste || 'N/A' }}</td>
                <td>{{ source.osmosis_params.pressure_clean || 'N/A' }}</td>
              </tr>
              <tr>
                <td><strong>Жесткость</strong></td>
                <td>{{ source.osmosis_params.hardness_input || 'N/A' }}</td>
                <td>{{ source.osmosis_params.hardness_waste || 'N/A' }}</td>
                <td>{{ source.osmosis_params.hardness_clean || 'N/A' }}</td>
              </tr>
              <tr>
                <td><strong>Ph</strong></td>
                <td>{{ source.osmosis_params.ph_input || 'N/A' }}</td>
                <td>{{ source.osmosis_params.ph_waste || 'N/A' }}</td>
                <td>{{ source.osmosis_params.ph_clean || 'N/A' }}</td>
              </tr>
            </tbody>
          </v-table>
        </template>
      </template>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { secureFetch } from '@/services/fetch'

const props = defineProps({
  source: {
    type: Object,
    required: true
  }
})

defineEmits(['edit', 'delete'])

const energyGroups = ref([])

const getGroupName = () => {
  const group = energyGroups.value.find(g => g.id === props.source.group)
  return group ? group.name : props.source.group
}

const getGroupIcon = () => {
  const group = energyGroups.value.find(g => g.id === props.source.group)
  return group ? group.icon : 'mdi-circle'
}

const getGroupColor = () => {
  if (props.source.group === 'electric') return 'primary'
  if (props.source.group === 'gas') return 'orange'
  if (props.source.group === 'heat') return 'red'
  if (props.source.group === 'water') return 'blue'
  if (props.source.group === 'reverse_osmosis') return 'cyan'
  return props.source.color || 'primary'
}

const getPurposeLabel = (purpose) => {
  const labels = {
    'input': 'Вход',
    'waste': 'Отход',
    'clean': 'Чистая'
  }
  return labels[purpose] || purpose
}


const loadGroups = async () => {
  try {
    const response = await secureFetch('/api/energy/groups')
    if (response.ok) {
      const data = await response.json()
      energyGroups.value = data.groups || []
    }
  } catch (err) {
    console.error('Error loading groups:', err)
  }
}

onMounted(() => {
  if (energyGroups.value.length === 0) {
    loadGroups()
  }
})
</script>

<style scoped>
.color-preview {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.12);
}
</style>
