<template>
  <div>
    <div v-for="port in ports" :key="port.name" class="mb-3">
      <div class="text-body-2 font-weight-medium mb-1">
        {{ port.name }}
        <v-chip v-if="port.required" size="x-small" color="error" variant="tonal" class="ms-1">
          Обязательный
        </v-chip>
      </div>
      <div v-if="port.description" class="text-caption text-grey mb-1">
        {{ port.description }}
      </div>
      <EntitySelect
        v-model="portValues[port.name]"
        :label="port.name"
        @update:model-value="updateValue"
      />
    </div>
    <div v-if="ports.length === 0" class="text-caption text-grey">
      Нет портов HA
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import EntitySelect from '@/components/EntitySelect.vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({})
  },
  ports: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue'])

const portValues = ref({})

watch(() => props.modelValue, (newVal) => {
  portValues.value = { ...(newVal || {}) }
}, { immediate: true, deep: true })

const updateValue = () => {
  emit('update:modelValue', { ...portValues.value })
}
</script>

<style scoped>
</style>


