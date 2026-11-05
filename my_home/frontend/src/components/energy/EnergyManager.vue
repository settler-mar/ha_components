<template>
  <div class="energy-manager">
    <v-row>
      <!-- Основная панель управления -->
      <v-col cols="12" md="8">
        <v-card class="mb-4">
          <v-card-title class="d-flex align-center justify-space-between">
            <div class="d-flex align-center">
              <v-icon class="me-2">mdi-lightning-bolt-circle</v-icon>
              Мониторинг энергии
            </div>
            <v-btn
              color="primary"
              prepend-icon="mdi-plus"
              @click="openAddSourceDialog"
            >
              Добавить источник
            </v-btn>
          </v-card-title>

          <v-card-text>
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

            <!-- Статистика -->
            <EnergyStats
              :sources="sources"
              :output="output"
              class="mb-4"
            />

            <!-- Список источников -->
            <div v-if="!loading && sources.length === 0" class="text-center text-grey py-8">
              <v-icon size="64" class="mb-4">mdi-lightning-bolt-outline</v-icon>
              <p>Нет источников энергии</p>
              <p class="text-caption">Добавьте первый источник для начала мониторинга</p>
            </div>

            <EnergySourceCard
              v-for="source in sources"
              :key="source.id"
              :source="source"
              @edit="editSource"
              @delete="deleteSource"
              class="mb-2"
            />
          </v-card-text>
        </v-card>

        <!-- Настройки выхода -->
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon class="me-2">mdi-transmission-tower</v-icon>
            Настройки выхода
          </v-card-title>
          <v-card-text>
            <EnergyOutputConfig
              v-model="output"
              :sources="sources"
            />
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Боковая панель с информацией -->
      <v-col cols="12" md="4">
        <EnergyInfoPanel
          :sources="sources"
          :output="output"
        />
      </v-col>
    </v-row>

    <!-- Диалог добавления/редактирования источника -->
    <EnergySourceDialog
      v-model:show="sourceDialog"
      :source="selectedSource"
      @saved="handleSourceSaved"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { secureFetch } from '@/services/fetch'
import useMessageStore from '@/store/messages'
import EnergyStats from './EnergyStats.vue'
import EnergySourceCard from './EnergySourceCard.vue'
import EnergySourceDialog from './EnergySourceDialog.vue'
import EnergyOutputConfig from './EnergyOutputConfig.vue'
import EnergyInfoPanel from './EnergyInfoPanel.vue'

const messageStore = useMessageStore()

const loading = ref(false)
const error = ref(null)
const sources = ref([])
const output = ref({
  calculation_mode: 'sum', // sum, max, min
  priority_logic: 'priority', // priority, power
  selected_source_id: null
})
const sourceDialog = ref(false)
const selectedSource = ref(null)

const loadData = async () => {
  loading.value = true
  error.value = null

  try {
    const [sourcesResponse, outputResponse] = await Promise.all([
      secureFetch('/api/energy/sources'),
      secureFetch('/api/energy/output')
    ])

    if (sourcesResponse.ok) {
      const sourcesData = await sourcesResponse.json()
      sources.value = sourcesData.sources || []
    }

    if (outputResponse.ok) {
      const outputData = await outputResponse.json()
      output.value = outputData.output || output.value
    }
  } catch (err) {
    console.error('Error loading energy data:', err)
    error.value = 'Ошибка загрузки данных'
  } finally {
    loading.value = false
  }
}

const openAddSourceDialog = () => {
  selectedSource.value = null
  sourceDialog.value = true
}

const editSource = (source) => {
  selectedSource.value = source
  sourceDialog.value = true
}

const deleteSource = async (source) => {
  if (!confirm(`Удалить источник "${source.name}"?`)) return

  try {
    const response = await secureFetch(`/api/energy/sources/${source.id}`, {
      method: 'DELETE'
    })

    if (response.ok) {
      messageStore.showSuccess('Источник удален')
      await loadData()
    } else {
      messageStore.showError('Ошибка удаления источника')
    }
  } catch (err) {
    console.error('Error deleting source:', err)
    messageStore.showError('Ошибка удаления источника')
  }
}

const handleSourceSaved = () => {
  loadData()
}

const saveOutput = async () => {
  try {
    const response = await secureFetch('/api/energy/output', {
      method: 'PUT',
      body: JSON.stringify(output.value)
    })

    if (response.ok) {
      messageStore.showSuccess('Настройки выхода сохранены')
    } else {
      messageStore.showError('Ошибка сохранения настроек выхода')
    }
  } catch (err) {
    console.error('Error saving output:', err)
    messageStore.showError('Ошибка сохранения настроек выхода')
  }
}

watch(() => output.value, () => {
  saveOutput()
}, { deep: true })

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.energy-manager {
  padding: 16px 0;
}
</style>

