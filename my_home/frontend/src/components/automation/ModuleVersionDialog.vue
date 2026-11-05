<template>
  <v-dialog v-model="dialog" max-width="1200px" scrollable persistent>
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <div class="d-flex align-center">
          <v-icon class="me-2">{{ module?.icon || 'mdi-folder' }}</v-icon>
          <span>Управление версиями: {{ module?.name }}</span>
        </div>
        <v-btn icon variant="text" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text>
        <v-tabs v-model="currentTab" class="mb-4">
          <v-tab value="versions">Версии</v-tab>
          <v-tab value="add">Добавить версию</v-tab>
        </v-tabs>

        <v-window v-model="currentTab">
          <!-- Список версий -->
          <v-window-item value="versions">
            <v-progress-linear
              v-if="loading"
              color="primary"
              height="4"
              indeterminate
              rounded
              class="mb-4"
            />

            <div v-if="!loading && (!module?.versions || module.versions.length === 0)" class="text-center text-grey py-8">
              <v-icon size="64" class="mb-4">mdi-code-braces</v-icon>
              <p>Нет версий модуля</p>
              <p class="text-caption">Добавьте первую версию модуля</p>
            </div>

            <v-list v-else>
              <v-list-item
                v-for="version in module?.versions || []"
                :key="version.version"
                :class="{ 'bg-primary-lighten-5': version.version === module?.current_version }"
              >
                <template v-slot:prepend>
                  <v-icon :color="version.version === module?.current_version ? 'primary' : 'grey'">
                    {{ version.version === module?.current_version ? 'mdi-star' : 'mdi-code-braces' }}
                  </v-icon>
                </template>

                <v-list-item-title>
                  <div class="d-flex align-center">
                    <span class="font-weight-medium">v{{ version.version }}</span>
                    <v-chip
                      v-if="version.version === module?.current_version"
                      size="x-small"
                      color="primary"
                      variant="tonal"
                      class="ms-2"
                    >
                      По умолчанию
                    </v-chip>
                    <v-chip
                      v-if="version.min_compatible_version"
                      size="x-small"
                      variant="outlined"
                      class="ms-2"
                    >
                      Совместимость: ≥v{{ version.min_compatible_version }}
                    </v-chip>
                  </div>
                </v-list-item-title>

                <v-list-item-subtitle>
                  <div v-if="version.created_at" class="text-caption text-grey">
                    Создано: {{ new Date(version.created_at).toLocaleString('ru-RU') }}
                  </div>
                  <div v-if="version.file_path" class="text-caption text-grey mt-1">
                    Файл: {{ version.file_path }}
                  </div>
                  <!-- Использование версии -->
                  <div v-if="getVersionUsage(version.version).length > 0" class="mt-2">
                    <div class="text-caption text-grey mb-1">Используется в:</div>
                    <v-chip
                      v-for="usage in getVersionUsage(version.version)"
                      :key="usage.instance_id"
                      size="x-small"
                      variant="outlined"
                      class="me-1"
                    >
                      {{ usage.instance_name }}
                    </v-chip>
                  </div>
                  <div v-if="getVersionUsage(version.version).length > 0" class="text-caption text-error mt-1">
                    Версия используется и не может быть удалена
                  </div>
                  <!-- Визуальные компоненты -->
                  <div v-if="version.visual_components && version.visual_components.length > 0" class="mt-2">
                    <div class="text-caption text-grey mb-1">Визуальные компоненты:</div>
                    <v-chip
                      v-for="component in version.visual_components"
                      :key="component.name"
                      size="x-small"
                      variant="tonal"
                      color="purple"
                      class="me-1 mb-1"
                    >
                      <v-icon size="12" class="me-1">mdi-palette</v-icon>
                      {{ component.name }}
                    </v-chip>
                  </div>
                </v-list-item-subtitle>

                <template v-slot:append>
                  <div class="d-flex align-center gap-2">
                    <v-btn
                      v-if="version.version !== module?.current_version"
                      size="small"
                      variant="text"
                      @click="setCurrentVersion(version.version)"
                      title="Установить по умолчанию"
                    >
                      <v-icon start>mdi-star-outline</v-icon>
                      По умолчанию
                    </v-btn>
                    <v-btn
                      size="small"
                      variant="outlined"
                      color="primary"
                      @click="viewVersionFile(version)"
                      title="Просмотреть файл"
                    >
                      <v-icon start>mdi-eye</v-icon>
                      Просмотреть
                    </v-btn>
                    <v-btn
                      size="small"
                      variant="outlined"
                      color="primary"
                      @click="downloadVersionFile(version)"
                      title="Скачать файл"
                    >
                      <v-icon start>mdi-download</v-icon>
                      Скачать
                    </v-btn>
                    <v-btn
                      size="small"
                      variant="text"
                      color="error"
                      @click="deleteVersion(version)"
                      title="Удалить версию"
                      :disabled="getVersionUsage(version.version).length > 0"
                    >
                      <v-icon start>mdi-delete</v-icon>
                      Удалить
                    </v-btn>
                  </div>
                </template>
              </v-list-item>
            </v-list>
          </v-window-item>

          <!-- Добавление версии -->
          <v-window-item value="add">
            <v-form ref="versionForm">
              <v-row>
                <v-col cols="12">
                  <v-file-input
                    v-model="versionFileInput"
                    label="Файл версии модуля"
                    accept=".py,.js,.lua"
                    hint="Загрузите файл версии модуля. Версия и минимальная совместимая версия будут извлечены из файла."
                    persistent-hint
                    show-size
                    :rules="[v => !!v || 'Файл версии обязателен']"
                    required
                  />
                  <v-alert
                    type="info"
                    variant="tonal"
                    density="compact"
                    class="mt-2"
                  >
                    <div class="text-body-2 mb-2">Версия модуля - это файл.</div>
                    <div class="text-caption">
                      Версия и минимальная совместимая версия извлекаются из файла.<br>
                      Поддерживаемые форматы в файле:<br>
                      • <code>version: 1.0.0</code> или <code>version = "1.0.0"</code><br>
                      • <code># version: 1.0.0</code><br>
                      • <code>min_compatible_version: 1.0.0</code> или <code>min_compatible_version = "1.0.0"</code>
                    </div>
                  </v-alert>
                </v-col>
              </v-row>
            </v-form>
          </v-window-item>
        </v-window>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn variant="text" @click="close" :disabled="saving">
          Закрыть
        </v-btn>
        <v-btn
          v-if="currentTab === 'add'"
          color="primary"
          @click="saveVersion"
          :loading="saving"
          :disabled="!versionFileInput || versionFileInput.length === 0"
        >
          Загрузить версию
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
const versionForm = ref(null)
const saving = ref(false)
const loading = ref(false)
const currentTab = ref('versions')
const instances = ref([])
const versionFileInput = ref(null)

