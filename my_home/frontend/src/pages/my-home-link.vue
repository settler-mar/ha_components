<template>
  <div class="link-page">
    <div class="page-header">
      <div>
        <h1>MY HOME Link</h1>
        <p>Универсальные связи между модулями</p>
      </div>
      <div class="d-flex align-center ga-2">
        <v-btn
          :color="editMode ? 'warning' : 'primary'"
          :prepend-icon="editMode ? 'mdi-lock-open-variant' : 'mdi-pencil-lock'"
          variant="tonal"
          @click="toggleEditMode"
        >{{ editMode ? 'Выйти из редактирования' : 'Редактировать' }}</v-btn>
        <v-btn v-if="editMode" color="primary" prepend-icon="mdi-plus" @click="openCreateDialog">Добавить</v-btn>
        <v-btn icon="mdi-refresh" variant="text" :loading="loading" @click="loadLinks" />
      </div>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" class="mb-4" closable @click:close="error = ''">{{ error }}</v-alert>

    <v-card v-for="link in links" :key="link.link_id" class="link-card mb-4" variant="outlined">
      <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-3">
        <div class="d-flex align-center ga-2">
          <v-icon color="primary">mdi-link-variant</v-icon>
          <span>{{ link.producer }} → {{ link.consumer }}</span>
          <v-chip size="x-small" variant="tonal" class="ml-2">{{ link.link_id }}</v-chip>
        </div>
        <div class="d-flex align-center ga-2">
          <v-select
            v-model="link.mode"
            :items="modes"
            label="Режим"
            density="compact"
            hide-details
            variant="outlined"
            style="max-width: 170px"
            @update:model-value="changeMode(link)"
          />
          <v-btn v-if="editMode" icon="mdi-code-json" size="small" variant="text" title="Открыть JSON debug" @click="openEditDialog(link, 'json')" />
          <v-btn v-if="editMode" icon="mdi-content-copy" size="small" variant="text" title="Копировать" @click="duplicateLink(link)" />
          <v-btn v-if="editMode" icon="mdi-delete" size="small" variant="text" color="error" title="Удалить" @click="confirmDelete(link)" />
        </div>
      </v-card-title>

      <v-card-text>
        <v-alert v-if="editMode" type="warning" variant="tonal" density="compact" class="mb-4">
          Режим редактирования: изменения этой связи применяются только после сохранения.
        </v-alert>
        <div v-if="editMode" class="inline-config mb-4">
          <v-text-field v-model="editableLink(link).producer" label="Производитель" variant="outlined" density="compact" hide-details />
          <v-text-field v-model="editableLink(link).consumer" label="Получатель" variant="outlined" density="compact" hide-details />
          <v-text-field v-model="editableLink(link).contract_version" label="Версия" type="number" variant="outlined" density="compact" hide-details />
          <v-switch v-model="editableLink(link).enabled" label="Разрешена" color="primary" density="compact" hide-details />
        </div>
        <div class="status-grid mb-4">
          <div><span>Состояние</span><strong>{{ link.mode === 'disabled' ? 'Отключена' : 'Активна' }}</strong></div>
          <div><span>Качество</span><strong :class="qualityClass(link)">{{ linkQuality(link) }}</strong></div>
          <div><span>Ошибка</span><strong>{{ link.last_error || 'нет' }}</strong></div>
          <div><span>Физические выходы</span><strong class="safe">защищены</strong></div>
        </div>

        <v-alert v-if="link.mode === 'virtual'" type="info" variant="tonal" density="compact" class="mb-4">
          Virtual module активен только для тестирования. Физические выходы недоступны.
        </v-alert>

        <v-table density="comfortable">
          <thead>
            <tr>
              <th><v-tooltip text="Стабильное имя значения внутри MY HOME Link." location="top"><template #activator="{ props }"><span v-bind="props" class="table-header-help">Значение</span></template></v-tooltip></th>
              <th><v-tooltip text="Источник формирует значение, получатель его принимает. Например: HA / floor_heating → ESP / boiler_ctrl." location="top"><template #activator="{ props }"><span v-bind="props" class="table-header-help">Источник → получатель</span></template></v-tooltip></th>
              <th><v-tooltip text="Последнее принятое значение. При timeout оно заменяется безопасным значением." location="top"><template #activator="{ props }"><span v-bind="props" class="table-header-help">Текущее</span></template></v-tooltip></th>
              <th v-if="!editMode"><v-tooltip text="Качество данных: good, degraded, stale, timeout, invalid или offline." location="top"><template #activator="{ props }"><span v-bind="props" class="table-header-help">Quality</span></template></v-tooltip></th>
              <th v-if="!editMode"><v-tooltip text="Сколько времени прошло с момента последнего обновления значения." location="top"><template #activator="{ props }"><span v-bind="props" class="table-header-help">Возраст</span></template></v-tooltip></th>
              <th><v-tooltip text="Максимально допустимый возраст значения. После него значение считается timeout." location="top"><template #activator="{ props }"><span v-bind="props" class="table-header-help">Timeout</span></template></v-tooltip></th>
              <th><v-tooltip text="Начальное значение используется до первого обновления. Безопасное значение используется при stale/timeout согласно выбранному поведению." location="top"><template #activator="{ props }"><span v-bind="props" class="table-header-help">Начальное / безопасное</span></template></v-tooltip></th>
              <th><v-tooltip text="Способ связи с Home Assistant: нет привязки, virtual port или существующий HA entity." location="top"><template #activator="{ props }"><span v-bind="props" class="table-header-help">HA-интерфейс</span></template></v-tooltip></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(spec, name) in editableLink(link).values" :key="name">
              <td>
                <strong>{{ name }}</strong>
                <small v-if="spec.unit"> · {{ spec.unit }}</small>
                <small class="d-block"> · {{ spec.value_type }}</small>
              </td>
              <td>
                <div class="endpoint-flow">
                  <span>{{ endpointLabel(spec.source, link.producer) }}</span>
                  <v-icon size="14">mdi-arrow-right</v-icon>
                  <span>{{ endpointLabel(spec.target, link.consumer) }}</span>
                </div>
                <v-select v-if="editMode" v-model="spec.direction" :items="directions" label="Направление" density="compact" variant="outlined" hide-details class="mt-3" style="min-width: 190px" />
                <small v-else>{{ spec.direction === 'producer_to_consumer' ? 'запрос' : 'обратная связь' }}</small>
              </td>
              <td>
                <div>{{ displayValue(link.states?.[name]?.value, spec) }}</div>
              </td>
              <td v-if="!editMode"><v-chip size="small" :color="qualityColor(link.states?.[name]?.quality)">{{ link.states?.[name]?.quality || 'unknown' }}</v-chip></td>
              <td v-if="!editMode">{{ age(link.states?.[name]) }}</td>
              <td>
                <v-text-field v-if="editMode" v-model="spec.timeout_s" type="number" suffix="s" density="compact" variant="outlined" hide-details style="max-width: 120px" />
                <span v-else>{{ spec.timeout_s }} s</span>
              </td>
              <td class="safety-cell">
                <template v-if="editMode">
                  <div class="safety-stack">
                    <v-select v-model="spec.error_behavior" :items="errorBehaviors" label="При ошибке" density="compact" variant="outlined" hide-details />
                    <v-text-field v-model="spec.initial" label="Начальное значение" density="compact" variant="outlined" hide-details />
                    <v-text-field
                      v-if="spec.error_behavior === 'safe_value'"
                      v-model="spec.on_stale"
                      label="Безопасное значение"
                      density="compact"
                      variant="outlined"
                      hide-details
                    />
                  </div>
                </template>
                <template v-else>
                  <div>Начальное: {{ spec.initial ?? '—' }}</div>
                  <div v-if="spec.error_behavior === 'safe_value'">Безопасное: {{ spec.on_stale ?? '—' }}</div>
                  <small>{{ errorBehaviorLabel(spec.error_behavior) }}</small>
                </template>
              </td>
              <td>
                <v-btn size="small" variant="tonal" :color="bindingMode(spec) === 'none' ? 'grey' : 'primary'" @click="openBindingDialog(link, name)">
                  {{ bindingLabel(spec) }}
                </v-btn>
                <v-btn v-if="editMode" size="small" variant="text" prepend-icon="mdi-chip" class="mt-1" @click="openPhysicalBindingDialog(editableLink(link), name)">
                  {{ physicalBindingLabel(spec) }}
                </v-btn>
              </td>
            </tr>
          </tbody>
        </v-table>
        <v-btn v-if="editMode" size="small" variant="tonal" prepend-icon="mdi-plus" class="mt-3" @click="addInlineValue(link)">
          Добавить строку значения
        </v-btn>
        <div v-if="editMode" class="d-flex justify-end ga-2 mt-4">
          <v-btn variant="text" @click="cancelInlineEdit(link)">Отмена</v-btn>
          <v-btn color="primary" prepend-icon="mdi-content-save" :loading="inlineSaving[link.link_id]" @click="saveInlineEdit(link)">Сохранить изменения</v-btn>
        </div>
      </v-card-text>
    </v-card>

    <v-card v-if="!loading && !links.length" variant="outlined"><v-card-text>Связи модулей ещё не созданы.</v-card-text></v-card>

    <v-dialog v-model="editorDialog" max-width="980" persistent>
      <v-card>
        <v-card-title class="d-flex align-center justify-space-between">
          <span>{{ editorMode === 'create' ? 'Новая связь' : `Редактирование: ${editorOriginalId}` }}</span>
          <v-chip size="small" color="warning" variant="tonal">режим редактирования</v-chip>
        </v-card-title>
        <v-card-text>
          <v-alert v-if="editorError" type="error" variant="tonal" class="mb-4">
            <div class="font-weight-medium mb-1">{{ editorError.title || editorError }}</div>
            <ul v-if="editorError.details?.length" class="editor-error-list">
              <li v-for="(detail, idx) in editorError.details" :key="idx">{{ detail }}</li>
            </ul>
            <div v-if="editorError.hint" class="mt-2 text-caption">{{ editorError.hint }}</div>
          </v-alert>
          <v-alert type="info" variant="tonal" density="compact" class="mb-3">
            <div class="font-weight-medium mb-1">Обязательные поля конфигурации</div>
            <ul class="editor-error-list">
              <li><code>link_id</code> — уникальный идентификатор связи (латиница, цифры, <code>-</code>, <code>_</code>). Пример: <code>floor-to-boiler</code>.</li>
              <li><code>producer</code> — имя модуля-источника. Пример: <code>floor_heating</code>.</li>
              <li><code>consumer</code> — имя модуля-получателя. Пример: <code>boiler_ctrl</code>.</li>
              <li><code>contract_version</code> — целое число, версия контракта (обычно <code>1</code>).</li>
              <li><code>values</code> — объект описаний значений. Можно оставить пустым <code>{}</code> и добавить позже.</li>
            </ul>
          </v-alert>
          <v-textarea
            v-model="editorJson"
            label="Полная конфигурация JSON / YAML"
            variant="outlined"
            rows="20"
            class="code-area"
            hint="Для debug, быстрого переноса и массового редактирования. Заполните поля сверху справа."
            persistent-hint
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="editorDialog = false">Отмена</v-btn>
          <v-btn color="primary" :loading="editorSaving" @click="saveEditor">Сохранить</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="deleteDialog" max-width="420">
      <v-card>
        <v-card-title>Удалить связь?</v-card-title>
        <v-card-text>Связь <strong>{{ deleteTarget?.link_id }}</strong> будет удалена безвозвратно.</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">Отмена</v-btn>
          <v-btn color="error" :loading="deleteSaving" @click="deleteLink">Удалить</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="bindingDialog" max-width="560">
      <v-card>
        <v-card-title>HA-интерфейс: {{ bindingTarget?.valueName }}</v-card-title>
        <v-card-text>
          <div class="binding-endpoints mb-4">
            <div><small>Источник</small><strong>{{ bindingTarget && endpointLabel(bindingTarget.spec.source, bindingTarget.link.producer) }}</strong></div>
            <v-icon>mdi-arrow-right</v-icon>
            <div><small>Получатель</small><strong>{{ bindingTarget && endpointLabel(bindingTarget.spec.target, bindingTarget.link.consumer) }}</strong></div>
          </div>
          <v-select v-model="bindingModeValue" :items="bindingModes" label="Способ привязки" variant="outlined" @update:model-value="loadBindingDevices" />
          <template v-if="bindingModeValue === 'ha_entity' || bindingModeValue === 'virtual_port'">
            <v-autocomplete
              v-model="bindingDeviceId"
              :items="bindingDeviceItems()"
              :label="bindingModeValue === 'ha_entity' ? 'Устройство Home Assistant' : 'Виртуальное устройство'"
              variant="outlined"
              item-title="title"
              item-value="value"
              clearable
              prepend-inner-icon="mdi-magnify"
              no-data-text="Устройства не найдены"
              :loading="bindingDevicesLoading"
              :error-messages="bindingLoadError ? [bindingLoadError] : []"
              @update:model-value="loadBindingPorts"
            >
              <template #item="{ props, item }">
                <v-list-item v-bind="props" :prepend-icon="item.raw.icon">
                  <template #title>{{ item.raw.title }}</template>
                  <template #subtitle>{{ item.raw.subtitle }}</template>
                </v-list-item>
              </template>
            </v-autocomplete>
            <v-autocomplete
              v-if="bindingDeviceId"
              v-model="bindingPortId"
              :items="bindingPortItems()"
              :label="bindingModeValue === 'ha_entity' ? 'Порт / entity' : 'Виртуальный порт'"
              variant="outlined"
              item-title="title"
              item-value="value"
              clearable
              prepend-inner-icon="mdi-magnify"
              no-data-text="Порты не найдены"
              :loading="bindingPortsLoading"
              hint="Сначала выберите устройство, затем его порт"
              persistent-hint
            >
              <template #item="{ props, item }">
                <v-list-item v-bind="props" :prepend-icon="item.raw.icon">
                  <template #title>{{ item.raw.title }}</template>
                  <template #subtitle>{{ item.raw.subtitle }}</template>
                </v-list-item>
              </template>
            </v-autocomplete>
            <div v-if="selectedBindingPort()" class="binding-selection-context mb-3">
              <v-icon size="18">mdi-information-outline</v-icon>
              <span>{{ selectedBindingPort().context }}</span>
            </div>
            <v-alert type="info" variant="tonal" density="compact">
              {{ bindingModeValue === 'ha_entity' ? 'Выберите существующее устройство и entity в Home Assistant.' : 'Virtual port используется для отображения и тестов. Он не управляет физическими выходами.' }}
            </v-alert>
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="bindingDialog = false">Отмена</v-btn>
          <v-btn color="primary" :loading="bindingSaving" @click="saveBinding">Сохранить</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="physicalBindingDialog" max-width="560">
      <v-card>
        <v-card-title>Физический ESP-порт: {{ physicalBindingTarget?.valueName }}</v-card-title>
        <v-card-text>
          <v-alert type="warning" variant="tonal" density="compact" class="mb-4">
            Передача на ESP выполняется только когда режим связи установлен в <strong>Physical</strong>. В Virtual и Disabled физические команды не отправляются.
          </v-alert>
          <v-autocomplete v-model="physicalDeviceId" :items="physicalDeviceItems()" label="Устройство ESP" variant="outlined" item-title="title" item-value="value" prepend-inner-icon="mdi-chip" clearable :loading="physicalDevicesLoading" @update:model-value="loadPhysicalPorts">
            <template #item="{ props, item }"><v-list-item v-bind="props" :prepend-icon="item.raw.icon"><template #title>{{ item.raw.title }}</template><template #subtitle>{{ item.raw.subtitle }}</template></v-list-item></template>
          </v-autocomplete>
          <v-autocomplete v-if="physicalDeviceId" v-model="physicalPortId" :items="physicalPortItems()" label="Порт ESP" variant="outlined" item-title="title" item-value="value" prepend-inner-icon="mdi-connection" clearable :loading="physicalPortsLoading" hint="Выберите выход для запроса или вход для обратной связи" persistent-hint @update:model-value="selectPhysicalPort">
            <template #item="{ props, item }"><v-list-item v-bind="props" :prepend-icon="item.raw.icon"><template #title>{{ item.raw.title }}</template><template #subtitle>{{ item.raw.subtitle }}</template></v-list-item></template>
          </v-autocomplete>
          <div v-if="selectedPhysicalPort" class="binding-selection-context">{{ selectedPhysicalPort.subtitle }}</div>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn variant="text" @click="physicalBindingDialog = false">Отмена</v-btn><v-btn color="primary" :loading="physicalBindingSaving" @click="savePhysicalBinding">Сохранить</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { secureFetch } from '@/services/fetch'
