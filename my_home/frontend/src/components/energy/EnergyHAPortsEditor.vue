<template>
  <div>
    <div class="d-flex justify-space-between align-center mb-2">
      <span class="text-caption text-grey">
        Порты из Home Assistant для источника
      </span>
      <v-btn
        size="small"
        prepend-icon="mdi-plus"
        @click="addPort"
      >
        Добавить порт
      </v-btn>
    </div>

    <v-list v-if="ports.length > 0">
      <v-list-item
        v-for="(port, index) in ports"
        :key="index"
        class="pa-2"
      >
        <v-card variant="outlined" class="pa-2">
          <div class="d-flex align-center justify-space-between">
            <div class="flex-grow-1">
              <v-text-field
                v-model="port.entity_id"
                label="Entity ID"
                density="compact"
                class="mb-2"
                hide-details
                hint="ID сущности в Home Assistant"
              />
              <v-select
                v-model="port.sign"
                :items="signOptions"
                label="Знак"
                density="compact"
                class="mb-2"
                hide-details
              />
              <v-checkbox
                v-model="port.positive_only"
                label="Только положительные значения"
                density="compact"
                hide-details
                class="mb-2"
              />
              <v-checkbox
                v-model="port.negative_only"
                label="Только отрицательные значения"
                density="compact"
                hide-details
              />
            </div>
            <v-btn
              icon
              size="small"
              color="error"
              @click="removePort(index)"
              class="ml-2"
            >
              <v-icon>mdi-delete</v-icon>
            </v-btn>
          </div>
        </v-card>
      </v-list-item>
    </v-list>

    <v-alert
      v-else
      type="info"
      variant="tonal"
      density="compact"
    >
      Нет портов Home Assistant
    </v-alert>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue'])

const signOptions = [
  { title: 'Плюс (+)', value: '+' },
  { title: 'Минус (-)', value: '-' }
]

const ports = computed({
  get: () => props.modelValue || [],
  set: (value) => emit('update:modelValue', value)
})

const addPort = () => {
  ports.value = [...ports.value, {
    entity_id: '',
    sign: '+',
    positive_only: false,
    negative_only: false
  }]
}

const removePort = (index) => {
  ports.value = ports.value.filter((_, i) => i !== index)
}
</script>

<style scoped>
</style>