const dialog = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const versionData = ref({})

watch(() => props.modelValue, (newVal) => {
  if (newVal && props.module) {
    loadInstances()
  } else {
    resetVersionData()
  }
})

const resetVersionData = () => {
  versionData.value = {}
  versionFileInput.value = null
  currentTab.value = 'versions'
}

const loadInstances = async () => {
  loading.value = true
  try {
    const response = await secureFetch('/api/automation/instances')
    if (response.ok) {
      const data = await response.json()
      instances.value = data.instances || []
    }
  } catch (err) {
    console.error('Error loading instances:', err)
  } finally {
    loading.value = false
  }
}

const getVersionUsage = (version) => {
  if (!props.module) return []
  return (instances.value || [])
    .filter(inst => inst.module_id === props.module.id && inst.module_version === version)
    .map(inst => ({
      instance_id: inst.id,
      instance_name: inst.name
    }))
}

const setCurrentVersion = async (version) => {
  try {
    const response = await secureFetch(`/api/automation/modules/${props.module.id}/current-version?version=${encodeURIComponent(version)}`, {
      method: 'PUT'
    })

    if (response.ok) {
      messageStore.showSuccess('Версия по умолчанию установлена')
      emit('saved')
    } else {
      messageStore.showError('Ошибка установки версии')
    }
  } catch (err) {
    console.error('Error setting current version:', err)
    messageStore.showError('Ошибка установки версии')
  }
}