import { webSocketService } from '@/services/websocket'

const links = ref([])
const loading = ref(false)
const error = ref('')
const modes = [
  { title: 'Disabled', value: 'disabled' },
  { title: 'Physical', value: 'physical' },
  { title: 'Virtual', value: 'virtual' },
]
const directions = [
  { title: 'К получателю', value: 'producer_to_consumer' },
  { title: 'Обратная связь', value: 'consumer_to_producer' },
]
const valueTypes = ['boolean', 'number', 'integer', 'string', 'json']
const errorBehaviors = [
  { title: 'Отклонить значение', value: 'reject' },
  { title: 'Безопасное значение', value: 'safe_value' },
]

const editMode = ref(false)
const inlineDrafts = ref({})
const inlineSaving = ref({})
const editorDialog = ref(false)
const editorMode = ref('create')
const editorOriginalId = ref('')
const editorJson = ref('')
const editorView = ref('form')
const editorGeneral = ref({})
const editorValues = ref([])
const editorError = ref('')
const editorSaving = ref(false)

const deleteDialog = ref(false)
const deleteTarget = ref(null)
const deleteSaving = ref(false)
const bindingDialog = ref(false)
const bindingTarget = ref(null)
const bindingModeValue = ref('none')
const bindingDeviceId = ref(null)
const bindingPortId = ref(null)
const bindingSaving = ref(false)
const bindingDevices = ref([])
const bindingPorts = ref([])
const bindingDevicesLoading = ref(false)
const bindingPortsLoading = ref(false)
const bindingLoadError = ref('')
const virtualPorts = ref([])
const physicalBindingDialog = ref(false)
const physicalBindingTarget = ref(null)
const physicalDeviceId = ref(null)
const physicalPortId = ref(null)
const physicalDevices = ref([])
const physicalPorts = ref([])
const physicalDevicesLoading = ref(false)
const physicalPortsLoading = ref(false)
const physicalBindingSaving = ref(false)
const selectedPhysicalPort = ref(null)
const bindingModes = [
  { title: 'Нет привязки', value: 'none' },
  { title: 'Virtual port', value: 'virtual_port' },
  { title: 'Реальный HA entity', value: 'ha_entity' },
]

