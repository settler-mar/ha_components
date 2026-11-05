<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon class="me-2">mdi-information</v-icon>
      Информация
    </v-card-title>

    <v-card-text>
      <div class="mb-4">
        <div class="text-caption text-grey mb-1">Всего источников</div>
        <div class="text-h6">{{ sources.length }}</div>
      </div>

      <div class="mb-4">
        <div class="text-caption text-grey mb-1">Активных источников</div>
        <div class="text-h6">{{ activeSourcesCount }}</div>
      </div>

      <v-divider class="my-4"></v-divider>

      <div class="text-caption text-grey mb-2">Источники по приоритету:</div>
      <v-list density="compact">
        <v-list-item
          v-for="source in sortedSources"
          :key="source.id"
          class="px-0"
        >
          <template v-slot:prepend>
            <v-icon
              :color="source.color || 'primary'"
              size="small"
            >
              mdi-circle
            </v-icon>
          </template>
          <v-list-item-title>
            {{ source.name }}
          </v-list-item-title>
          <v-list-item-subtitle>
            Приоритет: {{ source.priority || 0 }} | {{ source.power || 0 }} W
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  sources: {
    type: Array,
    default: () => []
  },
  output: {
    type: Object,
    default: () => ({})
  }
})

const activeSourcesCount = computed(() => {
  return props.sources.filter(s => s.active).length
})

const sortedSources = computed(() => {
  return [...props.sources].sort((a, b) => {
    const priorityA = a.priority || 0
    const priorityB = b.priority || 0
    return priorityB - priorityA
  })
})
</script>

<style scoped>
</style>



