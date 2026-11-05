<template>
  <div class="virtual-ports-manager">
    <div class="d-flex align-center justify-space-between mb-4">
      <h2 class="text-h6">Виртуальные устройства и порты</h2>
      <v-btn
        color="primary"
        prepend-icon="mdi-plus"
        @click="openAddDialog"
      >
        Добавить порт
      </v-btn>
    </div>

    <v-card variant="outlined" class="mb-6">
      <v-card-title class="d-flex align-center">
        <v-icon class="me-2">mdi-home-automation</v-icon>
        Виртуальные устройства
        <v-spacer />
        <v-select v-model="selectedTag" :items="tags" label="Хештег" clearable density="compact" hide-details class="tag-filter me-3" />
        <v-btn color="secondary" prepend-icon="mdi-plus" @click="createDevice">Добавить устройство</v-btn>
      </v-card-title>
      <v-card-text>
        <v-alert v-if="!devices.length" type="info" variant="tonal">Виртуальных устройств пока нет.</v-alert>
        <v-row v-else>
          <v-col v-for="device in devices" :key="device.id" cols="12" md="6" lg="4">
            <v-card variant="tonal">
              <v-card-title class="device-card-title">
                <span class="device-card-name">{{ device.name }}</span>
                <div class="device-card-actions">
                  <v-btn icon="mdi-pencil" size="x-small" variant="text" title="Изменить устройство" @click="editDevice(device)" />
                  <v-btn icon="mdi-content-copy" size="x-small" variant="text" title="Копировать" @click="copyDevice(device)" />
                  <v-btn icon="mdi-cloud-upload" size="x-small" variant="text" title="Опубликовать в HA" @click="publishDevice(device)" />
                  <v-btn icon="mdi-delete" size="x-small" color="error" variant="text" title="Удалить" @click="deleteDevice(device)" />
                </div>
              </v-card-title>
              <v-card-text>
                <div v-if="sourceDevices(device).length === 1" class="text-caption text-grey mb-2">
                  Источник: {{ sourceDevices(device)[0].name }}
                </div>
                <v-btn size="small" variant="outlined" prepend-icon="mdi-plus" @click="openAddPort(device)">Добавить порт</v-btn>
                <v-chip v-for="tag in device.tags || []" :key="tag" :color="tagColor(tag)" variant="tonal" size="x-small" class="me-1 mb-1">#{{ stripTag(tag) }}</v-chip>
                <div class="text-caption mt-2">Портов: {{ (device.ports || []).length }}</div>
                <div class="virtual-port-list">
                <div v-for="port in device.ports || []" :key="port.id" class="virtual-port-row text-body-2 mt-1">
                  <span class="virtual-port-name">{{ port.name }} <span class="text-caption">({{ port.binding?.physical_code || 'без привязки' }})</span></span>
                  <v-chip
                    :color="valueColor(port)"
                    size="x-small"
                    variant="tonal"
                    class="virtual-port-value"
                    :title="`Текущее значение: ${displayValue(port)}`"
                  >
                    {{ displayValue(port) }}
                  </v-chip>
                  <span class="virtual-port-status" :title="availabilityLabel(port)">
                    <v-icon :color="availabilityColor(port)" size="17">{{ availabilityIcon(port) }}</v-icon>
                  </span>
                  <span v-if="sourceDevices(device).length > 1" class="virtual-port-source text-caption">
                    {{ port.source_device_name || 'Источник не найден' }}
                  </span>
                  <span class="virtual-port-type" :title="`Тип HA: ${port.type || 'sensor'}`">
                    <v-icon size="17">{{ portIcon(port) }}</v-icon>
                    <span class="text-caption">{{ port.type || 'sensor' }}</span>
                  </span>
                  <v-icon
                    size="17"
                    :color="bindingColor(port.binding_status)"
                    :title="bindingLabel(port.binding_status)"
                  >{{ bindingIcon(port.binding_status) }}</v-icon>
                  <v-icon
                    size="17"
                    :color="port.published_to_ha ? 'success' : 'grey'"
                    :title="port.published_to_ha ? 'Опубликован в Home Assistant' : 'Не опубликован в Home Assistant'"
                  >{{ port.published_to_ha ? 'mdi-home-assistant' : 'mdi-home-outline' }}</v-icon>
                  <v-menu location="bottom end">
                    <template #activator="{ props: menuProps }">
                      <v-btn v-bind="menuProps" icon="mdi-dots-vertical" size="x-small" variant="text" title="Действия" />
                    </template>
                    <v-list density="compact">
                      <v-list-item prepend-icon="mdi-pencil" title="Изменить" @click="editPort(port)" />
                      <v-list-item prepend-icon="mdi-content-copy" title="Копировать" @click="copyPort(device, port)" />
                      <v-list-item prepend-icon="mdi-arrow-right-bold" title="Перенести в другое устройство" @click="openMoveDialog(device, port)" />
                      <v-list-item prepend-icon="mdi-delete" title="Удалить" class="text-error" @click="deleteDevicePort(device, port)" />
                    </v-list>
                  </v-menu>
                </div>
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

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

    <div v-if="!loading && ports.length === 0" class="text-center text-grey py-8">
      <v-icon size="64" class="mb-4">mdi-network</v-icon>
      <p>Нет отдельных виртуальных портов</p>
      <p class="text-caption">Порты внутри виртуальных устройств отображаются в их карточках</p>
    </div>

    <v-row v-else>
      <v-col
        cols="12"
        sm="6"
        md="4"
        lg="3"
        v-for="port in ports"
        :key="port.id"
      >
        <VirtualPortCard
          :port="port"
          @edit="editPort"
          @delete="deletePort"
        />
      </v-col>
    </v-row>

    <!-- Диалог добавления/редактирования -->
    <VirtualPortDialog
      v-model="dialog"
      :port="selectedPort"
      :virtual-device-id="selectedVirtualDeviceId"
      @saved="handlePortSaved"
    />

    <v-dialog v-model="deviceDialog" max-width="520">
      <v-card>
        <v-card-title>{{ editingDeviceId ? 'Изменить виртуальное устройство' : 'Новое виртуальное устройство' }}</v-card-title>
        <v-card-text>
          <v-text-field v-model="deviceForm.name" label="Название" autofocus />
          <TagsInput v-model="deviceForm.tags" class="mt-2" />
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn variant="text" @click="deviceDialog = false">Отмена</v-btn><v-btn color="primary" @click="saveDevice">{{ editingDeviceId ? 'Сохранить' : 'Создать' }}</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="moveDialog" max-width="520">
      <v-card>
        <v-card-title>Перенести виртуальный порт</v-card-title>
        <v-card-text>
          <div class="text-body-2 mb-3">{{ movePortTarget?.name }}</div>
          <v-select
            v-model="moveTargetDeviceId"
            :items="moveTargetDevices"
            item-title="name"
            item-value="id"
            label="Целевое виртуальное устройство"
            variant="outlined"
            density="compact"
            hide-details
          />
          <v-alert type="warning" variant="tonal" density="compact" class="mt-3">
            Физическая привязка сохранится. После переноса публикацию в HA потребуется выполнить для нового устройства.
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="moveDialog = false">Отмена</v-btn>
          <v-btn color="primary" :disabled="!moveTargetDeviceId" @click="movePort">Перенести</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { secureFetch } from '@/services/fetch'
