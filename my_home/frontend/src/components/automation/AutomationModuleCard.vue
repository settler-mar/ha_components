<template>
  <v-card elevation="2" class="module-card">
    <v-card-title class="d-flex align-center justify-space-between">
      <div class="d-flex align-center">
        <v-icon class="me-2" :color="module.enabled ? 'success' : 'grey'">
          {{ module.enabled ? 'mdi-play-circle' : 'mdi-pause-circle' }}
        </v-icon>
        <span>{{ module.name }}</span>
      </div>
      <v-chip
        size="x-small"
        :color="module.enabled ? 'success' : 'grey'"
        variant="tonal"
      >
        {{ module.enabled ? 'Активен' : 'Остановлен' }}
      </v-chip>
    </v-card-title>

    <v-card-text>
      <div class="text-caption text-grey mb-2">
        {{ module.description || 'Без описания' }}
      </div>

      <div class="module-info">
        <div class="info-item">
          <v-icon size="16" class="me-1">mdi-arrow-down</v-icon>
          <span class="text-caption">Входы: {{ module.inputs?.length || 0 }}</span>
        </div>
        <div class="info-item">
          <v-icon size="16" class="me-1">mdi-arrow-up</v-icon>
          <span class="text-caption">Выходы: {{ module.outputs?.length || 0 }}</span>
        </div>
        <div class="info-item">
          <v-icon size="16" class="me-1">mdi-home-assistant</v-icon>
          <span class="text-caption">Порты HA: {{ module.haPorts?.length || 0 }}</span>
        </div>
      </div>
    </v-card-text>

    <v-card-actions>
      <v-spacer></v-spacer>
      <v-btn
        icon
        size="small"
        @click="$emit('toggle', module)"
        :title="module.enabled ? 'Остановить' : 'Запустить'"
      >
        <v-icon>{{ module.enabled ? 'mdi-pause' : 'mdi-play' }}</v-icon>
      </v-btn>
      <v-btn
        icon
        size="small"
        @click="$emit('edit', module)"
        title="Редактировать"
      >
        <v-icon>mdi-pencil</v-icon>
      </v-btn>
      <v-btn
        icon
        size="small"
        color="error"
        @click="$emit('delete', module)"
        title="Удалить"
      >
        <v-icon>mdi-delete</v-icon>
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
defineProps({
  module: {
    type: Object,
    required: true
  }
})

defineEmits(['edit', 'delete', 'toggle'])
</script>

<style scoped>
.module-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.module-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-item {
  display: flex;
  align-items: center;
}
</style>



