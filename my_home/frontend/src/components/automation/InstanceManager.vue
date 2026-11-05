<template>
  <div class="instance-manager">
    <div class="d-flex align-center justify-space-between mb-4">
      <h2 class="text-h6">Автоматизации</h2>
      <v-btn
        color="primary"
        prepend-icon="mdi-plus"
        @click="openAddInstanceDialog"
      >
        Добавить автоматизацию
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

    <div v-if="!loading && instances.length === 0" class="text-center text-grey py-8">
      <v-icon size="64" class="mb-4">mdi-play-circle-outline</v-icon>
      <p>Нет автоматизаций</p>
      <p class="text-caption">Создайте первую автоматизацию на основе модуля</p>
    </div>

    <v-row v-else>
      <v-col
        cols="12"
        sm="6"
        md="4"
        lg="3"
        v-for="instance in instances"
        :key="instance.id"
      >
        <InstanceCard
          :instance="instance"
          :modules="modules"
          @edit="editInstance"
          @delete="deleteInstance"
        />
      </v-col>
    </v-row>

    <!-- Диалог добавления/редактирования автоматизации -->
    <InstanceDialog
      v-model="instanceDialog"
      :instance="selectedInstance"
      :modules="modules"
      @saved="handleInstanceSaved"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { secureFetch } from '@/services/fetch'
import useMessageStore from '@/store/messages'
import InstanceCard from './InstanceCard.vue'
import InstanceDialog from './InstanceDialog.vue'

const messageStore = useMessageStore()

const loading = ref(false)
const error = ref(null)
const instances = ref([])
const modules = ref([])
const instanceDialog = ref(false)
const selectedInstance = ref(null)

const loadInstances = async () => {
  loading.value = true
  error.value = null

  try {
    const response = await secureFetch('/api/automation/instances')
    if (response.ok) {
      const data = await response.json()
      instances.value = data.instances || []
    } else {
      error.value = 'Ошибка загрузки автоматизаций'
    }
  } catch (err) {
    console.error('Error loading instances:', err)
    error.value = 'Ошибка загрузки автоматизаций'
  } finally {
    loading.value = false
  }
}

const loadModules = async () => {
  try {
    const response = await secureFetch('/api/automation/modules')
    if (response.ok) {
      const data = await response.json()
      modules.value = data.modules || []
    }
  } catch (err) {
    console.error('Error loading modules:', err)
  }
}

const openAddInstanceDialog = () => {
  selectedInstance.value = null
  instanceDialog.value = true
}

const editInstance = (instance) => {
  selectedInstance.value = instance
  instanceDialog.value = true
}

const deleteInstance = async (instance) => {
  if (!confirm(`Удалить автоматизацию "${instance.name}"?`)) return

  try {
    const response = await secureFetch(`/api/automation/instances/${instance.id}`, {
      method: 'DELETE'
    })

    if (response.ok) {
      messageStore.showSuccess('Автоматизация удалена')
      await loadInstances()
    } else {
      messageStore.showError('Ошибка удаления автоматизации')
    }
  } catch (err) {
    console.error('Error deleting instance:', err)
    messageStore.showError('Ошибка удаления автоматизации')
  }
}

const handleInstanceSaved = () => {
  loadInstances()
}

onMounted(async () => {
  await Promise.all([loadInstances(), loadModules()])
})
</script>

<style scoped>
.instance-manager {
  padding: 16px 0;
}
</style>


