<template>
  <v-card class="mb-12" elevation="2">
    <v-toolbar density="compact" :elevation="2" border>
      <template v-slot:prepend>
        <span class="mr-2">{{ connectionIcon }}</span>
      </template>

      {{ connection.name }}
      <v-btn
      >
        <v-icon icon="mdi-refresh" @click="refresh" title="Обновить"/>
      </v-btn>

      <ActionHandler
        :actions="actions"
        :haConfigMode="haConfigMode"
        :haChangesCount="totalHAChangesCount"
        :hasHAChanges="hasHAChanges"
        :devices="devices"
        @toggle-ha-config="toggleHAConfig"
      />
    </v-toolbar>

    <v-card-text>
      <v-row>
        <v-col
          cols="12"
          xs="12"
          sm="12"
          md="6"
          lg="4"
          xl="3"
          v-for="device in devices || []"
          :key="device.id"
        >
          <DeviceCard
            :device="device"
            :readonly="readonly"
            :ha-config-mode="haConfigMode"
            @edit="editDevice"
            @toggle-ha-config="toggleHAConfig"
            @device-updated="handleDeviceUpdate"
          />
        </v-col>
        <v-col
          v-if="!devices?.length"
          cols="12"
          class="text-center text-grey"
        >
          Нет устройств в этом соединении
        </v-col>
      </v-row>
    </v-card-text>

    <UniversalDialog
      v-model:show="addDeviceDialog"
      :table="'devices'"
      :item="connectionData"
      :custom_params="devicesParams"
      @save="onDeviceAdded"
    />
  </v-card>
</template>

<script setup>
import {ref, computed} from 'vue'
import DeviceCard from '@/components/devices/DeviceCard.vue'
import DelButton from '@/components/UI/DelButton.vue'
import UniversalDialog from '@/components/devices/UniversalDialog.vue'
import ActionHandler from '@/components/devices/ActionHandler.vue'
import { useHAChangesStore } from '@/store/haChangesStore'

const props = defineProps({
  connection: Object,
  devices: Array,
  readonly: Boolean,
})

const emit = defineEmits(['edit', 'deleted', 'refresh', 'action', 'device-updated'])

const addDeviceDialog = ref(false)
const connectionData = ref({})
const haConfigMode = ref(false)

// Initialize HA changes store
const haChangesStore = useHAChangesStore()


const connectionDef = computed(() => {
  return {}
})

const connectionIcon = computed(() => {
  return connectionDef.value?.icon || '🔌'
})

// Подсчет изменений HA для всех устройств в соединении
const totalHAChangesCount = computed(() => {
  if (!props.devices) return 0
  let total = 0
  props.devices.forEach(device => {
    total += haChangesStore.getDeviceChangesCount(device.id)
  })
  return total
})

// Проверка, есть ли изменения HA в соединении
const hasHAChanges = computed(() => {
  return totalHAChangesCount.value > 0
})


const devicesParams = {
  'code': {
    'readonly': true,
  },
  'ha_integration_enabled': {
    'name': 'ha_integration_enabled',
    'type': 'boolean',
    'label': 'Интеграция с Home Assistant',
    'description': 'Включить интеграцию с Home Assistant',
    'default': true
  },
  'ha_entity_prefix': {
    'name': 'ha_entity_prefix',
    'type': 'text',
    'label': 'Префикс сущностей HA',
    'description': 'Префикс для всех сущностей этого устройства в Home Assistant',
    'default': null
  },
  'ha_publish_device_online': {
    'name': 'ha_publish_device_online',
    'type': 'boolean',
    'label': 'Публиковать статус устройства',
    'description': 'Создаёт сущность для отслеживания онлайн статуса устройства',
    'default': true
  },
  'model': {
    'readonly': true,
  },
  'vendor': {
    'readonly': true,
  },
  'type': {
    'readonly': true,
  },
  'params.backup_config': {
    'type': 'bool',
    'default': true,
    'description': 'Сохранять конфигурацию',
  },
  'params.save_logs': {
    'type': 'bool',
    'default': true,
    'description': 'Сохранять логи',
  },
  'params.remove_logs': {
    'type': 'bool',
    'default': true,
    'description': 'Удалять логи после сохранения',
  },
  'params.log_save_method': {
    'type': 'list',
    'default': 'gsheet',
    'description': 'Метод сохранения логов',
    'options': {
      'local_save': 'На сервере',
      'gsheet': 'Google Sheets',
    },
  },
  'params.ip': {
    'type': 'str',
    'default': null,
    'description': 'IP адрес устройства',
    'readonly': true,
  },
  'params.mac': {
    'type': 'str',
    'default': null,
    'description': 'MAC адрес устройства',
    'readonly': true,
  },
  'params.ssid': {
    'type': 'str',
    'default': null,
    'description': 'SSID устройства',
    'readonly': true,
  },
  'params.flash_date': {
    'type': 'str',
    'default': null,
    'description': 'Дата прошивки устройства',
    'readonly': true,
  },
  'params.version': {
    'type': 'str',
    'default': null,
    'description': 'Версия прошивки устройства',
    'readonly': true,
  },
}

