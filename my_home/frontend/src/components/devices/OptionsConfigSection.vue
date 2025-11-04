<template>
  <div class="options-config-section">
    <div class="section-header mb-4">
      <h3 class="text-h6 mb-2">
        <v-icon class="me-2">mdi-cog-box</v-icon>
        Options и Config порты
      </h3>
      <p class="text-body-2 text-grey">
        Просмотр значений портов с режимом options и config
      </p>
    </div>

    <v-tabs v-model="activeTab" class="mb-4">
      <v-tab value="options" v-if="optionsPorts.length">
        Options ({{ optionsPorts.length }})
      </v-tab>
      <v-tab value="config" v-if="configPorts.length">
        Config ({{ configPorts.length }})
      </v-tab>
    </v-tabs>

    <v-tabs-window v-model="activeTab">
      <v-tabs-window-item value="options" v-if="optionsPorts.length">
        <v-card variant="outlined">
          <v-card-text>
            <v-table density="compact">
              <thead>
                <tr>
                  <th class="text-left">Порт</th>
                  <th class="text-right">Значение</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="port in optionsPorts" :key="port.id || port.code">
                  <td>
                    <v-tooltip location="top">
                      <template #activator="{ props }">
                        <div v-bind="props" class="d-flex align-center">
                          <v-icon size="small" class="me-2" :color="getPortColor(port)">
                            {{ getPortIcon(port) }}
                          </v-icon>
                          <span>{{ port.label || port.name || port.code }}</span>
                        </div>
                      </template>
                      <div>
                        <div><strong>Код:</strong> {{ port.code }}</div>
                        <div v-if="port.description"><strong>Описание:</strong> {{ port.description }}</div>
                        <div v-if="port.type"><strong>Тип:</strong> {{ port.type }}</div>
                        <div v-if="port.unit"><strong>Единица:</strong> {{ port.unit }}</div>
                      </div>
                    </v-tooltip>
                  </td>
                  <td class="text-right">
                    <span class="font-weight-medium">{{ getPortValue(port) }}</span>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-tabs-window-item>

      <v-tabs-window-item value="config" v-if="configPorts.length">
        <v-card variant="outlined">
          <v-card-text>
            <v-table density="compact">
              <thead>
                <tr>
                  <th class="text-left">Порт</th>
                  <th class="text-right">Значение</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="port in configPorts" :key="port.id || port.code">
                  <td>
                    <v-tooltip location="top">
                      <template #activator="{ props }">
                        <div v-bind="props" class="d-flex align-center">
                          <v-icon size="small" class="me-2" :color="getPortColor(port)">
                            {{ getPortIcon(port) }}
                          </v-icon>
                          <span>{{ port.label || port.name || port.code }}</span>
                        </div>
                      </template>
                      <div>
                        <div><strong>Код:</strong> {{ port.code }}</div>
                        <div v-if="port.description"><strong>Описание:</strong> {{ port.description }}</div>
                        <div v-if="port.type"><strong>Тип:</strong> {{ port.type }}</div>
                        <div v-if="port.unit"><strong>Единица:</strong> {{ port.unit }}</div>
                      </div>
                    </v-tooltip>
                  </td>
                  <td class="text-right">
                    <span class="font-weight-medium">{{ getPortValue(port) }}</span>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-tabs-window-item>
    </v-tabs-window>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  portsData: {
    type: Array,
    default: () => []
  }
})

const activeTab = ref('options')

const isConfig = (port) => port.mode === 'config'
const isOptions = (port) => port.mode === 'options'

const optionsPorts = computed(() => (props.portsData || []).filter(p => isOptions(p)))
const configPorts = computed(() => (props.portsData || []).filter(p => isConfig(p)))

const getPortValue = (port) => {
  if (port.value !== undefined && port.value !== null) {
    return String(port.value)
  }
  return '—'
}

const getPortIcon = (port) => {
  if (port.type) {
    if (port.type.includes('temp')) return 'mdi-thermometer'
    if (port.type.includes('humidity')) return 'mdi-water-percent'
    if (port.type.includes('pressure')) return 'mdi-gauge'
    if (port.type.includes('voltage') || port.type.includes('current') || port.type.includes('power')) return 'mdi-lightning-bolt'
    if (port.type.includes('energy')) return 'mdi-battery'
    if (port.type.includes('switch') || port.type.includes('button')) return 'mdi-toggle-switch'
    if (port.type.includes('sensor')) return 'mdi-eye'
    if (port.type.includes('out.')) return 'mdi-cog'
  }
  return 'mdi-circle-outline'
}

const getPortColor = (port) => {
  if (port.type) {
    if (port.type.includes('temp')) return 'orange'
    if (port.type.includes('humidity')) return 'blue'
    if (port.type.includes('pressure')) return 'purple'
    if (port.type.includes('voltage') || port.type.includes('current') || port.type.includes('power')) return 'red'
    if (port.type.includes('energy')) return 'green'
    if (port.type.includes('switch') || port.type.includes('button')) return 'primary'
    if (port.type.includes('sensor')) return 'teal'
    if (port.type.includes('out.')) return 'grey'
  }
  return 'grey'
}
</script>

<style scoped>
.options-config-section {
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

