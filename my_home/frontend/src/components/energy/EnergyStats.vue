<template>
  <v-card variant="outlined" class="pa-4">
    <div class="d-flex align-center justify-space-between mb-4">
      <h3 class="text-h6">Текущая мощность</h3>
      <v-chip
        size="large"
        :color="currentPowerColor"
        variant="elevated"
      >
        <v-icon start>mdi-lightning-bolt</v-icon>
        {{ currentPower }} W
      </v-chip>
    </div>

    <v-row>
      <v-col cols="12" sm="6" md="3">
        <div class="text-caption text-grey mb-1">Активных источников</div>
        <div class="text-h6">{{ activeSourcesCount }}</div>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <div class="text-caption text-grey mb-1">Общая мощность</div>
        <div class="text-h6">{{ totalPower }} W</div>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <div class="text-caption text-grey mb-1">Выбранная линия</div>
        <div class="text-h6">{{ selectedSourceName || 'Не выбрана' }}</div>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <div class="text-caption text-grey mb-1">Режим расчета</div>
        <div class="text-h6">{{ calculationModeText }}</div>
      </v-col>
    </v-row>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  sources: {
    type: Array,
    default: () => []
  },
  output: {
    type: Object,
    default: () => ({
      calculation_mode: 'sum',
      selected_source_id: null
    })
  }
})

const activeSources = computed(() => {
  return props.sources.filter(s => s.active)
})

const activeSourcesCount = computed(() => activeSources.value.length)

const totalPower = computed(() => {
  return activeSources.value.reduce((sum, s) => sum + (s.power || 0), 0)
})

const currentPower = computed(() => {
  if (!props.output || !activeSources.value.length) return 0

  const mode = props.output.calculation_mode || 'sum'
  
  switch (mode) {
    case 'max':
      return Math.max(...activeSources.value.map(s => s.power || 0))
    case 'min':
      return Math.min(...activeSources.value.map(s => s.power || 0))
    case 'sum':
    default:
      return totalPower.value
  }
})

const currentPowerColor = computed(() => {
  const power = currentPower.value
  if (power > 5000) return 'error'
  if (power > 3000) return 'warning'
  return 'success'
})

const selectedSourceName = computed(() => {
  if (!props.output?.selected_source_id) return null
  const source = props.sources.find(s => s.id === props.output.selected_source_id)
  return source?.name || null
})

const calculationModeText = computed(() => {
  const mode = props.output?.calculation_mode || 'sum'
  const modes = {
    sum: 'Сумма',
    max: 'Максимум',
    min: 'Минимум'
  }
  return modes[mode] || mode
})
</script>

<style scoped>
</style>



