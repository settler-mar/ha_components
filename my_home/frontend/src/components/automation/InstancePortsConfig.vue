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
        v-if="!port.is_list"
        v-model="portValues[port.name]"
        :label="port.name"
        @update:model-value="updateValue"
      />
      <div v-else>
        <v-btn
          variant="outlined"
          size="small"
          prepend-icon="mdi-plus"
          @click="addPortItem(port.name)"
          class="mb-2"
        >
          Добавить {{ port.name }}
        </v-btn>
        <div v-for="(item, index) in (portValues[port.name] || [])" :key="index" class="d-flex align-center mb-2">
          <EntitySelect
            v-model="portValues[port.name][index]"
            :label="port.name"
            @update:model-value="updateValue"
            class="flex-grow-1"
          />
          <v-btn
            icon
            size="small"
            color="error"
            @click="removePortItem(port.name, index)"
            class="ml-2"
          >
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </div>
      </div>
    </div>
    <div v-if="ports.length === 0" class="text-caption text-grey">
      Нет портов
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

const addPortItem = (portName) => {
  if (!portValues.value[portName]) {
    portValues.value[portName] = []
  }
  portValues.value[portName].push(null)
  updateValue()
}

const removePortItem = (portName, index) => {
  portValues.value[portName].splice(index, 1)
  updateValue()
}
</script>

<style scoped>
</style>