const emptyLinkTemplate = () => ({
  link_id: '',
  producer: '',
  consumer: '',
  contract_version: 1,
  enabled: true,
  values: {},
  virtual: {},
})

const loadLinks = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await secureFetch('/api/module-links')
    const data = await response.json()
    links.value = data.links || []
  } catch (err) {
    error.value = 'Не удалось загрузить связи модулей'
  } finally {
    loading.value = false
  }
}

const editableLink = link => inlineDrafts.value[link.link_id] || link

const toggleEditMode = () => {
  if (editMode.value) {
    editMode.value = false
    inlineDrafts.value = {}
    return
  }
  inlineDrafts.value = Object.fromEntries(links.value.map(link => [link.link_id, sanitizeLink(link)]))
  editMode.value = true
}

const cancelInlineEdit = link => {
  const draft = inlineDrafts.value[link.link_id]
  if (draft) inlineDrafts.value[link.link_id] = sanitizeLink(link)
}

const addInlineValue = link => {
  const draft = editableLink(link)
  const name = `new_value_${Object.keys(draft.values || {}).length + 1}`
  draft.values[name] = {
    name,
    direction: 'producer_to_consumer',
    value_type: 'string',
    unit: null,
    minimum: null,
    maximum: null,
    initial: '',
    on_stale: '',
    timeout_s: 120,
    error_behavior: 'reject',
    source: { system: 'other', module: draft.producer },
    target: { system: 'other', module: draft.consumer },
    ha_binding: { mode: 'none' },
  }
}

