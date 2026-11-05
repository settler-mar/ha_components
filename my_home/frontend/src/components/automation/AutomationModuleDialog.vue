<template>
  <v-dialog v-model="dialog" max-width="800px" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <span>{{ module ? 'Редактировать модуль' : 'Добавить модуль' }}</span>
        <v-btn icon @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text>
        <v-progress-linear
          v-if="saving"
          color="primary"
          height="4"
          indeterminate
          rounded
          class="mb-4"
        />

        <v-form ref="form" v-model="valid">
          <v-text-field
            v-model="formData.name"
            label="Название модуля"
            required
            :rules="[v => !!v || 'Название обязательно']"
            class="mb-2"
          />

          <v-textarea
            v-model="formData.description"
            label="Описание"
            rows="2"
            class="mb-2"
          />

          <v-text-field
            v-model="formData.file_path"
            label="Путь к файлу модуля"
            required
            :rules="[v => !!v || 'Путь к файлу обязателен']"
            class="mb-2"
            hint="Относительный путь к файлу модуля в папке automation"
          />

          <!-- Входные параметры -->
          <v-card class="mb-4" variant="outlined">
            <v-card-title class="text-subtitle-1">
              <v-icon class="me-2">mdi-arrow-down</v-icon>
              Входные параметры
            </v-card-title>
            <v-card-text>
              <AutomationPortsEditor
                v-model="formData.inputs"
                port-type="input"
              />
            </v-card-text>
          </v-card>

          <!-- Выходные параметры -->
          <v-card class="mb-4" variant="outlined">
            <v-card-title class="text-subtitle-1">
              <v-icon class="me-2">mdi-arrow-up</v-icon>
              Выходные параметры
            </v-card-title>
            <v-card-text>
              <AutomationPortsEditor
                v-model="formData.outputs"
                port-type="output"
              />
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
          :disabled="!valid || saving"
        >
          Сохранить
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { secureFetch } from '@/services/fetch'
import useMessageStore from '@/store/messages'
import AutomationPortsEditor from './AutomationPortsEditor.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  module: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:show', 'saved'])

const messageStore = useMessageStore()
const form = ref(null)
const valid = ref(false)
const saving = ref(false)

const formData = ref({
  name: '',
  description: '',
  file_path: '',
  inputs: [],
  outputs: []
})

const dialog = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val)
})

watch(() => props.module, (newModule) => {
  if (newModule) {
    formData.value = {
      name: newModule.name || '',
      description: newModule.description || '',
      file_path: newModule.file_path || '',
      inputs: newModule.inputs || [],
      outputs: newModule.outputs || []
    }
  } else {
    formData.value = {
      name: '',
      description: '',
      file_path: '',
      inputs: [],
      outputs: []
    }
  }
}, { immediate: true })

const close = () => {
  dialog.value = false
}

const save = async () => {
  if (!form.value) return
  if (!form.value.validate()) return

  saving.value = true

  try {
    const url = props.module
      ? `/api/automation/modules/${props.module.id}`
      : '/api/automation/modules'
    
    const method = props.module ? 'PUT' : 'POST'

    const response = await secureFetch(url, {
      method,
      body: JSON.stringify(formData.value)
    })

    if (response.ok) {
      messageStore.showSuccess('Модуль сохранен')
      emit('saved')
      close()
    } else {
      const error = await response.json()
      messageStore.showError(error.message || 'Ошибка сохранения модуля')
    }
  } catch (err) {
    console.error('Error saving module:', err)
    messageStore.showError('Ошибка сохранения модуля')
  } finally {
    saving.value = false
  }
}
</script>


