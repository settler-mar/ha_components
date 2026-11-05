<template>
  <v-dialog v-model="dialog" max-width="1000px" scrollable persistent>
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <span>{{ instance ? 'Редактировать автоматизацию' : 'Создать автоматизацию' }}</span>
        <v-btn icon variant="text" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text>
        <v-progress-linear
          v-if="saving || loadingModule"
          color="primary"
          height="4"
          indeterminate
          rounded
          class="mb-4"
        />

        <v-form ref="form" v-model="valid">
          <v-row>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="formData.name"
                label="Название"
                :rules="[v => !!v || 'Название обязательно']"
                required
              />
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                v-model="formData.module_id"
                :items="modules"
                item-title="name"
                item-value="id"
                label="Модуль"
                :rules="[v => !!v || 'Модуль обязателен']"
                required
                @update:model-value="onModuleChange"
              >
                <template v-slot:item="{ props, item }">
                  <v-list-item v-bind="props">
                    <template v-slot:prepend>
                      <v-icon :color="item.raw.color || 'primary'">
                        {{ item.raw.icon || 'mdi-folder' }}
                      </v-icon>
                    </template>
                  </v-list-item>
                </template>
              </v-select>
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12">
              <v-textarea
                v-model="formData.description"
                label="Описание"
                rows="3"
              />
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12" md="6">
              <v-switch
                v-model="formData.active"
                label="Активна"
                color="success"
              />
            </v-col>
            <v-col cols="12" md="6">
              <div class="d-flex align-center">
                <v-select
                  v-model="formData.module_version"
                  :items="moduleVersions"
                  label="Версия модуля"
                  :rules="[v => !!v || 'Версия обязательна']"
                  required
                  :loading="loadingModule"
                  class="flex-grow-1"
                />
                <v-btn
                  v-if="props.instance && formData.module_version"
                  icon
                  variant="text"
                  @click="changeVersion"
                  title="Изменить версию"
                  class="ml-2"
                >
                  <v-icon>mdi-refresh</v-icon>
                </v-btn>
              </div>
            </v-col>
          </v-row>

          <!-- Порты входа -->
          <v-card v-if="selectedModuleVersion" class="mb-4" variant="outlined">
            <v-card-title class="text-subtitle-1">
              <v-icon class="me-2">mdi-arrow-down</v-icon>
              Порты входа
            </v-card-title>
            <v-card-text>
              <InstancePortsConfig
                v-model="formData.input_ports"
                :ports="selectedModuleVersion.input_ports || []"
              />
            </v-card-text>
          </v-card>

          <!-- Порты выхода -->
          <v-card v-if="selectedModuleVersion" class="mb-4" variant="outlined">
            <v-card-title class="text-subtitle-1">
              <v-icon class="me-2">mdi-arrow-up</v-icon>
              Порты выхода
            </v-card-title>
            <v-card-text>
              <InstancePortsConfig
                v-model="formData.output_ports"
                :ports="selectedModuleVersion.output_ports || []"
              />
            </v-card-text>
          </v-card>


          <!-- Параметры -->
          <v-card v-if="selectedModuleVersion && selectedModuleVersion.parameters?.length > 0" class="mb-4" variant="outlined">
            <v-card-title class="text-subtitle-1">
              <v-icon class="me-2">mdi-cog</v-icon>
              Параметры
            </v-card-title>
            <v-card-text>
              <InstanceParametersConfig
                v-model="formData.parameters"
                :parameters="selectedModuleVersion.parameters || []"
              />
            </v-card-text>
          </v-card>

          <!-- Визуальные компоненты -->
          <v-card v-if="selectedModuleVersion && selectedModuleVersion.visual_components?.length > 0" class="mb-4" variant="outlined">
            <v-card-title class="text-subtitle-1">
              <v-icon class="me-2">mdi-palette</v-icon>
              Визуальные компоненты для Home Assistant
            </v-card-title>
            <v-card-text>
              <div v-for="component in selectedModuleVersion.visual_components" :key="component.name" class="mb-3">
                <div class="text-body-2 font-weight-medium mb-1">
                  {{ component.name }}
                </div>
                <div v-if="component.description" class="text-caption text-grey mb-2">
                  {{ component.description }}
                </div>
                <v-expansion-panels variant="accordion" class="mt-2">
                  <v-expansion-panel>
                    <v-expansion-panel-title>
                      <span class="text-caption">Параметры компонента</span>
                    </v-expansion-panel-title>
                    <v-expansion-panel-text>
                      <pre class="text-caption">{{ JSON.stringify(component.parameters, null, 2) }}</pre>
                    </v-expansion-panel-text>
                  </v-expansion-panel>
                </v-expansion-panels>
              </div>
            </v-card-text>
          </v-card>
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
          :disabled="!valid || !formData.module_id || !formData.module_version"
        >
          Сохранить
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { secureFetch } from '@/services/fetch'
import useMessageStore from '@/store/messages'
import InstancePortsConfig from './InstancePortsConfig.vue'
import InstanceParametersConfig from './InstanceParametersConfig.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  instance: {
    type: Object,
    default: null
  },
  modules: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const messageStore = useMessageStore()