const saveInlineEdit = async link => {
  const draft = editableLink(link)
  inlineSaving.value[link.link_id] = true
  try {
    const response = await secureFetch(`/api/module-links/${link.link_id}`, { method: 'PUT', data: sanitizeLink(draft) })
    const data = await response.json()
    Object.assign(link, data.link)
    delete inlineDrafts.value[link.link_id]
  } catch (err) {
    error.value = err?.message || 'Не удалось сохранить конфигурацию'
  } finally {
    inlineSaving.value[link.link_id] = false
  }
}

const loadVirtualPorts = async () => {
  try {
    const response = await secureFetch('/api/virtual-ports')
    const data = await response.json()
    virtualPorts.value = data.ports || []
  } catch (err) {
    virtualPorts.value = []
  }
}

const changeMode = async link => {
  try {
    const response = await secureFetch(`/api/module-links/${link.link_id}/mode`, { method: 'POST', data: { mode: link.mode } })
    const data = await response.json()
    Object.assign(link, data.link)
  } catch (err) {
    error.value = 'Не удалось изменить режим связи'
    await loadLinks()
  }
}

const createDisplayPort = async (link, valueName) => {
  try {
    await secureFetch(`/api/module-links/${link.link_id}/display-ports`, {
      method: 'POST',
      data: { value_name: valueName },
    })
    await loadVirtualPorts()
  } catch (err) {
    error.value = `Не удалось создать display port для ${valueName}`
  }
}