const saveVersion = async () => {
  if (!versionForm.value) return
  
  const { valid } = await versionForm.value.validate()
  if (!valid) return

  if (!versionFileInput.value || versionFileInput.value.length === 0) {
    messageStore.showError('Выберите файл версии')
    return
  }

  saving.value = true

  try {
    const formData = new FormData()
    formData.append('file', versionFileInput.value[0])
    
    const apiUrl = getApiUrl(`/api/automation/modules/${props.module.id}/versions`)
    const token = localStorage.getItem('ha_token') || localStorage.getItem('access_token')
    const headers = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: headers,
      body: formData
    })

    if (response.ok) {
      const data = await response.json()
      messageStore.showSuccess(`Версия ${data.version.version} добавлена`)
      emit('saved')
      resetVersionData()
      currentTab.value = 'versions'
    } else {
      const errorData = await response.json()
      messageStore.showError(errorData.detail || 'Ошибка загрузки версии')
    }
  } catch (err) {
    console.error('Error saving version:', err)
    messageStore.showError('Ошибка загрузки версии')
  } finally {
    saving.value = false
  }
}

const viewVersionFile = async (version) => {
  try {
    // Используем file_path из версии, если есть, иначе используем ID модуля
    const fileIdentifier = version.file_path?.replace(/\.py$/, '') || props.module.id
    const response = await secureFetch(`/api/automation/modules/${fileIdentifier}/content`)
    if (response.ok) {
      const data = await response.json()
      const newWindow = window.open('', '_blank')
      newWindow.document.write(`
        <html>
          <head>
            <title>${data.filename}</title>
            <style>
              body { font-family: monospace; padding: 20px; background: #1e1e1e; color: #d4d4d4; }
              pre { margin: 0; }
            </style>
          </head>
          <body>
            <h3>${data.filename} (v${version.version})</h3>
            <pre>${data.content.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
          </body>
        </html>
      `)
      newWindow.document.close()
    } else {
      messageStore.showError('Ошибка загрузки файла версии')
    }
  } catch (err) {
    console.error('Error viewing version file:', err)
    messageStore.showError('Ошибка загрузки файла версии')
  }
}

const downloadVersionFile = async (version) => {
  try {
    // Используем file_path из версии, если есть, иначе используем ID модуля
    const fileIdentifier = version.file_path?.replace(/\.py$/, '') || props.module.id
    const apiUrl = getApiUrl(`/api/automation/modules/${fileIdentifier}/download`)
    const token = localStorage.getItem('ha_token') || localStorage.getItem('access_token')
    
    // Используем secureFetch для получения файла с авторизацией
    const response = await secureFetch(apiUrl)
    
    if (response.ok) {
      // Получаем blob из ответа
      const blob = await response.blob()
      // Создаем URL для blob
      const blobUrl = window.URL.createObjectURL(blob)
      // Создаем временную ссылку для скачивания
      const link = document.createElement('a')
      link.href = blobUrl
      link.download = version.file_path || `version-${version.version}.py`
      document.body.appendChild(link)
      link.click()
      // Удаляем ссылку и освобождаем память
      document.body.removeChild(link)
      window.URL.revokeObjectURL(blobUrl)
      messageStore.showSuccess('Файл скачан')
    } else {
      messageStore.showError('Ошибка скачивания файла')
    }
  } catch (err) {
    console.error('Error downloading version file:', err)
    messageStore.showError('Ошибка скачивания файла')
  }
}

const deleteVersion = async (version) => {
  if (getVersionUsage(version.version).length > 0) {
    messageStore.showError('Версия используется и не может быть удалена')
    return
  }
  
  if (!confirm(`Удалить версию "${version.version}"?`)) return

  try {
    const response = await secureFetch(`/api/automation/modules/${props.module.id}/versions/${version.version}`, {
      method: 'DELETE'
    })

    if (response.ok) {
      messageStore.showSuccess('Версия удалена')
      emit('saved')
    } else {
      const errorData = await response.json()
      messageStore.showError(errorData.detail || 'Ошибка удаления версии')
    }
  } catch (err) {
    console.error('Error deleting version:', err)
    messageStore.showError('Ошибка удаления версии')
  }
}

const close = () => {
  dialog.value = false
  resetVersionData()
}
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>

