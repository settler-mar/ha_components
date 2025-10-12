<template>
  <div>
    <!-- Навигационное меню -->
    <v-app-bar density="compact" elevation="1" class="mb-4">
      <v-app-bar-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-home</v-icon>
        My Home Devices
      </v-app-bar-title>
      
      <v-spacer></v-spacer>
      
      <v-btn
        variant="text"
        prepend-icon="mdi-cog"
        to="/system"
        class="mr-2"
      >
        Бэкапы
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
  </div>
</template>

<script setup>
import {ref, computed, onMounted} from 'vue'
import {useTableStore} from '@/store/tables'
import {usePortsStore} from '@/store/portsStore';

import ConnectionCard from '@/components/devices/ConnectionCard.vue'

const store = useTableStore()
const portsStore = usePortsStore()

const devices = computed(() => store.tables.devices?.items || [])
const ports = computed(() => store.tables.ports?.items || [])

const conn = {
  "name": "my home",
  "type": "my_home",
}

const refresh = () => {
  console.log('Refreshing devices and ports...')
  portsStore.loadPorts(true)
  store.loadTableData('devices', true, true)
  // store.loadTableData('ports', true)
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