const displayPortFor = (link, valueName) => virtualPorts.value.find(port => {
  const binding = port?.binding || {}
  return binding.module_link_id === link.link_id && binding.value_name === valueName
})

const bindingMode = spec => spec?.ha_binding?.mode || 'none'
const bindingLabel = spec => ({ none: 'не подключено', virtual_port: spec?.ha_binding?.port_id ? 'virtual port' : 'virtual port', ha_entity: spec?.ha_binding?.entity_id || 'HA entity' }[bindingMode(spec)] || 'не подключено')
const systemLabel = system => ({ home_assistant: 'HA', esp: 'ESP', my_home: 'MY HOME', other: 'другое' }[system] || system || '—')
const inferredSystem = moduleName => ({ floor_heating: 'home_assistant', boiler_ctrl: 'esp' }[moduleName] || '')
const endpointLabel = (endpoint, fallback) => `${systemLabel(endpoint?.system || inferredSystem(endpoint?.module || fallback))} / ${endpoint?.module || fallback || '—'}`
const bindingDeviceItems = () => bindingDevices.value.map(device => ({
  title: device.name || device.device_id,
  value: device.device_id,
  icon: bindingModeValue.value === 'ha_entity' ? 'mdi-home-assistant' : 'mdi-chip',
  subtitle: [device.manufacturer, device.model, `${device.ports?.length || 0} порт.`].filter(Boolean).join(' · '),
}))
const bindingPortItems = () => bindingPorts.value.map(port => {
  const entity = port.entity_id || port.port_id
  const current = port.state ?? port.value
  return {
    title: port.name || entity,
    value: port.port_id || entity,
    icon: port.icon || (port.domain === 'sensor' ? 'mdi-gauge' : 'mdi-connection'),
    subtitle: [entity, port.domain, current != null ? `текущее: ${current}` : null, port.unit_of_measurement || port.unit].filter(Boolean).join(' · '),
    context: [entity, port.domain, current != null ? `текущее значение: ${current}` : null, port.unit_of_measurement || port.unit].filter(Boolean).join(' · '),
  }
})
const selectedBindingPort = () => bindingPortItems().find(item => item.value === bindingPortId.value)
const physicalBindingLabel = spec => {
  const binding = spec?.physical_binding || {}
  return binding.device_id && binding.port_id ? `ESP ${binding.device_id} / ${binding.port_id}` : 'Привязать ESP'
}
const physicalDeviceItems = () => physicalDevices.value.map(device => ({
  title: device.name || `ESP ${device.device_id}`,
  value: device.device_id,
  icon: device.online ? 'mdi-chip' : 'mdi-chip-off',
  subtitle: [device.ip, device.online ? 'онлайн' : 'офлайн', `${device.ports_count || 0} порт.`].filter(Boolean).join(' · '),
}))
const physicalPortItems = () => physicalPorts.value.map(port => ({
  title: port.name || port.code,
  value: port.port_id || port.code,
  icon: port.direction === 'out' ? 'mdi-export' : 'mdi-import',
  subtitle: [port.code, port.direction === 'out' ? 'выход' : 'вход', port.kind, port.value_type, port.unit].filter(Boolean).join(' · '),
}))
const selectPhysicalPort = portId => { selectedPhysicalPort.value = physicalPortItems().find(item => item.value === portId) || null }

const loadPhysicalDevices = async () => {
  physicalDevicesLoading.value = true
  try {
    const response = await secureFetch('/api/module-links/physical/devices')
    const data = await response.json()
    if (!data.success) throw new Error(data.error || 'Не удалось загрузить ESP')
    physicalDevices.value = data.devices || []
  } catch (err) {
    error.value = err?.message || 'Не удалось загрузить ESP-устройства'
  } finally {
    physicalDevicesLoading.value = false
  }
}

const loadPhysicalPorts = async deviceId => {
  physicalDeviceId.value = deviceId || null
  physicalPortId.value = null
  selectedPhysicalPort.value = null
  physicalPorts.value = []
  if (!deviceId) return
  physicalPortsLoading.value = true
  try {
    const response = await secureFetch(`/api/module-links/physical/devices/${encodeURIComponent(deviceId)}/ports`)
    const data = await response.json()
    if (!data.success) throw new Error(data.error || 'Не удалось загрузить порты ESP')
    physicalPorts.value = data.ports || []
  } catch (err) {
    error.value = err?.message || 'Не удалось загрузить порты ESP'
  } finally {
    physicalPortsLoading.value = false
  }
}

const openPhysicalBindingDialog = async (link, valueName) => {
  physicalBindingTarget.value = { link, valueName, spec: link.values[valueName] }
  physicalDeviceId.value = link.values[valueName]?.physical_binding?.device_id || null
  physicalPortId.value = link.values[valueName]?.physical_binding?.port_id || null
  physicalBindingDialog.value = true
  await loadPhysicalDevices()
  if (physicalDeviceId.value) {
    await loadPhysicalPorts(physicalDeviceId.value)
    physicalPortId.value = link.values[valueName]?.physical_binding?.port_id || null
  }
}

