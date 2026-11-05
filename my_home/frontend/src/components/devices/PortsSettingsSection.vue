<template>
  <div class="ports-settings-section">
    <!-- Заголовок -->
    <div class="section-header d-flex align-center mb-2">
      <v-icon size="20" class="me-2" color="primary">mdi-tune</v-icon>
      <span class="text-subtitle-1">Параметры портов</span>
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
  padding: 4px 0;
}

.section-header {
  border-bottom: 1px solid #e0e0e0;
  padding-bottom: 6px;
}
</style>