import useMessageStore from '@/store/messages'
import VirtualPortCard from './VirtualPortCard.vue'
import VirtualPortDialog from './VirtualPortDialog.vue'
import TagsInput from '@/components/form_elements/TagsInput.vue'
import { normalizeTag, stripTag, tagColor } from '@/utils/tags'

const messageStore = useMessageStore()

const loading = ref(false)
const error = ref(null)
const ports = ref([])
const dialog = ref(false)
const selectedPort = ref(null)
const selectedVirtualDeviceId = ref(null)
const devices = ref([])
const tags = ref([])
const selectedTag = ref(null)
const deviceDialog = ref(false)
const deviceForm = ref({ name: '', tags: [] })
const editingDeviceId = ref(null)
const moveDialog = ref(false)
const movePortTarget = ref(null)
const moveSourceDevice = ref(null)
const moveTargetDeviceId = ref(null)
const moveTargetDevices = computed(() => devices.value.filter(device => device.id !== moveSourceDevice.value?.id))

const sourceDevices = device => {
  const sources = new Map()
  for (const port of device.ports || []) {
    if (port.source_device_id == null) continue
    sources.set(String(port.source_device_id), {
      id: port.source_device_id,
      name: port.source_device_name || `Устройство #${port.source_device_id}`
    })
  }
  return [...sources.values()]
}

