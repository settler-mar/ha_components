<template>
  <div>
    <v-row>
      <v-col cols="12" md="6">
        <v-select
          v-model="output.calculation_mode"
          :items="calculationModes"
          label="Режим расчета мощности"
          hint="Как рассчитывается текущая мощность из активных источников"
        />
      </v-col>
      <v-col cols="12" md="6">
        <v-select
          v-model="output.priority_logic"
          :items="priorityLogics"
          label="Логика выбора основной линии"
          hint="Как выбирается основная (выбранная) линия"
        />
      </v-col>
    </v-row>

    <v-select
      v-model="output.selected_source_id"
      :items="availableSources"
      label="Выбранная основная линия"
      hint="Основная линия (может быть выбрана автоматически по логике)"
      clearable
      class="mt-4"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  },
  sources: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue'])

const calculationModes = [
  { title: 'Сумма всех активных', value: 'sum' },
  { title: 'Максимум среди активных', value: 'max' },
  { title: 'Минимум среди активных', value: 'min' }
]

const priorityLogics = [
  { title: 'По приоритету', value: 'priority' },
  { title: 'По мощности', value: 'power' }
]

const output = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const availableSources = computed(() => {
  return props.sources
    .filter(s => s.active)
    .map(s => ({
      title: s.name,
      value: s.id
    }))
})
</script>

<style scoped>
</style>



