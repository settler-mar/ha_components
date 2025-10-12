<template>
  <div class="compact-color-port">
    <!-- Для входных портов - только цветовой индикатор -->
    <div v-if="isReadOnly" class="color-display-only">
      <div 
        class="color-preview"
        :style="{ backgroundColor: displayColor }"
      ></div>
    </div>
    
    <!-- Для выходных портов - компактный цветовой слайдер -->
    <div v-else class="color-control">
      <div 
        class="color-current"
        :style="{ backgroundColor: displayColor }"
        :title="`Цвет: ${colorValue}`"
      ></div>
      
      <input
        v-model.number="colorValue"
        type="range"
        min="0"
        max="256"
        step="1"
        @input="updateColorFromNumber"
        class="color-slider"
      />
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
    default: 0
  },
})

const emit = defineEmits(['update'])

// Reactive data
const colorValue = ref(0)

// Computed properties
const isReadOnly = computed(() => {
  return props.port.type?.startsWith('in.') || props.port.direction === 'in'
})

const displayColor = computed(() => {
  return colFromNum(colorValue.value)
})

// Methods - используем алгоритм из ESP UI
const colFromNum = (pos) => {
  const toHex = (a) => {
    return (a < 16 ? '0' : '') + a.toString(16)
  }
  
  let r = 0, g = 0, b = 0
  
  if (pos == 256) {
    r = 255
    g = 255
    b = 255
  } else {
    pos = pos % 255
    pos = pos * 6
    
    if (pos <= 255) {
      b = pos
      r = 255
    } else if (pos < 510) {
      pos = 510 - pos
      r = pos
      b = 255
    } else if (pos < 765) {
      pos = pos - 510
      g = pos
      b = 255
    } else if (pos < 1020) {
      pos = 1020 - pos
      b = pos
      g = 255
    } else if (pos < 1275) {
      pos = pos - 1020
      r = pos
      g = 255
    } else {
      pos = 1530 - pos
      g = pos
      r = 255
    }
  }
  
  return ('#' + toHex(r) + toHex(g) + toHex(b)).toUpperCase()
}

const updateColorFromNumber = () => {
  emit('update', props.port.code, colorValue.value)
}

// Watchers
watch(() => props.value, (newValue) => {
  // Конвертируем значение в число для слайдера
  const numValue = parseInt(newValue) || 0
  colorValue.value = Math.max(0, Math.min(256, numValue))
}, { immediate: true })
</script>

<style scoped>
.compact-color-port {
  display: flex;
  align-items: center;
  min-width: 80px;
}

.color-display-only {
  display: flex;
  align-items: center;
  justify-content: center;
}

.color-preview {
  width: 20px;
  height: 20px;
  border-radius: 3px;
  border: 1px solid #ddd;
}

.color-control {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 110px; /* Фиксированная ширина: 20px (цвет) + 6px (gap) + 80px (слайдер) + 4px (отступ) */
}

.color-current {
  width: 20px;
  height: 20px;
  border-radius: 3px;
  border: 1px solid #ddd;
  flex-shrink: 0;
}

.color-slider {
  width: 80px; /* Фиксированная ширина как у других слайдеров */
  height: 4px;
  background: linear-gradient(
    to right,
    #FF0000 0%,     /* 0: Красный (r=255, g=0, b=0) */
    #FF00FF 16.7%,  /* ~42: Красный+Синий (r=255, g=0, b=255) */
    #0000FF 33.3%,  /* ~85: Синий (r=0, g=0, b=255) */
    #00FFFF 50%,    /* ~128: Синий+Зеленый (r=0, g=255, b=255) */
    #00FF00 66.7%,  /* ~170: Зеленый (r=0, g=255, b=0) */
    #FFFF00 83.3%,  /* ~213: Зеленый+Красный (r=255, g=255, b=0) */
    #FF0000 99.6%,  /* ~255: Красный (r=255, g=0, b=0) */
    #FFFFFF 100%    /* 256: Белый (r=255, g=255, b=255) */
  );
  border-radius: 2px;
  outline: none;
  cursor: pointer;
  appearance: none;
}

.color-slider::-webkit-slider-thumb {
  appearance: none;
  width: 12px;
  height: 12px;
  background: #333;
  border: 2px solid #fff;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
  transition: all 0.2s ease;
}

.color-slider::-webkit-slider-thumb:hover {
  background: #000;
  transform: scale(1.2);
  box-shadow: 0 3px 6px rgba(0, 0, 0, 0.5);
}

.color-slider::-moz-range-thumb {
  width: 12px;
  height: 12px;
  background: #333;
  border: 2px solid #fff;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
  transition: all 0.2s ease;
}

.color-slider::-moz-range-thumb:hover {
  background: #000;
  transform: scale(1.2);
}
</style>
