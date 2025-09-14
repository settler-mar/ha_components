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
      />
    </v-toolbar>

    <v-card-text>
      <v-row>
        <v-col
          cols="12"
          sm="6"
          md="4"
          v-for="device in devices || []"
          :key="device.id"
        >
          <DeviceCard :device="device" :readonly="readonly" @edit="editDevice"/>
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

const props = defineProps({
  connection: Object,
  devices: Array,
  readonly: Boolean,
})

const emit = defineEmits(['edit', 'deleted', 'refresh', 'action'])

const addDeviceDialog = ref(false)
const connectionData = ref({})


const connectionDef = computed(() => {
  return {}
})

const connectionIcon = computed(() => {
  return connectionDef.value?.icon || '🔌'
})


const devicesParams = {
  'code': {
    'readonly': true,
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


function onDeviceAdded() {
  addDeviceDialog.value = false
  emit('refresh')
}


function openDialog(device) {
  addDeviceDialog.value = true
  // convert device to a new object
  // {'id': null, 'name': '', 'params': {'a':12}} => {'id': null, 'name': '', 'params.a': 12, 'connection_id': connection.id}

  connectionData.value = {...device}
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
</script>
