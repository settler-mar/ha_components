<template>
  <div>
    <div class="d-flex justify-space-between align-center mb-2">
      <span class="text-caption text-grey">
        {{ portType === 'input' ? 'Входные' : 'Выходные' }} параметры модуля
      </span>
      <v-btn
        size="small"
        prepend-icon="mdi-plus"
        @click="addPort"
      >
        Добавить
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
                v-model="port.name"
                label="Название"
                density="compact"
                class="mb-2"
                hide-details
              />
              <v-text-field
                v-model="port.type"
                label="Тип"
                density="compact"
                class="mb-2"
                hide-details
                hint="Тип данных (int, float, bool, string)"
              />
              <v-textarea
                v-model="port.description"
                label="Описание"
                density="compact"
                rows="2"
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
      Нет {{ portType === 'input' ? 'входных' : 'выходных' }} параметров
    </v-alert>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  },
  portType: {
    type: String,
    required: true,
    validator: (value) => ['input', 'output'].includes(value)
  }
})

const emit = defineEmits(['update:modelValue'])

const ports = computed({
  get: () => props.modelValue || [],
  set: (value) => emit('update:modelValue', value)
})

const addPort = () => {
  ports.value = [...ports.value, {
    name: '',
    type: 'float',
    description: ''
  }]
}

const removePort = (index) => {
  ports.value = ports.value.filter((_, i) => i !== index)
}
</script>

<style scoped>
</style>



