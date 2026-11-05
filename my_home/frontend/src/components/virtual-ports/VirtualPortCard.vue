<template>
  <v-card variant="outlined" elevation="1">
    <v-card-title class="d-flex align-center justify-space-between">
      <div class="d-flex align-center">
        <v-icon
          class="me-2"
          color="primary"
        >
          {{ port.icon || 'mdi-network' }}
        </v-icon>
        <span>{{ port.name }}</span>
      </div>
      <div>
        <v-btn
          icon
          size="small"
          variant="text"
          @click="$emit('edit', port)"
          title="Редактировать"
        >
          <v-icon>mdi-pencil</v-icon>
        </v-btn>
        <v-btn
          icon
          size="small"
          variant="text"
          color="error"
          @click="$emit('delete', port)"
          title="Удалить"
        >
          <v-icon>mdi-delete</v-icon>
        </v-btn>
      </div>
    </v-card-title>

    <v-card-text>
      <div v-if="port.description" class="text-body-2 text-grey mb-2">
        {{ port.description }}
      </div>

      <div v-if="port.entity_id" class="text-caption text-grey mb-1">
        Entity ID: <code>{{ port.entity_id }}</code>
      </div>

      <div v-if="port.type" class="text-caption text-grey mb-1">
        Тип: <code>{{ port.type }}</code>
      </div>

      <div v-if="port.device_class" class="text-caption text-grey mb-1">
        Класс устройства: {{ port.device_class }}
      </div>

      <div v-if="port.unit_of_measurement || port.unit" class="text-caption text-grey mb-1">
        Единица: {{ port.unit_of_measurement || port.unit }}
      </div>

      <v-chip
        v-if="port.value !== undefined && port.value !== null"
        color="primary"
        size="x-small"
        class="mt-2"
      >
        Значение: {{ port.value }}
      </v-chip>
    </v-card-text>
  </v-card>
</template>

<script setup>
defineProps({
  port: {
    type: Object,
    required: true
  }
})

defineEmits(['edit', 'delete'])
</script>

<style scoped>
</style>