const actions = [{
  "id": "ha-config",
  "name": "НАСТРОЙКА HA",
  "type": "request",
  "scope": "connection",
  "icon": "mdi-home-assistant",
  "endpoint": "/api/ha/toggle-config",
  "method": "POST",
  "input": {
    "enabled": {
      "name": "enabled",
      "type": "boolean",
      "description": "Включить режим настройки HA",
      "required": true,
      "default": false
    }
  }
}, {
  "id": "myhome-devices",
  "name": "Устройства MyHome",
  "type": "table_modal",
  "scope": "connection",
  "icon": "mdi-router-wireless",
  "endpoint": "/api/live/scan",
  "structure": [
    {"name": "ip", "title": "IP адрес"}, {"name": "mac", "title": "MAC адрес"}, {
      "name": "name",
      "title": "Имя"
    }, {"name": "version", "title": "Версия"}, {"name": "chip_id", "title": "Chip ID"}, {
      "name": "flash_chip_revision",
      "title": "Тип"
    }, {"name": "flash_chip_speed", "title": "Скорость"}, {
      "name": "flash_date",
      "title": "Дата прошивки"
    }, {"name": "config_name", "title": "Имя конфигурации"}, {
      "name": "flash_counter",
      "title": "Счетчик прошивок"
    }, {"name": "flash_heap", "title": "Память"}, {"name": "fs_name", "title": "Файловая система"}, {
      "name": "run_time",
      "title": "Время работы"
    }, {"name": "ssid", "title": "SSID"}, {"name": "rssi", "title": "RSSI"}],
  "actions": [
    {
      "name": "Добавить",
      "type": "request",
      "method": "GET",
      "endpoint": "/api/live/add/{ip}",
      "update_after": "table.devices|table.ports",
      "icon": "mdi-plus"
    }, {
      "name": "Заменить",
      "type": "request",
      "method": "GET",
      "endpoint": "/api/live/replace/{ip}/{device_id}",
      "update_after": "table.devices|table.ports",
      "icon": "mdi-unfold-more-vertical",
      "input": {
        "device_id": {
          "name": "device_id",
          "type": "text",
          "description": "ID устройства",
          "required": true,
          "default": null
        }
      }
    }],
  "refreshable": true
}, {
  "id": "add-device-by-ip",
  "name": "Добавить устройство по IP",
  "type": "request",
  "endpoint": "/api/live/add/{ip}",
  "method": "GET",
  "icon": "mdi-plus",
  "scope": "connection",
  "input": {
    "ip": {
      "name": "ip",
      "type": "text",
      "description": "IP адрес устройства",
      "required": true,
      "default": null
    }
  },
  "update_after": "table.devices|table.ports"
}]


function onDeviceAdded(deviceData) {
  addDeviceDialog.value = false

  // Сохраняем HA настройки в params
  if (deviceData.ha_integration_enabled !== undefined ||
      deviceData.ha_entity_prefix !== undefined ||
      deviceData.ha_publish_device_online !== undefined) {

    const haSettings = {
      enabled: deviceData.ha_integration_enabled ?? true,
      entityPrefix: deviceData.ha_entity_prefix || deviceData.name || 'device',
      publishDeviceOnline: deviceData.ha_publish_device_online ?? true
    }

    // Обновляем params устройства
    deviceData.params = deviceData.params || {}
    deviceData.params.ha_integration = haSettings

    // Удаляем временные поля
    delete deviceData.ha_integration_enabled
    delete deviceData.ha_entity_prefix
    delete deviceData.ha_publish_device_online
  }

  emit('refresh')
}


function openDialog(device) {
  addDeviceDialog.value = true
  // convert device to a new object
  // {'id': null, 'name': '', 'params': {'a':12}} => {'id': null, 'name': '', 'params.a': 12, 'connection_id': connection.id}

  const deviceData = {...device}

  // Обрабатываем HA настройки
  const haSettings = device.params?.ha_integration || {}
  deviceData.ha_integration_enabled = haSettings.enabled ?? true
  deviceData.ha_entity_prefix = haSettings.entityPrefix || device.name || 'device'
  deviceData.ha_publish_device_online = haSettings.publishDeviceOnline ?? true

  connectionData.value = deviceData
}

function editDevice(device) {
  openDialog(device)
}

function handleAction(action) {
  const scopeData = {connection_id: props.connection.id}
  emit('action', {action, scopeData})
}

function refresh() {
  emit('refresh')
}

function toggleHAConfig() {
  haConfigMode.value = !haConfigMode.value
}

function handleDeviceUpdate(updatedDevice) {
  // Пробрасываем событие обновления устройства выше
  emit('device-updated', updatedDevice)
}
</script>

<style scoped>
/* Адаптивные стили для ConnectionCard */
@media (max-width: 600px) {
  .v-card-text {
    padding: 8px;
  }

  .v-row {
    margin: -4px;
  }

  .v-col {
    padding: 4px;
  }
}

@media (max-width: 400px) {
  .v-card-text {
    padding: 4px;
  }

  .v-row {
    margin: -2px;
  }

  .v-col {
    padding: 2px;
  }
}
</style>
