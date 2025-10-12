<template>
  <div class="ports-settings-section">
    <!-- Заголовок -->
    <div class="section-header mb-4">
      <h3 class="text-h6 mb-2">
        <v-icon class="me-2">mdi-cog</v-icon>
        Настройка портов устройства
      </h3>
      <p class="text-body-2 text-grey">
        Управление параметрами портов, публикацией в Home Assistant и настройками логирования
      </p>
    </div>

    <!-- Единая вкладка настроек портов -->
    <UnifiedPortsTab 
      :device-id="deviceId"
      :device-data="deviceData"
      :ports-data="portsData"
      :logs-config="logsConfig"
      @update-port-param="$emit('update-port-param', $event)"
      @update-ha-settings="$emit('update-ha-settings', $event)"
      @update-favorite-ports="$emit('update-favorite-ports', $event)"
      @update-logs-config="$emit('update-logs-config', $event)"
      @notification="$emit('notification', $event)"
    />
  </div>
</template>

<script setup>
import UnifiedPortsTab from './tabs/UnifiedPortsTab.vue'

const props = defineProps({
  deviceId: {
    type: Number,
    required: true
  },
  deviceData: {
    type: Object,
    default: () => ({})
  },
  portsData: {
    type: Array,
    default: () => []
  },
  logsConfig: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits([
  'update-port-param',
  'update-ha-settings',
  'update-favorite-ports',
  'update-logs-config',
  'notification'
])
</script>

<style scoped>
.ports-settings-section {
  padding: 16px 0;
}

.section-header {
  border-bottom: 1px solid #e0e0e0;
  padding-bottom: 16px;
}

.section-header h3 {
  color: #1976d2;
  font-weight: 500;
}

.section-header p {
  margin: 0;
}
</style>