const savePhysicalBinding = async () => {
  if (!physicalBindingTarget.value) return
  physicalBindingSaving.value = true
  try {
    const { link, valueName } = physicalBindingTarget.value
    const response = await secureFetch(`/api/module-links/${link.link_id}/values/${valueName}/physical-binding`, {
      method: 'PUT',
      data: { physical_binding: physicalDeviceId.value && physicalPortId.value ? { device_id: physicalDeviceId.value, port_id: physicalPortId.value } : {} },
    })
    const data = await response.json()
    Object.assign(link, data.link)
    physicalBindingDialog.value = false
  } catch (err) {
    error.value = err?.message || 'Не удалось сохранить привязку ESP'
  } finally {
    physicalBindingSaving.value = false
  }
}

const loadBindingDevices = async () => {
  if (!['ha_entity', 'virtual_port'].includes(bindingModeValue.value)) return
  bindingDevicesLoading.value = true
  bindingLoadError.value = ''
  bindingDevices.value = []
  bindingPorts.value = []
  try {
    const path = bindingModeValue.value === 'ha_entity' ? '/api/module-links/ha/devices' : '/api/module-links/virtual/devices'
    const response = await secureFetch(path)
    const data = await response.json()
    if (!data.success) {
      throw new Error(data.error === 'ha_unavailable'
        ? 'HA API недоступен или ключ не настроен'
        : 'Не удалось получить реестр Home Assistant')
    }
    bindingDevices.value = data.devices || []
    const saved = bindingTarget.value?.spec?.ha_binding || {}
    bindingDeviceId.value = saved.device_id || null
    if (bindingDeviceId.value) await loadBindingPorts(bindingDeviceId.value, saved.port_id || saved.entity_id || saved.virtual_port_id)
  } catch (err) {
    bindingLoadError.value = err?.message || (bindingModeValue.value === 'ha_entity'
      ? 'Не удалось связаться с backend MY HOME'
      : 'Не удалось загрузить виртуальные устройства')
  } finally {
    bindingDevicesLoading.value = false
  }
}

const loadBindingPorts = async (deviceId, preferredPort = null) => {
  bindingDeviceId.value = deviceId || null
  bindingPortId.value = null
  bindingPorts.value = []
  if (!deviceId) return
  bindingPortsLoading.value = true
  try {
    const prefix = bindingModeValue.value === 'ha_entity' ? 'ha' : 'virtual'
    const response = await secureFetch(`/api/module-links/${prefix}/devices/${encodeURIComponent(deviceId)}/ports`)
    const data = await response.json()
    if (!data.success) throw new Error(data.error || 'Список недоступен')
    bindingPorts.value = data.ports || []
    bindingPortId.value = preferredPort || null
  } catch (err) {
    bindingLoadError.value = 'Не удалось загрузить порты устройства'
  } finally {
    bindingPortsLoading.value = false
  }
}

const openBindingDialog = (link, valueName) => {
  const spec = link.values[valueName]
  bindingTarget.value = { link, valueName, spec }
  bindingModeValue.value = bindingMode(spec)
  bindingDeviceId.value = null
  bindingPortId.value = null
  bindingDevices.value = []
  bindingPorts.value = []
  bindingLoadError.value = ''
  bindingDialog.value = true
  loadBindingDevices()
}

const saveBinding = async () => {
  if (!bindingTarget.value) return
  bindingSaving.value = true
  try {
    const { link, valueName, spec } = bindingTarget.value
    const haBinding = { mode: bindingModeValue.value }
    if (bindingModeValue.value === 'ha_entity') {
      if (!bindingDeviceId.value || !bindingPortId.value) throw new Error('Выберите устройство и порт Home Assistant')
      haBinding.device_id = bindingDeviceId.value
      haBinding.port_id = bindingPortId.value
      haBinding.entity_id = bindingPortId.value
    }
    if (bindingModeValue.value === 'virtual_port') {
      if (!bindingDeviceId.value || !bindingPortId.value) throw new Error('Выберите виртуальное устройство и порт')
      haBinding.device_id = bindingDeviceId.value
      haBinding.port_id = bindingPortId.value
      haBinding.virtual_port_id = bindingPortId.value
    }
    const response = await secureFetch(`/api/module-links/${link.link_id}/values/${valueName}/binding`, {
      method: 'PUT',
      data: { source: spec.source, target: spec.target, ha_binding: haBinding },
    })
    const data = await response.json()
    Object.assign(link, data.link)
    bindingDialog.value = false
  } catch (err) {
    error.value = err?.message || 'Не удалось сохранить HA-привязку'
  } finally {
    bindingSaving.value = false
  }
}

const sanitizeLink = raw => {
  const copy = JSON.parse(JSON.stringify(raw))
  delete copy.states
  delete copy.mode
  delete copy.last_error
  delete copy.physical_outputs_protected
  return copy
}

const editorValueFromSpec = (name, spec = {}) => ({
  _id: `${Date.now()}-${Math.random()}`,
  name,
  direction: spec.direction || 'producer_to_consumer',
  value_type: spec.value_type || 'string',
  unit: spec.unit || '',
  minimum: spec.minimum ?? '',
  maximum: spec.maximum ?? '',
  initial: spec.initial ?? '',
  on_stale: spec.on_stale ?? '',
  timeout_s: spec.timeout_s ?? 120,
  error_behavior: spec.error_behavior || 'reject',
  source: spec.source || {},
  target: spec.target || {},
  ha_binding: spec.ha_binding || { mode: 'none' },
})

