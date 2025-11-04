<template>
  <div class="mb-4">
    <h3 class="text-h6 mb-2">Управление логами</h3>
    <div class="d-flex align-center mb-3">
      <v-chip size="small" :color="logsStatusColor" variant="tonal" class="me-2">
        {{ logsStatusText }}
      </v-chip>
      <v-spacer></v-spacer>
      <v-btn size="small" @click="$emit('trigger-logs-export')" :loading="logsLoading">
        <v-icon size="16" class="me-1">mdi-file-export</v-icon>
        Экспорт логов
      </v-btn>
    </div>
    
    <!-- Список физических файлов логов -->
    <v-card variant="outlined">
      <v-card-title class="text-subtitle-1">Физические файлы логов</v-card-title>
      <v-card-text>
        <v-btn size="small" @click="$emit('refresh-log-files')" :loading="loadingFiles" class="mb-2">
          <v-icon size="16" class="me-1">mdi-refresh</v-icon>
          Обновить список
        </v-btn>
        <div v-if="logFiles.length">
          <div v-for="file in logFiles" :key="file.name" class="log-file-entry d-flex align-center justify-space-between py-2">
            <div class="d-flex align-center">
              <v-icon size="16" class="me-2">mdi-file-document</v-icon>
              <span>{{ file.name }}</span>
              <v-chip size="x-small" variant="tonal" class="ms-2">
                {{ file.size }}
              </v-chip>
            </div>
            <div>
              <v-btn size="x-small" variant="outlined" @click="$emit('download-log-file', file)" class="me-1">
                <v-icon size="12">mdi-download</v-icon>
              </v-btn>
              <v-btn size="x-small" variant="outlined" @click="$emit('view-log-file', file)">
                <v-icon size="12">mdi-eye</v-icon>
              </v-btn>
            </div>
          </div>
        </div>
        <div v-else class="text-grey">
          Файлы логов не найдены
        </div>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
const props = defineProps({
  deviceId: {
    type: Number,
    required: true
  },
  logsLoading: {
    type: Boolean,
    default: false
  },
  loadingFiles: {
    type: Boolean,
    default: false
  },
  logsStatusColor: {
    type: String,
    default: 'grey'
  },
  logsStatusText: {
    type: String,
    default: ''
  },
  logFiles: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits([
  'trigger-logs-export',
  'refresh-log-files',
  'download-log-file',
  'view-log-file',
  'notification'
])
</script>

<style scoped>
.log-file-entry {
  border-bottom: 1px solid #e0e0e0;
}

.log-file-entry:last-child {
  border-bottom: none;
}
</style>








