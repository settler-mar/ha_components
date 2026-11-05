<template>
  <v-card variant="outlined" elevation="1">
    <v-card-title class="d-flex align-center justify-space-between">
      <div class="d-flex align-center">
        <v-icon
          class="me-2"
          :color="module.color || 'primary'"
        >
          {{ module.icon || 'mdi-folder' }}
        </v-icon>
        <span>{{ module.name }}</span>
      </div>
      <div>
        <v-btn
          icon
          size="small"
          variant="text"
          @click="$emit('version', module)"
          title="Управление версиями"
        >
          <v-icon>mdi-code-braces</v-icon>
        </v-btn>
        <v-btn
          icon
          size="small"
          variant="text"
          color="error"
          @click="$emit('delete', module)"
          title="Удалить"
        >
          <v-icon>mdi-delete</v-icon>
        </v-btn>
      </div>
    </v-card-title>

    <v-card-text>
      <div v-if="module.description" class="text-body-2 text-grey mb-2">
        {{ module.description }}
      </div>

      <div class="text-caption text-grey mb-1">Версий: {{ module.versions?.length || 0 }}</div>
      <div v-if="module.current_version" class="text-caption text-grey mb-2">
        Текущая версия: <strong>{{ module.current_version }}</strong>
      </div>

      <!-- Визуальные компоненты -->
      <v-divider class="my-2" v-if="hasVisualComponents"></v-divider>
      <div v-if="hasVisualComponents" class="mt-2">
        <div class="text-caption text-grey mb-1">Визуальные компоненты:</div>
        <v-chip
          v-for="component in visualComponents"
          :key="component.name"
          size="x-small"
          variant="tonal"
          color="purple"
          class="me-1 mb-1"
        >
          <v-icon size="12" class="me-1">mdi-palette</v-icon>
          {{ component.name }}
        </v-chip>
      </div>

      <!-- Использование модуля -->
      <v-divider class="my-2" v-if="module.usage && module.usage.length > 0"></v-divider>
      <div v-if="module.usage && module.usage.length > 0" class="mt-2">
        <div class="text-caption text-grey mb-1">Используется в:</div>
        <v-chip
          v-for="usage in module.usage"
          :key="usage.instance_id"
          size="x-small"
          variant="outlined"
          class="me-1 mb-1"
        >
          {{ usage.instance_name }} (v{{ usage.version }})
        </v-chip>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  module: {
    type: Object,
    required: true
  }
})

defineEmits(['delete', 'version'])

// Получаем визуальные компоненты из текущей версии модуля
const visualComponents = computed(() => {
  if (!props.module?.versions) return []
  const currentVersion = props.module.versions.find(v => v.version === props.module.current_version)
  return currentVersion?.visual_components || []
})

const hasVisualComponents = computed(() => {
  return visualComponents.value.length > 0
})
</script>

<style scoped>
</style>

