<template>
  <div class="module-manager">
    <div class="d-flex align-center justify-space-between mb-4">
      <h2 class="text-h6">Модули автоматизации</h2>
      <v-btn
        color="primary"
        prepend-icon="mdi-plus"
        @click="openAddModuleDialog"
      >
        Добавить модуль
      </v-btn>
    </div>

    <v-progress-linear
      v-if="loading"
      color="primary"
      height="4"
      indeterminate
      rounded
      class="mb-4"
    />

    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      class="mb-4"
    >
      {{ error }}
    </v-alert>

    <div v-if="!loading && modules.length === 0" class="text-center text-grey py-8">
      <v-icon size="64" class="mb-4">mdi-folder-outline</v-icon>
      <p>Нет модулей автоматизации</p>
      <p class="text-caption">Создайте первый модуль для начала работы</p>
    </div>

    <v-row v-else>
      <v-col
        cols="12"
        sm="6"
        md="4"
        lg="3"
        v-for="module in modules"
        :key="module.id"
      >
        <ModuleCard
          :module="module"
          @delete="deleteModule"
          @version="manageVersions"
        />
      </v-col>
    </v-row>

    <!-- Диалог добавления/редактирования модуля -->
    <ModuleDialog
      v-model="moduleDialog"
      :module="selectedModule"
      @saved="handleModuleSaved"
    />

    <!-- Диалог управления версиями -->
    <ModuleVersionDialog
      v-model="versionDialog"
      :module="selectedModuleForVersion"
      @saved="handleModuleSaved"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { secureFetch } from '@/services/fetch'
import useMessageStore from '@/store/messages'
import ModuleCard from './ModuleCard.vue'
import ModuleDialog from './ModuleDialog.vue'
import ModuleVersionDialog from './ModuleVersionDialog.vue'

const messageStore = useMessageStore()

const loading = ref(false)
const error = ref(null)
const modules = ref([])
const moduleDialog = ref(false)
const versionDialog = ref(false)
const selectedModule = ref(null)
const selectedModuleForVersion = ref(null)

const loadModules = async () => {
  loading.value = true
  error.value = null

  try {
    const response = await secureFetch('/api/automation/modules')
    if (response.ok) {
      const data = await response.json()
      modules.value = data.modules || []
    } else {
      error.value = 'Ошибка загрузки модулей'
    }
  } catch (err) {
    console.error('Error loading modules:', err)
    error.value = 'Ошибка загрузки модулей'
  } finally {
    loading.value = false
  }
}

const openAddModuleDialog = () => {
  selectedModule.value = null
  moduleDialog.value = true
}

const manageVersions = (module) => {
  selectedModuleForVersion.value = module
  versionDialog.value = true
}

const deleteModule = async (module) => {
  if (!confirm(`Удалить модуль "${module.name}"?`)) return

  try {
    const response = await secureFetch(`/api/automation/modules/${module.id}`, {
      method: 'DELETE'
    })

    if (response.ok) {
      messageStore.showSuccess('Модуль удален')
      await loadModules()
    } else {
      const errorData = await response.json()
      messageStore.showError(errorData.detail || 'Ошибка удаления модуля')
    }
  } catch (err) {
    console.error('Error deleting module:', err)
    messageStore.showError('Ошибка удаления модуля')
  }
}

const handleModuleSaved = () => {
  loadModules()
}

onMounted(() => {
  loadModules()
})
</script>

<style scoped>
.module-manager {
  padding: 16px 0;
}
</style>

