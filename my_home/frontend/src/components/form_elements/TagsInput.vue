<template>
  <v-combobox
    :model-value="modelValue"
    :items="allItems"
    :label="label"
    :placeholder="placeholder"
    :density="density"
    :hide-details="hideDetails"
    :disabled="disabled"
    variant="outlined"
    multiple
    chips
    closable-chips
    :delimiters="[',', 'Enter']"
    @update:model-value="handleUpdate"
  >
    <template #chip="{ props: chipProps, item }">
      <v-chip v-bind="chipProps" :color="tagColor(item.raw || item.title)" variant="tonal">
        #{{ String(item.raw || item.title).replace(/^#/, '') }}
      </v-chip>
    </template>
  </v-combobox>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { secureFetch } from '@/services/fetch'
import { normalizeTag, tagColor } from '@/utils/tags'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  items: { type: Array, default: null },
  label: { type: String, default: 'Хештеги' },
  placeholder: { type: String, default: 'Введите тег и нажмите Enter или запятую' },
  density: { type: String, default: 'compact' },
  hideDetails: { type: Boolean, default: true },
  disabled: { type: Boolean, default: false },
  autoload: { type: Boolean, default: true }
})
const emit = defineEmits(['update:modelValue'])

const loadedItems = ref([])
const allItems = computed(() => props.items ?? loadedItems.value)

const handleUpdate = values => {
  const normalized = [...new Set((values || []).map(normalizeTag).filter(Boolean))]
  const current = (props.modelValue || []).map(normalizeTag).filter(Boolean)
  if (normalized.join('|') !== current.join('|')) emit('update:modelValue', normalized)
}

const loadTags = async () => {
  try {
    const response = await secureFetch('/api/virtual-devices')
    const data = await response.json()
    loadedItems.value = (data.tags || []).map(normalizeTag).filter(Boolean)
  } catch (error) {
    console.warn('Failed to load virtual device tags:', error)
  }
}

onMounted(() => {
  if (props.items == null && props.autoload) loadTags()
})
</script>
