<template>
  <div>
    <v-btn
      color="primary"
      variant="outlined"
      prepend-icon="mdi-plus"
      @click="addParameter"
      class="mb-3"
    >
      Добавить параметр
    </v-btn>

    <v-table v-if="parameters.length > 0" density="compact">
      <thead>
        <tr>
          <th>Название</th>
          <th>Тип</th>
          <th>Значение/Entity</th>
          <th>Обязательный</th>
          <th>Действия</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(param, index) in parameters" :key="index">
          <td>
            <v-text-field
              v-model="param.name"
              density="compact"
              hide-details
              :rules="[v => !!v || 'Название обязательно']"
            />
          </td>
          <td>
            <v-select
              v-model="param.type"
              :items="[
                { title: 'Фиксированное', value: 'fixed' },
                { title: 'Entity', value: 'entity' }
              ]"
              density="compact"
              hide-details
            />
          </td>
          <td>
            <v-text-field
              v-if="param.type === 'fixed'"
              v-model="param.value"
              density="compact"
              hide-details
              type="number"
              step="any"
            />
            <EntitySelect
              v-else
              v-model="param.entity_id"
              density="compact"
              hide-details
            />
          </td>
          <td>
            <v-checkbox
              v-model="param.required"
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
              @click="removeParameter(index)"
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
      Нет параметров
    </v-alert>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import EntitySelect from '@/components/EntitySelect.vue'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue'])

const parameters = computed({
  get: () => props.modelValue || [],
  set: (value) => emit('update:modelValue', value)
})

const addParameter = () => {
  parameters.value = [...parameters.value, {
    name: '',
    description: '',
    type: 'fixed',
    value: null,
    entity_id: null,
    required: false
  }]
}

const removeParameter = (index) => {
  parameters.value = parameters.value.filter((_, i) => i !== index)
}
</script>

<style scoped>
</style>