const formatValue = value => {
  if (value === undefined || value === null || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const rawValue = port => {
  const candidates = [port.current_value, port.value, port.val]
  for (const item of candidates) if (item !== undefined && item !== null && item !== '') return item
  return null
}

const displayValue = port => {
  const value = rawValue(port)
  if (value === null) return '—'
  if (typeof value === 'boolean') return value ? 'вкл' : 'выкл'
  if (value === 'true' || value === '1') return port.type === 'switch' || port.binding?.signature?.value_type === 'boolean' ? 'вкл' : String(value)
  if (value === 'false' || value === '0') return port.type === 'switch' || port.binding?.signature?.value_type === 'boolean' ? 'выкл' : String(value)
  const unit = port.unit_of_measurement
  const text = typeof value === 'object' ? JSON.stringify(value) : String(value)
  return unit ? `${text} ${unit}` : text
}

const valueColor = port => {
  const value = rawValue(port)
  if (value === null) return 'grey'
  if (value === true || value === 'true' || value === '1') return 'success'
  if (value === false || value === 'false' || value === '0') return 'grey'
  return 'primary'
}

const availabilityIcon = port => {
  if (port.availability?.state === 'unavailable' || port.binding_status === 'not_found') return 'mdi-alert-circle-outline'
  if (port.availability?.online === false) return 'mdi-lan-disconnect'
  return 'mdi-lan-connect'
}

const availabilityColor = port => {
  if (port.availability?.state === 'unavailable' || port.binding_status === 'not_found') return 'error'
  if (port.availability?.online === false) return 'warning'
  return 'success'
}

const availabilityLabel = port => {
  if (port.availability?.state === 'unavailable' || port.binding_status === 'not_found') return 'Источник не найден'
  return port.availability?.online === false ? 'Источник offline' : 'Источник online'
}

const portIcon = port => {
  if (port.icon) return String(port.icon).replace(/^mdi:/, 'mdi-')
  if (port.type === 'switch' || port.type === 'input_boolean') return 'mdi-toggle-switch-outline'
  if (port.type === 'number' || port.type === 'input_number') return 'mdi-counter'
  if (port.type === 'input_select') return 'mdi-format-list-bulleted'
  if (port.type === 'input_text') return 'mdi-form-textbox'
  if (port.device_class === 'temperature') return 'mdi-thermometer'
  if (port.device_class === 'humidity') return 'mdi-water-percent'
  if (port.device_class === 'power' || port.device_class === 'energy') return 'mdi-flash'
  return 'mdi-chart-line'
}

const bindingIcon = status => ({
  bound: 'mdi-link-variant',
  not_found: 'mdi-link-variant-off',
  changed: 'mdi-link-variant-minus',
  unbound: 'mdi-link-variant-off'
}[status] || 'mdi-help-circle-outline')

const loadPorts = async () => {
  loading.value = true
  error.value = null

  try {
    const response = await secureFetch('/api/virtual-ports')
    if (response.ok) {
      const data = await response.json()
      // Порты внутри виртуальных устройств показываются в их карточках,
      // поэтому в общем нижнем списке оставляем только standalone-порты.
      ports.value = (data.ports || []).filter(port => !port.virtual_device_id)
    } else {
      error.value = 'Ошибка загрузки виртуальных портов'
    }
  } catch (err) {
    console.error('Error loading virtual ports:', err)
    error.value = 'Ошибка загрузки виртуальных портов'
  } finally {
    loading.value = false
  }
}

const loadDevices = async () => {
  const query = selectedTag.value ? `?tag=${encodeURIComponent(selectedTag.value)}` : ''
  try {
    const response = await secureFetch(`/api/virtual-devices${query}`)
    const data = await response.json()
    devices.value = data.devices || []
    tags.value = data.tags || []
  } catch (err) { messageStore.showError('Ошибка загрузки виртуальных устройств') }
}
const createDevice = () => { editingDeviceId.value = null; deviceForm.value = { name: '', tags: [] }; deviceDialog.value = true }
const editDevice = device => {
  editingDeviceId.value = device.id
  deviceForm.value = { name: device.name || '', tags: (device.tags || []).map(normalizeTag).filter(Boolean) }
  deviceDialog.value = true
}
const saveDevice = async () => {
  if (!deviceForm.value.name.trim()) return
  const payload = { name: deviceForm.value.name, tags: (deviceForm.value.tags || []).map(stripTag).filter(Boolean) }
  if (editingDeviceId.value) {
    const response = await secureFetch(`/api/virtual-devices/${editingDeviceId.value}`, { method: 'PUT', data: payload })
    if (!response.ok) { messageStore.showError('Не удалось сохранить устройство'); return }
    deviceDialog.value = false; await loadDevices(); messageStore.showSuccess('Виртуальное устройство обновлено')
  } else {
    await secureFetch('/api/virtual-devices', { method: 'POST', data: payload })
    deviceDialog.value = false; await loadDevices(); messageStore.showSuccess('Виртуальное устройство создано')
  }
}
const copyDevice = async device => { await secureFetch(`/api/virtual-devices/${device.id}/copy`, { method: 'POST', data: {} }); await loadDevices(); messageStore.showSuccess('Устройство скопировано') }
const copyPort = async (device, port) => { await secureFetch(`/api/virtual-devices/${device.id}/ports/${port.id}/copy`, { method: 'POST', data: {} }); await loadDevices(); messageStore.showSuccess('Порт скопирован') }
const openMoveDialog = (device, port) => { moveSourceDevice.value = device; movePortTarget.value = port; moveTargetDeviceId.value = null; moveDialog.value = true }
const movePort = async () => {
  if (!moveSourceDevice.value || !movePortTarget.value || !moveTargetDeviceId.value) return
  const response = await secureFetch(`/api/virtual-devices/${moveSourceDevice.value.id}/ports/${movePortTarget.value.id}/move`, { method: 'PUT', data: { target_virtual_device_id: moveTargetDeviceId.value } })
  if (!response.ok) { messageStore.showError('Не удалось перенести порт'); return }
  moveDialog.value = false
  await loadDevices()
  messageStore.showSuccess('Порт перенесён в другое виртуальное устройство')
}
const deleteDevicePort = async (device, port) => { if (!confirm(`Удалить порт "${port.name}"?`)) return; await secureFetch(`/api/virtual-devices/${device.id}/ports/${port.id}`, { method: 'DELETE' }); await loadDevices() }
const bindingLabel = status => ({ bound: 'привязан', not_found: 'не найден', changed: 'изменён', unbound: 'без привязки' }[status] || '—')
const bindingColor = status => ({ bound: 'success', not_found: 'error', changed: 'warning', unbound: 'grey' }[status] || 'grey')
const publishDevice = async device => { await secureFetch(`/api/virtual-devices/${device.id}/publish`, { method: 'POST', data: {} }); messageStore.showSuccess('Публикация в HA выполнена') }
const deleteDevice = async device => { if (!confirm(`Удалить виртуальное устройство "${device.name}"?`)) return; await secureFetch(`/api/virtual-devices/${device.id}`, { method: 'DELETE' }); await loadDevices(); messageStore.showSuccess('Устройство удалено') }

const openAddDialog = () => {
  selectedPort.value = null
  selectedVirtualDeviceId.value = null
  dialog.value = true
}

const openAddPort = device => {
  selectedPort.value = null
  selectedVirtualDeviceId.value = device.id
  dialog.value = true
}

const editPort = (port) => {
  selectedPort.value = port
  selectedVirtualDeviceId.value = port.virtual_device_id || null
  dialog.value = true
}

const deletePort = async (port) => {
  if (!confirm(`Удалить виртуальный порт "${port.name}"?`)) return

  try {
    const response = await secureFetch(`/api/virtual-ports/${port.id}`, {
      method: 'DELETE'
    })

    if (response.ok) {
      messageStore.showSuccess('Виртуальный порт удален')
      await loadPorts()
    } else {
      const errorData = await response.json()
      messageStore.showError(errorData.detail || 'Ошибка удаления порта')
    }
  } catch (err) {
    console.error('Error deleting virtual port:', err)
    messageStore.showError('Ошибка удаления порта')
  }
}

const handlePortSaved = () => {
  loadPorts()
  loadDevices()
}

onMounted(() => {
  loadPorts()
  loadDevices()
})
watch(selectedTag, loadDevices)
</script>

<style scoped>
.virtual-ports-manager {
  padding: 16px 0;
}
.tag-filter { max-width: 220px; }
.device-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.device-card-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.device-card-actions {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 2px;
  margin-left: auto;
}
.virtual-port-row {
  display: grid;
  grid-template-columns: minmax(115px, 1.5fr) minmax(40px, .7fr) 20px minmax(80px, .9fr) 20px 20px auto;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.virtual-port-list {
  overflow: hidden;
}
.virtual-port-name,
.virtual-port-source,
.virtual-port-value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.virtual-port-value {
  font-family: monospace;
  justify-self: start;
  max-width: 100%;
}
.virtual-port-value :deep(.v-chip__content) {
  overflow: hidden;
  text-overflow: ellipsis;
}
.virtual-port-actions {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}
@media (max-width: 900px) {
  .virtual-port-row {
    grid-template-columns: minmax(100px, 1.4fr) minmax(35px, .7fr) 20px minmax(70px, .8fr) 20px 20px auto;
  }
}
</style>
