<template>
  <v-dialog v-model="dialog" max-width="800" persistent>
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <span>Создать модуль</span>
        <v-btn icon variant="text" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text>
        <v-form ref="form">
          <v-row>
            <v-col cols="12">
              <v-file-input
                v-model="fileInput"
                label="Файл модуля"
                accept=".py,.js,.lua"
                hint="Загрузите файл модуля. Метаданные (название, описание, иконка, цвет) будут извлечены из файла."
                persistent-hint
                show-size
                :rules="[v => !!v || 'Файл модуля обязателен']"
                required
              />
              <v-alert
                type="info"
                variant="tonal"
                density="compact"
                class="mt-2"
              >
                <div class="text-body-2 mb-2">Метаданные модуля в YAML блоке в комментариях.</div>
                <div class="text-caption">
                  В начале файла должен быть docstring с блоком MODULE_METADATA:<br>
                  <pre class="text-caption mt-2" style="background: rgba(0,0,0,0.05); padding: 8px; border-radius: 4px; overflow-x: auto; font-size: 0.75rem;">"""
MODULE_METADATA:
name: "Название модуля"
description: "Описание"
icon: "mdi-folder"
color: "#1976d2"
version: "1.0.0"
min_compatible_version: null
class_name: "MyModule"
input_ports:
  - name: "port1"
    description: "Описание"
    required: true
output_ports: []
parameters:
  - name: "param1"
    type: "float"
    default: 0.0
visual_components:
  - name: "Название компонента"
    description: "Описание компонента"
    parameters:
      type: "card"
      title: "Заголовок"
      entity: "sensor.example"
      icon: "mdi-palette"
"""
</pre>
                  Затем следует класс с методом <code>process(self, input_ports, output_ports, parameters)</code>
                </div>
              </v-alert>
            </v-col>
          </v-row>
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
          :disabled="!fileInput || fileInput.length === 0"
        >
          Создать модуль
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { secureFetch, getApiUrl } from '@/services/fetch'
import useMessageStore from '@/store/messages'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  module: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const messageStore = useMessageStore()
const form = ref(null)
const saving = ref(false)
const fileInput = ref(null)
const uploadingFile = ref(false)

const dialog = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})


const close = () => {
  dialog.value = false
  fileInput.value = null
}

const save = async () => {
  if (!form.value) return
  
  const { valid } = await form.value.validate()
  if (!valid) return

  if (!fileInput.value || fileInput.value.length === 0) {
    messageStore.showError('Выберите файл модуля')
    return
  }

  saving.value = true

  try {
    const formDataToSend = new FormData()
    formDataToSend.append('file', fileInput.value[0])
    
    const apiUrl = getApiUrl('/api/automation/modules')
    const token = localStorage.getItem('ha_token') || localStorage.getItem('access_token')
    const headers = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: headers,
      body: formDataToSend
    })

    if (response.ok) {
      const data = await response.json()
      messageStore.showSuccess(`Модуль "${data.module.name}" создан`)
      emit('saved')
      close()
    } else {
      const errorData = await response.json()
      messageStore.showError(errorData.detail || 'Ошибка создания модуля')
    }
  } catch (err) {
    console.error('Error saving module:', err)
    messageStore.showError('Ошибка создания модуля')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
</style>