const loadEditorFromLink = (link, mode = 'edit') => {
  editorMode.value = mode
  editorOriginalId.value = link?.link_id || ''
  editorGeneral.value = {
    link_id: link?.link_id || '',
    producer: link?.producer || '',
    consumer: link?.consumer || '',
    contract_version: link?.contract_version || 1,
    enabled: link?.enabled !== false,
    virtual: link?.virtual || {},
  }
  editorValues.value = Object.entries(link?.values || {}).map(([name, spec]) => editorValueFromSpec(name, spec))
  editorJson.value = JSON.stringify(sanitizeLink(link), null, 2)
  editorView.value = 'form'
  editorError.value = ''
  editorDialog.value = true
}

const addEditorValue = () => editorValues.value.push(editorValueFromSpec('', { value_type: 'string' }))
const removeEditorValue = index => editorValues.value.splice(index, 1)

const parseEditorValue = (value, type) => {
  if (value === '' || value == null) return null
  if (type === 'boolean') return value === true || value === 'true'
  if (type === 'number') return Number(value)
  if (type === 'integer') return Number.parseInt(value, 10)
  if (type === 'json') {
    try { return JSON.parse(value) } catch { return value }
  }
  return String(value)
}

const buildEditorPayload = () => {
  const values = {}
  for (const item of editorValues.value) {
    const name = String(item.name || '').trim()
    if (!name) throw new Error('У каждого значения должно быть имя')
    values[name] = {
      name,
      direction: item.direction,
      value_type: item.value_type,
      unit: item.unit || null,
      minimum: item.minimum === '' ? null : Number(item.minimum),
      maximum: item.maximum === '' ? null : Number(item.maximum),
      initial: parseEditorValue(item.initial, item.value_type),
      on_stale: parseEditorValue(item.on_stale, item.value_type),
      timeout_s: Number(item.timeout_s || 120),
      error_behavior: item.error_behavior || 'reject',
      source: item.source || { system: 'other', module: editorGeneral.value.producer },
      target: item.target || { system: 'other', module: editorGeneral.value.consumer },
      ha_binding: item.ha_binding || { mode: 'none' },
    }
  }
  return {
    link_id: String(editorGeneral.value.link_id || '').trim(),
    producer: String(editorGeneral.value.producer || '').trim(),
    consumer: String(editorGeneral.value.consumer || '').trim(),
    contract_version: Number(editorGeneral.value.contract_version || 1),
    enabled: editorGeneral.value.enabled !== false,
    values,
    virtual: editorGeneral.value.virtual || {},
  }
}

const openCreateDialog = () => {
  if (!editMode.value) return
  loadEditorFromLink({ ...emptyLinkTemplate(), link_id: '', enabled: true }, 'create')
}

const openEditDialog = (link, view = 'form') => {
  if (!editMode.value) return
  loadEditorFromLink(sanitizeLink(link), 'edit')
  editorView.value = view
}

const duplicateLink = link => {
  const copy = sanitizeLink(link)
  copy.link_id = `${link.link_id}-copy`
  loadEditorFromLink(copy, 'create')
}

const saveEditor = async () => {
  editorError.value = ''
  let payload
  try {
    payload = editorView.value === 'json' ? JSON.parse(editorJson.value || '{}') : buildEditorPayload()
  } catch (err) {
    editorError.value = {
      title: 'Невалидный JSON',
      details: [err?.message || 'Не удалось разобрать текст конфигурации'],
      hint: 'Проверьте запятые, кавычки и фигурные скобки.',
    }
    return
  }

  const missing = []
  if (!payload.link_id || !String(payload.link_id).trim()) {
    missing.push('"link_id" — уникальный идентификатор связи (например "floor-to-boiler")')
  } else if (!/^[A-Za-z0-9_-]+$/.test(String(payload.link_id).trim())) {
    missing.push('"link_id" содержит недопустимые символы. Разрешены латиница, цифры, "-" и "_"')
  }
  if (!payload.producer || !String(payload.producer).trim()) {
    missing.push('"producer" — имя модуля-источника (например "floor_heating")')
  }
  if (!payload.consumer || !String(payload.consumer).trim()) {
    missing.push('"consumer" — имя модуля-получателя (например "boiler_ctrl")')
  }
  if (payload.contract_version != null && Number.isNaN(Number(payload.contract_version))) {
    missing.push('"contract_version" должен быть числом (обычно 1)')
  }
  if (payload.values != null && typeof payload.values !== 'object') {
    missing.push('"values" должен быть объектом. Если значений ещё нет — используйте {}')
  }
  if (missing.length) {
    editorError.value = {
      title: `Заполните обязательные поля (${missing.length})`,
      details: missing,
      hint: 'Добавьте недостающие поля в JSON и повторите сохранение.',
    }
    return
  }

  editorSaving.value = true
  try {
    if (editorMode.value === 'create') {
      await secureFetch('/api/module-links', { method: 'POST', data: payload })
    } else {
      await secureFetch(`/api/module-links/${editorOriginalId.value}`, { method: 'PUT', data: payload })
    }
    editorDialog.value = false
    await loadLinks()
  } catch (err) {
    editorError.value = {
      title: 'Не удалось сохранить связь',
      details: [err?.message || 'Ошибка сервера'],
    }
  } finally {
    editorSaving.value = false
  }
}

const confirmDelete = link => {
  deleteTarget.value = link
  deleteDialog.value = true
}

