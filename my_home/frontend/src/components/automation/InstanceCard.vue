<template>
  <v-card variant="outlined" elevation="1">
    <v-card-title class="d-flex align-center justify-space-between">
      <div class="d-flex align-center">
        <v-icon
          class="me-2"
          :color="instance.active ? 'success' : 'grey'"
        >
          {{ instance.active ? 'mdi-play-circle' : 'mdi-pause-circle' }}
        </v-icon>
        <span>{{ instance.name }}</span>
        <v-chip
          size="x-small"
          :color="instance.active ? 'success' : 'grey'"
          variant="tonal"
          class="ms-2"
        >
          {{ instance.active ? 'Активна' : 'Неактивна' }}
        </v-chip>
      </div>
      <div>
        <v-btn
          icon
          size="small"
          variant="text"
          @click="$emit('edit', instance)"
          title="Редактировать"
        >
          <v-icon>mdi-pencil</v-icon>
        </v-btn>
        <v-btn
          icon
          size="small"
          variant="text"
          color="error"
          @click="$emit('delete', instance)"
          title="Удалить"
        >
          <v-icon>mdi-delete</v-icon>
        </v-btn>
      </div>
    </v-card-title>

    <v-card-text>
      <div v-if="instance.description" class="text-body-2 text-grey mb-2">
        {{ instance.description }}
      </div>

      <div v-if="moduleInfo" class="mb-2">
        <div class="text-caption text-grey mb-1">Модуль:</div>
        <div class="text-body-2">
          <v-icon size="small" class="me-1">{{ moduleInfo.icon || 'mdi-folder' }}</v-icon>
          {{ moduleInfo.name }}
          <v-chip size="x-small" variant="outlined" class="ms-1">
            v{{ instance.module_version }}
          </v-chip>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  instance: {
    type: Object,
    required: true
  },
  modules: {
    type: Array,
    default: () => []
  }
})

const moduleInfo = computed(() => {
  return props.modules.find(m => m.id === props.instance.module_id)
})

defineEmits(['edit', 'delete'])
</script>

<style scoped>
</style>


