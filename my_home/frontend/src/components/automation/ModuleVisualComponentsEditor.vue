<template>
  <div>
    <v-btn
      color="primary"
      variant="outlined"
      prepend-icon="mdi-plus"
      @click="addComponent"
      class="mb-3"
    >
      Добавить визуальный компонент
    </v-btn>

    <v-expansion-panels v-if="components.length > 0" multiple class="mb-3">
      <v-expansion-panel
        v-for="(component, index) in components"
        :key="index"
        :value="index"
      >
        <v-expansion-panel-title>
          <div class="d-flex align-center">
            <v-icon class="me-2">mdi-view-dashboard</v-icon>
            <span>{{ component.name || 'Новый компонент' }}</span>
            <v-btn
              icon
              size="small"
              color="error"
              @click.stop="removeComponent(index)"
              class="ms-auto"
            >
              <v-icon>mdi-delete</v-icon>
            </v-btn>
          </div>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-row>
            <v-col cols="12">
              <v-text-field
                v-model="component.name"
                label="Имя компонента"
                density="compact"
                :rules="[v => !!v || 'Имя компонента обязательно']"
                hint="Имя компонента для отображения на панели HA"
                persistent-hint
              />
            </v-col>
            <v-col cols="12">
              <v-textarea
                v-model="component.description"
                label="Описание"
                density="compact"
                rows="2"
                hint="Описание компонента"
                persistent-hint
              />
            </v-col>
            <v-col cols="12">
              <div class="text-subtitle-2 mb-2">Параметры компонента</div>
              <v-btn
                color="primary"
                variant="text"
                size="small"
                prepend-icon="mdi-plus"
                @click="addParameter(index)"
                class="mb-2"
              >
                Добавить параметр
              </v-btn>
              <v-table v-if="component.parameters && Object.keys(component.parameters).length > 0" density="compact">
                <thead>
                  <tr>
                    <th>Ключ</th>
                    <th>Значение</th>
                    <th>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(value, key) in component.parameters" :key="key">
                    <td>
                      <v-text-field
                        :model-value="key"
                        density="compact"
                        hide-details
                        :rules="[v => !!v || 'Ключ обязателен']"
                        @input="updateParameterKey(index, key, $event.target.value)"
                      />
                    </td>
                    <td>
                      <v-text-field
                        v-model="component.parameters[key]"
                        density="compact"
                        hide-details
                        :rules="[v => v !== undefined && v !== null || 'Значение обязательно']"
                      />
                    </td>
                    <td>
                      <v-btn
                        icon
                        size="small"
                        color="error"
                        @click="removeParameter(index, key)"
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
                Нет параметров. Добавьте параметры для настройки компонента.
              </v-alert>
            </v-col>
          </v-row>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <v-alert
      v-else
      type="info"
      variant="tonal"
      density="compact"
    >
      Нет визуальных компонентов. Добавьте компоненты для интеграции на панель Home Assistant.
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

const components = computed({
  get: () => props.modelValue || [],
  set: (value) => emit('update:modelValue', value)
})

const addComponent = () => {
  components.value = [...components.value, {
    name: '',
    description: '',
    parameters: {}
  }]
}

const removeComponent = (index) => {
  components.value = components.value.filter((_, i) => i !== index)
}

const addParameter = (componentIndex) => {
  if (!components.value[componentIndex].parameters) {
    components.value[componentIndex].parameters = {}
  }
  const newKey = `param_${Date.now()}`
  // Создаем новый объект для реактивности
  components.value[componentIndex].parameters = {
    ...components.value[componentIndex].parameters,
    [newKey]: ''
  }
}

const removeParameter = (componentIndex, key) => {
  if (components.value[componentIndex].parameters) {
    const newParams = { ...components.value[componentIndex].parameters }
    delete newParams[key]
    // Создаем новый объект для реактивности
    components.value[componentIndex].parameters = newParams
  }
}

const updateParameterKey = (componentIndex, oldKey, newKey) => {
  if (oldKey === newKey || !newKey) return
  
  const component = components.value[componentIndex]
  if (component.parameters && component.parameters[oldKey] !== undefined) {
    const value = component.parameters[oldKey]
    const newParams = { ...component.parameters }
    delete newParams[oldKey]
    newParams[newKey] = value
    // Создаем новый объект для реактивности
    component.parameters = newParams
  }
}
</script>

<style scoped>
</style>

