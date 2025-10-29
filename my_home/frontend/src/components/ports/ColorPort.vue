<template>
  <div class="color-port" :class="{ 'read-only': isReadOnly }">
    <!-- Цветовой индикатор -->
    <div 
      class="color-display"
      :style="{ backgroundColor: displayColor }"
      @click="!isReadOnly && openColorPicker()"
    >
      <div class="color-overlay" v-if="!isValidColor"></div>
      <span v-if="!isValidColor" class="invalid-text">N/A</span>
    </div>
    
    <!-- Цветовое значение -->
    <div class="color-info">
      <div class="color-value">{{ formattedColor }}</div>
      <div v-if="colorName" class="color-name">{{ colorName }}</div>
    </div>
    
    <!-- Цветовая палитра для out портов -->
    <div v-if="!isReadOnly" class="color-controls">
      <input
        v-model="colorInput"
        type="color"
        @change="updateColor"
        class="color-picker"
        ref="colorPickerRef"
      />
      
      <!-- Предустановленные цвета -->
      <div class="preset-colors">
        <button
          v-for="preset in presetColors"
          :key="preset.value"
          class="preset-color"
          :style="{ backgroundColor: preset.color }"
          :title="preset.name"
          @click="setPresetColor(preset.value)"
        ></button>
      </div>
      
      <!-- RGB/HEX ввод -->
      <div class="color-input-group">
        <input
          v-model="hexInput"
          type="text"
          placeholder="#FFFFFF"
          @change="updateFromHex"
          @keyup.enter="updateFromHex"
          class="hex-input"
          maxlength="7"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, defineProps, defineEmits } from 'vue'

const props = defineProps({
  port: {
    type: Object,
    required: true
  },
  value: {
    type: [String, Number],
    default: '#000000'
  }
})

const emit = defineEmits(['update'])

// Reactive data
const colorInput = ref('#000000')
const hexInput = ref('#000000')
const colorPickerRef = ref(null)

// Computed properties
const isReadOnly = computed(() => {
  return props.port.type?.startsWith('in.') || props.port.direction === 'in'
})

const displayColor = computed(() => {
  return normalizeColor(props.value) || '#000000'
})

const formattedColor = computed(() => {
  const color = normalizeColor(props.value)
  return color ? color.toUpperCase() : 'Invalid'
})

const isValidColor = computed(() => {
  return !!normalizeColor(props.value)
})

const colorName = computed(() => {
  const color = normalizeColor(props.value)
  if (!color) return null
  
  const name = getColorName(color)
  return name !== color ? name : null
})

const presetColors = computed(() => [
  { name: 'Красный', color: '#FF0000', value: '#FF0000' },
  { name: 'Зеленый', color: '#00FF00', value: '#00FF00' },
  { name: 'Синий', color: '#0000FF', value: '#0000FF' },
  { name: 'Желтый', color: '#FFFF00', value: '#FFFF00' },
  { name: 'Пурпурный', color: '#FF00FF', value: '#FF00FF' },
  { name: 'Голубой', color: '#00FFFF', value: '#00FFFF' },
  { name: 'Белый', color: '#FFFFFF', value: '#FFFFFF' },
  { name: 'Черный', color: '#000000', value: '#000000' }
])

// Methods
const normalizeColor = (color) => {
  if (!color) return null
  
  let colorStr = color.toString().trim()
  
  // Если это число, конвертируем в hex
  if (/^\d+$/.test(colorStr)) {
    const num = parseInt(colorStr)
    colorStr = '#' + num.toString(16).padStart(6, '0')
  }
  
  // Добавляем # если нет
  if (!/^#/.test(colorStr)) {
    colorStr = '#' + colorStr
  }
  
  // Проверяем валидность hex цвета
  if (/^#[0-9A-Fa-f]{6}$/.test(colorStr)) {
    return colorStr.toUpperCase()
  }
  
  return null
}

const getColorName = (hex) => {
  const colors = {
    '#FF0000': 'Красный',
    '#00FF00': 'Зеленый',
    '#0000FF': 'Синий',
    '#FFFF00': 'Желтый',
    '#FF00FF': 'Пурпурный',
    '#00FFFF': 'Голубой',
    '#FFFFFF': 'Белый',
    '#000000': 'Черный',
    '#FFA500': 'Оранжевый',
    '#800080': 'Фиолетовый',
    '#FFC0CB': 'Розовый',
    '#A52A2A': 'Коричневый',
    '#808080': 'Серый'
  }
  
  return colors[hex] || hex
}

const openColorPicker = () => {
  if (colorPickerRef.value) {
    colorPickerRef.value.click()
  }
}

const updateColor = () => {
  emit('update', props.port.code, colorInput.value)
}

const setPresetColor = (color) => {
  colorInput.value = color
  hexInput.value = color
  emit('update', props.port.code, color)
}

const updateFromHex = () => {
  let hex = hexInput.value.trim()
  if (!hex.startsWith('#')) {
    hex = '#' + hex
  }
  
  if (/^#[0-9A-Fa-f]{6}$/.test(hex)) {
    colorInput.value = hex
    emit('update', props.port.code, hex)
  }
}

// Watchers
watch(() => props.value, (newValue) => {
  const normalized = normalizeColor(newValue)
  if (normalized) {
    colorInput.value = normalized
    hexInput.value = normalized
  }
}, { immediate: true })
</script>

<style scoped>
.color-port {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  min-width: 120px;
}

.color-port.read-only {
  background: rgba(255, 255, 255, 0.02);
}

.color-display {
  width: 60px;
  height: 40px;
  border-radius: 6px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  cursor: pointer;
  transition: border-color 0.2s ease, transform 0.2s ease;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.color-display:hover {
  border-color: rgba(255, 255, 255, 0.4);
  transform: scale(1.05);
}

.color-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: repeating-linear-gradient(
    45deg,
    transparent,
    transparent 4px,
    rgba(255, 255, 255, 0.1) 4px,
    rgba(255, 255, 255, 0.1) 8px
  );
  border-radius: 4px;
}

.invalid-text {
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.8em;
  font-weight: bold;
}

.color-info {
  text-align: center;
  gap: 2px;
}

.color-value {
  font-size: 0.9em;
  font-weight: 500;
  color: #ffffff;
  font-family: monospace;
}

.color-name {
  font-size: 0.75em;
  color: rgba(255, 255, 255, 0.7);
}

.color-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.color-picker {
  display: none;
}

.preset-colors {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
}

.preset-color {
  width: 20px;
  height: 20px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.preset-color:hover {
  transform: scale(1.1);
  border-color: rgba(255, 255, 255, 0.4);
}

.color-input-group {
  display: flex;
  gap: 4px;
}

.hex-input {
  flex: 1;
  padding: 4px 6px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  font-size: 0.8em;
  font-family: monospace;
  text-transform: uppercase;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.hex-input:focus {
  outline: none;
  border-color: #68b700;
  background: rgba(255, 255, 255, 0.15);
}

.hex-input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

/* Темная тема */
@media (prefers-color-scheme: dark) {
  .color-port {
    background: rgba(255, 255, 255, 0.08);
  }
  
  .color-port.read-only {
    background: rgba(255, 255, 255, 0.04);
  }
}
</style>







