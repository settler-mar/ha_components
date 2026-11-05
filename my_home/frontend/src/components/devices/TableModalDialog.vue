<template>
  <v-dialog v-model="visible" :width="isMyHomeDevicesTable ? '95vw' : undefined" max-width="1800">
    <v-card>
      <v-card-title>
        {{ action?.name }}
        <v-btn @click="loadData" :loading="loading" density="compact" icon="mdi-refresh"/>
      </v-card-title>
      <v-card-text>
        <v-progress-linear
          v-if="loading"
          color="deep-purple-accent-4"
          height="6"
          indeterminate
          rounded
        />
        <div v-if="action?.description" class="mb-2">
          {{ action.description }}
        </div>

        <v-data-table
          :headers="displayHeaders"
          :items="displayRows"
          item-value="id"
          :density="isMyHomeDevicesTable ? 'compact' : 'default'"
          class="elevation-1 compact-device-table"
        >
          <template #item.actions="{ item }">
            <div class="d-flex align-center ga-2">
              <v-chip
                v-if="isMyHomeDevicesTable && isAdded(item)"
                size="small"
                color="success"
                variant="tonal"
                prepend-icon="mdi-check"
              >
                Добавлено
              </v-chip>
              <ActionHandler
                v-if="rowActions(item).length"
                :actions="rowActions(item)"
                :params="actionParams(item)"
                @executed="handleActionExecuted(item, $event)"/>
            </div>
          </template>
          <template v-if="isMyHomeDevicesTable" #item.device="{ item }">
            <div class="two-line-cell"><strong>{{ cell(item, 'name') }}</strong><span>{{ cell(item, 'mac') }}</span></div>
          </template>
          <template v-if="isMyHomeDevicesTable" #item.firmware="{ item }">
            <div class="two-line-cell"><strong>{{ cell(item, 'version') }}</strong><span>{{ cell(item, 'flash_date') }}</span></div>
          </template>
          <template v-if="isMyHomeDevicesTable" #item.chip="{ item }">
            <div class="two-line-cell"><strong>{{ cell(item, 'chip_id') }}</strong><span>тип {{ cell(item, 'flash_chip_revision') }}</span></div>
          </template>
          <template v-if="isMyHomeDevicesTable" #item.config="{ item }">
            <div class="two-line-cell"><strong>{{ cell(item, 'config_name') }}</strong><span>{{ cell(item, 'fs_name') }}</span></div>
          </template>
          <template v-if="isMyHomeDevicesTable" #item.hardware="{ item }">
            <div class="two-line-cell"><strong>{{ cell(item, 'flash_chip_speed') }}</strong><span>{{ cell(item, 'flash_heap') }}</span></div>
          </template>
          <template v-if="isMyHomeDevicesTable" #item.network="{ item }">
            <div class="two-line-cell"><strong>{{ cell(item, 'ssid') }}</strong><span>RSSI {{ cell(item, 'rssi') }}</span></div>
          </template>
        </v-data-table>
      </v-card-text>
      <v-card-actions>
        <v-spacer/>
        <v-btn text @click="visible = false">Закрыть</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import {ref, watch, computed} from 'vue'
import {secureFetch} from '@/services/fetch'
import useMessageStore from '@/store/messages'
import {useTableStore} from '@/store/tables'
import ActionHandler from '@/components/devices/ActionHandler.vue'

const props = defineProps({
  action: Object,
  params: Object
})

const emit = defineEmits(['executed', 'close'])
const visible = ref(true)
const loading = ref(false)
const rows = ref([])
const headers = ref([])
const addedKeys = ref(new Set())
const messageStore = useMessageStore()
const tableStore = useTableStore()

const isMyHomeDevicesTable = computed(() => props.action?.id === 'myhome-devices')

const displayHeaders = computed(() => {
  if (!isMyHomeDevicesTable.value) return headers.value
  return [
    {title: 'IP адрес', key: 'ip'},
    {title: 'Устройство', key: 'device'},
    {title: 'Прошивка', key: 'firmware'},
    {title: 'Chip', key: 'chip'},
    {title: 'Конфигурация', key: 'config'},
    {title: 'Память / скорость', key: 'hardware'},
    {title: 'Сеть', key: 'network'},
    {title: 'Время работы', key: 'run_time'},
    {title: 'Действия', key: 'actions', sortable: false},
  ]
})

const displayRows = computed(() => {
  if (!isMyHomeDevicesTable.value) return rows.value
  return rows.value.map(row => ({...row, device: row.name, firmware: row.version}))
})

function actionParams(item) {
  const row = item?.raw || item
  return {...props.params, ...row}
}

function rowKey(item) {
  const row = item?.raw || item
  return row?.ip || row?.chip_id || row?.mac
}

function isAdded(item) {
  return addedKeys.value.has(rowKey(item))
}

function rowActions(item) {
  if (!isMyHomeDevicesTable.value || !isAdded(item)) return props.action?.actions || []
  return (props.action?.actions || []).filter(action => action.name !== 'Добавить')
}

function handleActionExecuted(item, event) {
  if (event?.action?.name === 'Добавить') {
    const key = rowKey(item)
    if (key) addedKeys.value = new Set([...addedKeys.value, key])
  }
  emit('executed', event)
}

function cell(item, key) {
  return (item?.raw || item)?.[key] ?? '—'
}

watch(visible, (val) => {
  if (!val) emit('close')
})

loadData()

async function loadData() {
  loading.value = true
  try {
    const url = props.action.endpoint.replace(/\{(\w+?)\}/g, (_, k) => props.params[k] ?? '')
    const res = await secureFetch(url)
    rows.value = await res.json()
    if (isMyHomeDevicesTable.value) await loadAddedDevices()
    headers.value = (props.action.structure || []).map(s => ({title: s.title, key: s.name}))
    if (!headers.value.some(h => h.key === 'actions')) {
      headers.value.push({title: 'Действия', key: 'actions'})
    }
  } catch (e) {
    console.warn('TableModal load error', e)
    messageStore.addMessage({type: 'error', text: 'Не удалось загрузить таблицу'})
    visible.value = false
  } finally {
    loading.value = false
  }
}

async function loadAddedDevices() {
  try {
    const response = await secureFetch('/api/devices/')
    const devices = await response.json()
    const keys = new Set()
    for (const device of devices || []) {
      const ip = device?.params?.ip || device?.ip
      if (ip) keys.add(ip)
      if (device?.code) keys.add(device.code)
    }
    addedKeys.value = keys
  } catch (e) {
    console.warn('Could not load added devices:', e)
  }
}
</script>

<style scoped>
.compact-device-table :deep(th),
.compact-device-table :deep(td) {
  white-space: nowrap;
  padding: 6px 10px;
}

.two-line-cell {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.two-line-cell span {
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.78rem;
}
</style>
