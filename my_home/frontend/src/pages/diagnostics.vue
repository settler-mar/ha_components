<template>
  <v-container fluid class="diagnostics-page">
    <div class="d-flex align-center mb-4 flex-wrap ga-3">
      <div>
        <h1 class="text-h5">Диагностика</h1>
        <div class="text-caption text-medium-emphasis">События системы, падения и потери соединения</div>
      </div>
      <v-spacer />
      <v-select v-model="deviceFilter" :items="deviceOptions" label="Плата" density="compact" hide-details class="filter" clearable />
      <v-select v-model="filter" :items="filters" label="Фильтр по типу" density="compact" hide-details class="filter" />
      <v-btn prepend-icon="mdi-refresh" :loading="loading" @click="loadEvents">Обновить</v-btn>
    </div>

    <v-row dense class="mb-4">
      <v-col v-for="stat in stats" :key="stat.key" cols="6" sm="4" md="2">
        <v-card variant="tonal" :color="stat.color" class="stat-card" @click="applyStatFilter(stat.key)">
          <div class="stat-value">{{ stat.value }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="mb-4" variant="outlined">
      <div class="d-flex align-center justify-space-between px-4 pt-3 flex-wrap ga-2">
        <div class="text-subtitle-2">Динамика событий</div>
        <div class="d-flex align-center ga-2 flex-wrap">
          <v-btn-toggle v-model="timelineGroup" mandatory density="compact" color="primary" variant="outlined">
            <v-btn size="small" value="device" prepend-icon="mdi-developer-board">По платам</v-btn>
            <v-btn size="small" value="type" prepend-icon="mdi-shape-outline">По типам</v-btn>
          </v-btn-toggle>
          <v-btn-toggle v-model="timelineMode" mandatory density="compact" color="primary" variant="outlined">
            <v-btn size="small" value="hour" prepend-icon="mdi-clock-outline">24 часа</v-btn>
            <v-btn size="small" value="day" prepend-icon="mdi-calendar-outline">14 дней</v-btn>
          </v-btn-toggle>
        </div>
      </div>
      <div class="timeline-chart px-3 pb-3">
        <LineChart
          v-if="timeline.labels.length && timeline.series.length"
          :data="timeline.data"
          :x-labels="timeline.labels"
          :label="timeline.series"
          type="bar"
          :show-points="false"
          stacked
        />
        <div v-else class="text-medium-emphasis text-center py-6">Нет данных для построения</div>
      </div>
    </v-card>

    <v-alert v-if="error" type="warning" variant="tonal" class="mb-4">{{ error }}</v-alert>

    <v-card>
      <v-table density="comfortable" hover>
        <thead>
          <tr><th>Время</th><th>Тип</th><th>Устройство</th><th>Событие</th><th>Причина</th><th>Детали</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-if="!loading && !filteredEvents.length"><td colspan="7" class="text-center py-8 text-medium-emphasis">
            {{ events.length ? 'Нет событий по выбранным фильтрам' : 'Событий пока нет' }}
          </td></tr>
          <tr v-for="event in filteredEvents" :key="event.timestamp + event.message + JSON.stringify(event.details)">
            <td class="nowrap">{{ formatDate(event.timestamp) }}</td>
            <td><v-chip size="small" :color="typeColor(event.type)">{{ typeLabel(event.type) }}</v-chip></td>
            <td>{{ event.device_name || (event.device_id ? `#${event.device_id}` : 'Система') }}</td>
            <td>{{ event.message }}</td>
            <td>{{ event.reason || '—' }}</td>
            <td class="details">
              <a v-if="event.type === 'coredump_collected' && event.details?.filename"
                 :href="dumpUrl(event.device_id, event.details.filename)" download>
                <v-icon size="small">mdi-download</v-icon> {{ event.details.filename }} ({{ formatBytes(event.details.size) }})
              </a>
              <div v-else-if="event.details?.uploaded_files?.length" class="replaced-files">
                <a v-for="file in event.details.uploaded_files" :key="file"
                   :href="configBackupUrl(event.device_id, event.details.backup, file)" download>
                  <v-icon size="small">mdi-file-download-outline</v-icon> {{ file }}
                </a>
              </div>
              <span v-else>{{ detailText(event.details) }}</span>
            </td>
            <td>
              <v-btn v-if="canRollback(event)" size="small" color="warning" variant="tonal"
                     :loading="rollbackLoading === event.timestamp + event.message"
                     @click="rollback(event)">
                Откатить
              </v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
  </v-container>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getApiUrl, secureFetch } from '@/services/fetch'
