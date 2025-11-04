<template>
  <div>
    <!-- Навигационное меню -->
    <v-app-bar density="compact" elevation="1" class="mb-4">
      <v-app-bar-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-home</v-icon>
        My Home
      </v-app-bar-title>

      <v-spacer></v-spacer>

      <v-btn
        variant="text"
        prepend-icon="mdi-cog-box"
        @click="showConfigDialog = true"
        class="mr-2"
      >
        Настройки
      </v-btn>

      <v-btn
        variant="text"
        prepend-icon="mdi-refresh"
        @click="refresh"
      >
        Обновить
      </v-btn>
    </v-app-bar>

    <!-- Основной контент -->
    <ConnectionCard :connection="conn" :readonly="false" :devices="devices" @refresh="refresh"/>

    <!-- Диалог конфигурации аддона -->
    <AddonConfigDialog
      v-model="showConfigDialog"
      @saved="handleConfigSaved"
    />
  </div>
</template>

<script setup>
import {ref, computed, onMounted} from 'vue'
import {useTableStore} from '@/store/tables'
import {usePortsStore} from '@/store/portsStore'
import useMessageStore from '@/store/messages'

import ConnectionCard from '@/components/devices/ConnectionCard.vue'
import AddonConfigDialog from '@/components/AddonConfigDialog.vue'

const store = useTableStore()
const portsStore = usePortsStore()
const messageStore = useMessageStore()

const devices = computed(() => store.tables.devices?.items || [])
const ports = computed(() => store.tables.ports?.items || [])
const showConfigDialog = ref(false)

const conn = {
  "name": "Devices",
  "type": "my_home",
}

const refresh = () => {
  console.log('Refreshing devices and ports...')
  portsStore.loadPorts(true)
  store.loadTableData('devices', true, true)
  // store.loadTableData('ports', true)
}

const handleConfigSaved = () => {
  messageStore.showInfo('Конфигурация аддона сохранена. Может потребоваться перезапуск аддона.')
}

onMounted(() => {
  refresh()
})

</script>

<style>
.btn-add-connection {
  margin-bottom: 16px;
  margin-top: -40px;
}
</style>