const form = ref(null)
const valid = ref(false)
const saving = ref(false)
const loadingModule = ref(false)

const dialog = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const formData = ref({
  name: '',
  description: '',
  module_id: null,
  module_version: null,
  active: true,
  input_ports: {},
  output_ports: {},
  parameters: {}
})

const selectedModule = computed(() => {
  return props.modules.find(m => m.id === formData.value.module_id)
})

const moduleVersions = computed(() => {
  if (!selectedModule.value) return []
  return (selectedModule.value.versions || []).map(v => ({
    title: `v${v.version}`,
    value: v.version,
    raw: v
  }))
})

const selectedModuleVersion = computed(() => {
  if (!formData.value.module_version || !selectedModule.value) return null
  return selectedModule.value.versions?.find(v => v.version === formData.value.module_version)
})

watch(() => props.instance, (newInstance) => {
  if (newInstance) {
    formData.value = {
      name: newInstance.name || '',
      description: newInstance.description || '',
      module_id: newInstance.module_id || null,
      module_version: newInstance.module_version || null,
      active: newInstance.active !== undefined ? newInstance.active : true,
      input_ports: { ...(newInstance.input_ports || {}) },
      output_ports: { ...(newInstance.output_ports || {}) },
      parameters: { ...(newInstance.parameters || {}) }
    }
  } else {
    formData.value = {
      name: '',
      description: '',
      module_id: null,
      module_version: null,
      active: true,
      input_ports: {},
      output_ports: {},
      parameters: {}
    }
  }
}, { immediate: true })

watch(() => formData.value.module_id, () => {
  // Сброс версии при смене модуля
  formData.value.module_version = null
  formData.value.input_ports = {}
  formData.value.output_ports = {}
  formData.value.parameters = {}
  
  // Установка версии по умолчанию если есть
  if (selectedModule.value?.current_version) {
    formData.value.module_version = selectedModule.value.current_version
  }
})

const onModuleChange = async () => {
  if (formData.value.module_id) {
    loadingModule.value = true
    try {
      const response = await secureFetch(`/api/automation/modules/${formData.value.module_id}`)
      if (response.ok) {
        const data = await response.json()
        // Обновляем модуль в списке
        const moduleIndex = props.modules.findIndex(m => m.id === formData.value.module_id)
        if (moduleIndex >= 0) {
          props.modules[moduleIndex] = data.module
        }
      }
    } catch (err) {
      console.error('Error loading module:', err)
    } finally {
      loadingModule.value = false
    }
  }
}

const changeVersion = async () => {
  if (!props.instance || !formData.value.module_version) return
  
  const newVersion = prompt('Введите новую версию модуля:', formData.value.module_version)
  if (!newVersion || newVersion === formData.value.module_version) return

  try {
    const response = await secureFetch(`/api/automation/instances/${props.instance.id}/version?new_version=${encodeURIComponent(newVersion)}`, {
      method: 'PUT'
    })

    if (response.ok) {
      messageStore.showSuccess('Версия модуля изменена')
      formData.value.module_version = newVersion
      emit('saved')
    } else {
      const errorData = await response.json()
      messageStore.showError(errorData.detail || 'Ошибка изменения версии')
    }
  } catch (err) {
    console.error('Error changing version:', err)
    messageStore.showError('Ошибка изменения версии')
  }
}

const close = () => {
  dialog.value = false
}

const save = async () => {
  if (!form.value) return
  
  const { valid: formValid } = await form.value.validate()
  if (!formValid) return

  saving.value = true

  try {
    const url = props.instance
      ? `/api/automation/instances/${props.instance.id}`
      : '/api/automation/instances'
    
    const method = props.instance ? 'PUT' : 'POST'

    const response = await secureFetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(formData.value)
    })

    if (response.ok) {
      messageStore.showSuccess(props.instance ? 'Автоматизация обновлена' : 'Автоматизация создана')
      emit('saved')
      close()
    } else {
      const errorData = await response.json()
      messageStore.showError(errorData.detail || 'Ошибка сохранения автоматизации')
    }
  } catch (err) {
    console.error('Error saving instance:', err)
    messageStore.showError('Ошибка сохранения автоматизации')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
</style>