import LineChart from '@/components/LineChart.vue'

const events = ref([])
const loading = ref(false)
const error = ref('')
const rollbackLoading = ref('')
const filter = ref('all')
const deviceFilter = ref(null)
const timelineMode = ref('hour')
const timelineGroup = ref('device')
const filters = [
  { title: 'Все события', value: 'all' },
  { title: 'Падения', value: 'crash_detected' },
  { title: 'Потери соединения', value: 'connection_loss' },
  { title: 'Coredump', value: 'coredump_collected' },
  { title: 'Ошибки скачивания', value: 'coredump_failed' },
]
let timer

const loadEvents = async () => {
  loading.value = true
  error.value = ''
  try {
    const query = filter.value === 'all' ? '' : `?event_type=${encodeURIComponent(filter.value)}`
    const response = await secureFetch(`/api/diagnostics/events${query}`)
    events.value = (await response.json()).events || []
  } catch (e) {
    error.value = 'Не удалось загрузить журнал диагностики'
  } finally {
    loading.value = false
  }
}

const canRollback = event => Boolean(event.device_id && event.details?.backup &&
  ['configuration_restored', 'configuration_restore_failed', 'configuration_changed', 'configuration_lost'].includes(event.type))
const configBackupUrl = (deviceId, backup, file) =>
  getApiUrl(`/api/diagnostics/config-backup/${deviceId}/${encodeURIComponent(backup)}/${file.split('/').map(encodeURIComponent).join('/')}`)

const rollback = async (event) => {
  if (!window.confirm(`Откатить конфигурацию устройства к версии ${event.details.backup}?`)) return
  const key = event.timestamp + event.message
  rollbackLoading.value = key
  try {
    await secureFetch('/api/diagnostics/rollback', {
      method: 'POST',
      data: {device_id: event.device_id, backup: event.details.backup},
    })
    await loadEvents()
  } catch (e) {
    error.value = 'Не удалось выполнить откат конфигурации'
  } finally {
    rollbackLoading.value = ''
  }
}

const deviceKey = event => event.device_id != null ? String(event.device_id) : '__system__'
const deviceLabel = event => event.device_name || (event.device_id != null ? `#${event.device_id}` : 'Система')

const deviceOptions = computed(() => {
  const map = new Map()
  for (const e of events.value) {
    const k = deviceKey(e)
    if (!map.has(k)) map.set(k, deviceLabel(e))
  }
  return [...map.entries()]
    .map(([value, title]) => ({ value, title }))
    .sort((a, b) => a.title.localeCompare(b.title, 'ru'))
})

const filteredEvents = computed(() => events.value.filter(e => {
  if (deviceFilter.value && deviceKey(e) !== deviceFilter.value) return false
  return true
}))

const stats = computed(() => {
  const list = filteredEvents.value
  const by = type => list.filter(e => e.type === type).length
  const devices = new Set(list.map(deviceKey)).size
  return [
    { key: '__all__', label: 'Всего событий', value: list.length, color: 'primary' },
    { key: '__devices__', label: 'Устройств', value: devices, color: 'info' },
    { key: 'crash_detected', label: 'Падения', value: by('crash_detected'), color: 'error' },
    { key: 'connection_loss', label: 'Потери связи', value: by('connection_loss'), color: 'warning' },
    { key: 'coredump_collected', label: 'Coredump', value: by('coredump_collected'), color: 'info' },
    { key: 'configuration_lost', label: 'Конфиг. потеря', value: by('configuration_lost') + by('configuration_partially_lost'), color: 'error' },
  ]
})

