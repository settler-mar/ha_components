import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useHAChangesStore = defineStore('haChanges', () => {
  // Упрощенная структура: { deviceId: { portCode: action } }
  const changes = ref({})

  // Обновить изменение для порта (упрощенная версия)
  const updateChange = (deviceId, portCode, action) => {
    // Инициализируем устройство если его нет
    if (!changes.value[deviceId]) {
      changes.value[deviceId] = {}
    }
    // Если действие null, удаляем изменение
    if (action === null) {
      delete changes.value[deviceId][portCode]
      // Если нет изменений для устройства, удаляем его
      if (Object.keys(changes.value[deviceId]).length === 0) {
        delete changes.value[deviceId]
      }
      return
    }

    // Сохраняем действие
    changes.value[deviceId][portCode] = action
  }

  // Проверить, есть ли изменения для порта
  const hasPortChanges = (deviceId, portCode) => {
    return changes.value[deviceId] && changes.value[deviceId][portCode] !== undefined
  }

  // Получить действие для порта
  const getPortAction = (deviceId, portCode) => {
    return changes.value[deviceId]?.[portCode] || null
  }

  // Проверить, есть ли изменения для устройства
  const hasDeviceChanges = (deviceId) => {
    return changes.value[deviceId] && Object.keys(changes.value[deviceId]).length > 0
  }

  // Получить количество изменений для устройства
  const getDeviceChangesCount = (deviceId) => {
    return changes.value[deviceId] ? Object.keys(changes.value[deviceId]).length : 0
  }

  // Очистить все изменения для устройства
  const clearDeviceChanges = (deviceId) => {
    delete changes.value[deviceId]
  }

  // Очистить все изменения
  const clearAllChanges = () => {
    changes.value = {}
  }

  // Получить все изменения (для отладки)
  const getAllChanges = () => {
    return changes.value
  }

  // Computed properties
  const totalChangesCount = computed(() => {
    let total = 0
    for (const deviceChanges of Object.values(changes.value)) {
      total += Object.keys(deviceChanges).length
    }
    return total
  })

  const hasAnyChanges = computed(() => {
    return Object.keys(changes.value).length > 0
  })

  return {
    // State
    changes,

    // Actions
    updateChange,
    clearDeviceChanges,
    clearAllChanges,

    // Getters
    hasPortChanges,
    getPortAction,
    hasDeviceChanges,
    getDeviceChangesCount,
    getAllChanges,

    // Computed
    totalChangesCount,
    hasAnyChanges
  }
})
