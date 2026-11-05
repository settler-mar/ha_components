<template>
  <div>
    <v-btn
      color="primary"
      variant="outlined"
      prepend-icon="mdi-plus"
      @click="addPort"
      class="mb-3"
    >
      Добавить виртуальный порт
    </v-btn>

    <v-table v-if="ports.length > 0" density="compact">
      <thead>
        <tr>
          <th>Название</th>
          <th>Описание</th>
          <th>Обязательный</th>
          <th>Действия</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(port, index) in ports" :key="index">
          <td>
            <v-text-field
              v-model="port.name"
              density="compact"
              hide-details
              :rules="[v => !!v || 'Название обязательно']"
            />
          </td>
          <td>
            <v-text-field
              v-model="port.description"
              density="compact"
              hide-details
            />
          </td>
          <td>
            <v-checkbox
              v-model="port.required"
              density="compact"
              hide-details
              label="Обязательный"
            />
          </td>
          <td>
            <v-btn
              icon
              size="small"
              color="error"
              @click="removePort(index)"
            >
              <v-icon>mdi-delete</v-icon>
            </v-btn>
          </td>
        </tr>
      </tbody>
    </v-table>

    <v-alert
      v-else
      type="info"
      variant="tonal"
      density="compact"
    >
      Нет виртуальных портов
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

const ports = computed({
  get: () => props.modelValue || [],
  set: (value) => emit('update:modelValue', value)
})

const addPort = () => {
  ports.value = [...ports.value, {
    name: '',
    description: '',
    purpose: 'input',
    is_list: false,
    entity_id: null,
    required: false
  }]
}

const removePort = (index) => {
  ports.value = ports.value.filter((_, i) => i !== index)
}
</script>

<style scoped>
</style>