const timeline = computed(() => {
  const now = new Date()
  const hour = timelineMode.value === 'hour'
  const count = hour ? 24 : 14
  const stepMs = hour ? 3600_000 : 86_400_000

  const bucketStarts = []
  for (let i = count - 1; i >= 0; i--) {
    const d = new Date(now)
    if (hour) { d.setMinutes(0, 0, 0); d.setHours(d.getHours() - i) }
    else { d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - i) }
    bucketStarts.push(d.getTime())
  }
  const firstStart = bucketStarts[0]
  const lastEnd = bucketStarts[bucketStarts.length - 1] + stepMs

  const byDevice = timelineGroup.value === 'device'
  const seriesMap = new Map()

  for (const e of filteredEvents.value) {
    const t = e.timestamp ? new Date(e.timestamp).getTime() : NaN
    if (!Number.isFinite(t) || t < firstStart || t >= lastEnd) continue
    const idx = Math.floor((t - firstStart) / stepMs)
    const key = byDevice ? deviceKey(e) : (e.type || 'unknown')
    const label = byDevice ? deviceLabel(e) : typeLabel(e.type)
    if (!seriesMap.has(key)) seriesMap.set(key, { label, data: new Array(count).fill(0) })
    seriesMap.get(key).data[idx]++
  }

  const sorted = [...seriesMap.values()].sort((a, b) =>
    b.data.reduce((s, v) => s + v, 0) - a.data.reduce((s, v) => s + v, 0))

  const labels = bucketStarts.map(start => {
    const d = new Date(start)
    if (hour) return `${String(d.getHours()).padStart(2, '0')}:00`
    return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}`
  })

  return {
    labels,
    data: sorted.length ? sorted.map(s => s.data) : [],
    series: sorted.map(s => s.label),
  }
})

const applyStatFilter = key => {
  if (key === '__all__' || key === '__devices__') {
    filter.value = 'all'
    return
  }
  filter.value = filters.some(f => f.value === key) ? key : 'all'
}

watch(filter, loadEvents)
onMounted(() => { loadEvents(); timer = setInterval(loadEvents, 10000) })
onUnmounted(() => clearInterval(timer))

const typeLabel = type => ({ connection: 'Связь', connection_loss: 'Потеря связи', crash_detected: 'Падение', coredump_collected: 'Coredump', coredump_failed: 'Coredump: ошибка', configuration_lost: 'Конфигурация потеряна', configuration_partially_lost: 'Конфигурация повреждена', configuration_changed: 'Конфигурация изменена', configuration_restored: 'Конфигурация восстановлена', configuration_restore_failed: 'Восстановление не удалось', configuration_unknown: 'Конфигурация: неизвестно', configuration_recovery_restart: 'Перезагрузка' }[type] || type)
const typeColor = type => ({ connection: 'success', connection_loss: 'warning', crash_detected: 'error', coredump_collected: 'info', coredump_failed: 'warning', configuration_lost: 'error', configuration_partially_lost: 'warning', configuration_changed: 'info', configuration_restored: 'success', configuration_restore_failed: 'error', configuration_unknown: 'warning', configuration_recovery_restart: 'info' }[type] || 'default')
const formatDate = value => value ? new Date(value).toLocaleString() : '—'
const formatBytes = value => !value ? '0 Б' : `${(value / 1024).toFixed(value > 1024 ? 1 : 0)} КБ`
const detailText = details => details ? Object.entries(details).filter(([key]) => key !== 'url').map(([key, value]) => `${key}: ${value}`).join('; ') : '—'
const dumpUrl = (deviceId, filename) => getApiUrl(`/api/diagnostics/coredumps/${deviceId}/${encodeURIComponent(filename)}`)
</script>

<style scoped>
.filter { max-width: 240px; min-width: 180px; }
.stat-card { padding: 12px 14px; cursor: pointer; transition: transform 0.1s, filter 0.1s; }
.stat-card:hover { transform: translateY(-1px); filter: brightness(1.05); }
.stat-value { font-size: 22px; font-weight: 700; line-height: 1.1; }
.stat-label { font-size: 12px; opacity: 0.85; margin-top: 2px; }
.timeline-chart { min-height: 220px; }
.timeline-chart :deep(> div) { height: 220px; }
.nowrap { white-space: nowrap; }
.details { max-width: 360px; font-size: 0.85rem; }
.replaced-files { display: flex; flex-direction: column; gap: 4px; }
</style>