const deleteLink = async () => {
  if (!deleteTarget.value) return
  deleteSaving.value = true
  try {
    await secureFetch(`/api/module-links/${deleteTarget.value.link_id}`, { method: 'DELETE' })
    deleteDialog.value = false
    deleteTarget.value = null
    await loadLinks()
  } catch (err) {
    error.value = 'Не удалось удалить связь'
  } finally {
    deleteSaving.value = false
  }
}

const onLinkEvent = link => {
  const index = links.value.findIndex(item => item.link_id === link.link_id)
  if (index >= 0) links.value[index] = link
  else loadLinks()
}

const onLinkDeleted = payload => {
  const id = payload?.link_id
  if (!id) return
  links.value = links.value.filter(item => item.link_id !== id)
}

const linkQuality = link => Object.values(link.states || {}).reduce((worst, state) => {
  const order = ['invalid', 'timeout', 'offline', 'stale', 'degraded', 'unknown', 'good']
  return order.indexOf(state.quality) < order.indexOf(worst) ? state.quality : worst
}, 'good')
const qualityClass = link => ['good'].includes(linkQuality(link)) ? 'safe' : 'warn'
const qualityColor = quality => ({ good: 'success', degraded: 'warning', stale: 'orange', timeout: 'error', invalid: 'error', offline: 'error' }[quality] || 'grey')
const age = state => state?.age_s == null ? '—' : `${Math.round(state.age_s)} s`
const displayValue = (value, spec) => value == null ? '—' : `${value}${spec.unit ? ` ${spec.unit}` : ''}`
const errorBehaviorLabel = value => errorBehaviors.find(item => item.value === value)?.title || value || '—'

onMounted(async () => {
  await loadLinks()
  await loadVirtualPorts()
  webSocketService.onMessage('module_link', 'state_update', onLinkEvent)
  webSocketService.onMessage('module_link', 'mode_changed', onLinkEvent)
  webSocketService.onMessage('module_link', 'updated', onLinkEvent)
  webSocketService.onMessage('module_link', 'deleted', onLinkDeleted)
})
onBeforeUnmount(() => {
  webSocketService.offMessage('module_link', 'state_update', onLinkEvent)
  webSocketService.offMessage('module_link', 'mode_changed', onLinkEvent)
  webSocketService.offMessage('module_link', 'updated', onLinkEvent)
  webSocketService.offMessage('module_link', 'deleted', onLinkDeleted)
})
</script>

<style scoped>
.link-page { padding: 24px; max-width: 1400px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; gap: 12px; flex-wrap: wrap; }
.page-header h1 { margin: 0; font-size: 28px; }
.page-header p { margin: 4px 0 0; color: rgb(var(--v-theme-on-surface)); opacity: .75; }
.link-card { overflow: hidden; }
.status-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.status-grid div { padding: 12px; border: 1px solid rgba(var(--v-border-color), .35); border-radius: 8px; background: rgba(var(--v-theme-surface-variant), .35); }
.status-grid span { display: block; font-size: 13px; font-weight: 500; color: rgb(var(--v-theme-on-surface)); opacity: .9; margin-bottom: 6px; }
.status-grid strong { font-size: 15px; color: rgb(var(--v-theme-on-surface)); }
.safe { color: rgb(var(--v-theme-success)) !important; }
.warn { color: rgb(var(--v-theme-warning)) !important; }
small { color: rgb(var(--v-theme-on-surface)); opacity: .7; }
.code-area :deep(textarea) { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; }
.endpoint-flow { display: flex; align-items: center; gap: 4px; white-space: nowrap; }
.table-header-help { cursor: help; border-bottom: 1px dotted currentColor; }
.binding-endpoints { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.binding-endpoints div { flex: 1; padding: 10px; border-radius: 8px; background: rgba(var(--v-theme-surface-variant), .45); }
.binding-endpoints small, .binding-endpoints strong { display: block; }
.binding-selection-context { display: flex; align-items: center; gap: 8px; padding: 9px 12px; border-radius: 8px; background: rgba(var(--v-theme-primary), .08); color: rgb(var(--v-theme-on-surface)); font-size: 13px; }
.inline-config { display: grid; grid-template-columns: 1fr 1fr 120px 150px; gap: 10px; align-items: center; padding: 12px; border: 1px dashed rgba(var(--v-theme-primary), .45); border-radius: 8px; }
.config-section-title { font-size: 15px; font-weight: 600; margin-bottom: 12px; }
.config-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.config-value-summary { margin-left: 12px; font-size: 13px; opacity: .65; }
@media (max-width: 800px) { .status-grid { grid-template-columns: repeat(2, 1fr); } .link-page { padding: 12px; } }
@media (max-width: 700px) { .config-grid { grid-template-columns: 1fr; } .config-value-summary { display: none; } }
@media (max-width: 900px) { .inline-config { grid-template-columns: 1fr 1fr; } }
.safety-cell { min-width: 240px; }
.editor-error-list { margin: 4px 0 0 20px; padding: 0; }
.editor-error-list li { margin-bottom: 2px; }
.editor-error-list code { padding: 1px 6px; border-radius: 4px; background: rgba(var(--v-theme-surface-variant), .55); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
.safety-stack { display: flex; flex-direction: column; gap: 14px; padding: 4px 0; }
:deep(.v-table) tbody td { vertical-align: top; padding-top: 14px !important; padding-bottom: 14px !important; }
</style>
