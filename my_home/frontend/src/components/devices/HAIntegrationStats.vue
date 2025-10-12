<template>
  <v-card class="ha-stats">
    <v-card-title class="d-flex align-center">
      <v-icon class="me-2">mdi-chart-box</v-icon>
      Статистика интеграции с Home Assistant
    </v-card-title>

    <v-card-text>
      <v-row>
        <!-- Общая статистика -->
        <v-col cols="12" md="4">
          <v-card variant="outlined" class="text-center">
            <v-card-text>
              <div class="text-h4 text-primary">{{ totalEntities }}</div>
              <div class="text-caption">Всего сущностей</div>
            </v-card-text>
          </v-card>
        </v-col>
        
        <v-col cols="12" md="4">
          <v-card variant="outlined" class="text-center">
            <v-card-text>
              <div class="text-h4 text-success">{{ onlineEntities }}</div>
              <div class="text-caption">Онлайн</div>
            </v-card-text>
          </v-card>
        </v-col>
        
        <v-col cols="12" md="4">
          <v-card variant="outlined" class="text-center">
            <v-card-text>
              <div class="text-h4 text-info">{{ lastUpdateTime }}</div>
              <div class="text-caption">Последнее обновление</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Статистика по уровням публикации -->
      <v-row class="mt-4">
        <v-col cols="12">
          <v-card variant="outlined">
            <v-card-title class="py-2">
              <v-icon class="me-2">mdi-layers</v-icon>
              Статистика по уровням публикации
            </v-card-title>
            <v-card-text>
              <v-row>
                <v-col cols="12" md="4">
                  <div class="d-flex align-center mb-2">
                    <v-icon color="primary" class="me-2">mdi-view-grid</v-icon>
                    <span class="font-weight-medium">Все порты</span>
                    <v-spacer></v-spacer>
                    <v-chip size="small" color="primary" variant="outlined">
                      {{ statsByLevel.all }}
                    </v-chip>
                  </div>
                </v-col>
                
                <v-col cols="12" md="4">
                  <div class="d-flex align-center mb-2">
                    <v-icon color="secondary" class="me-2">mdi-folder-multiple</v-icon>
                    <span class="font-weight-medium">Группы портов</span>
                    <v-spacer></v-spacer>
                    <v-chip size="small" color="secondary" variant="outlined">
                      {{ statsByLevel.groups }}
                    </v-chip>
                  </div>
                </v-col>
                
                <v-col cols="12" md="4">
                  <div class="d-flex align-center mb-2">
                    <v-icon color="success" class="me-2">mdi-circle</v-icon>
                    <span class="font-weight-medium">Отдельные порты</span>
                    <v-spacer></v-spacer>
                    <v-chip size="small" color="success" variant="outlined">
                      {{ statsByLevel.individual }}
                    </v-chip>
                  </div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Статистика по типам сущностей -->
      <v-row class="mt-4">
        <v-col cols="12">
          <v-card variant="outlined">
            <v-card-title class="py-2">
              <v-icon class="me-2">mdi-shape</v-icon>
              Статистика по типам сущностей
            </v-card-title>
            <v-card-text>
              <v-row>
                <v-col cols="6" md="3" v-for="(count, type) in statsByType" :key="type">
                  <div class="d-flex align-center mb-2">
                    <v-icon :color="getTypeColor(type)" class="me-2">{{ getTypeIcon(type) }}</v-icon>
                    <span class="text-caption">{{ getTypeName(type) }}</span>
                    <v-spacer></v-spacer>
                    <v-chip size="small" :color="getTypeColor(type)" variant="outlined">
                      {{ count }}
                    </v-chip>
                  </div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Статистика по группам -->
      <v-row class="mt-4" v-if="statsByGroup.length > 0">
        <v-col cols="12">
          <v-card variant="outlined">
            <v-card-title class="py-2">
              <v-icon class="me-2">mdi-folder</v-icon>
              Статистика по группам
            </v-card-title>
            <v-card-text>
              <v-list density="compact">
                <v-list-item
                  v-for="group in statsByGroup"
                  :key="group.name"
                  class="px-0"
                >
                  <template #prepend>
                    <v-icon :icon="getGroupIcon(group.name)" class="me-2"></v-icon>
                  </template>
                  <v-list-item-title>{{ group.name }}</v-list-item-title>
                  <template #append>
                    <v-chip size="small" color="primary" variant="outlined">
                      {{ group.count }}
                    </v-chip>
                  </template>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  entities: {
    type: Array,
    default: () => []
  },
  publishLevel: {
    type: String,
    default: 'all'
  },
  selectedGroups: {
    type: Array,
    default: () => []
  },
  selectedPorts: {
    type: Array,
    default: () => []
  }
})

// Общая статистика
const totalEntities = computed(() => props.entities.length)
const onlineEntities = computed(() => props.entities.filter(e => e.state === 'online').length)
const lastUpdateTime = computed(() => {
  const lastTime = props.entities
    .map(e => e.last_seen)
    .filter(t => t)
    .sort()
    .pop()
  
  return lastTime ? formatTime(lastTime) : 'Никогда'
})

// Статистика по уровням публикации
const statsByLevel = computed(() => {
  const stats = { all: 0, groups: 0, individual: 0 }
  
  if (props.publishLevel === 'all') {
    stats.all = props.entities.length
  } else if (props.publishLevel === 'groups') {
    stats.groups = props.entities.length
  } else if (props.publishLevel === 'individual') {
    stats.individual = props.entities.length
  }
  
  return stats
})

// Статистика по типам сущностей
const statsByType = computed(() => {
  const stats = {}
  
  props.entities.forEach(entity => {
    const type = entity.attributes?.device_class || 'unknown'
    stats[type] = (stats[type] || 0) + 1
  })
  
  return stats
})

// Статистика по группам
const statsByGroup = computed(() => {
  const groupStats = {}
  
  props.entities.forEach(entity => {
    const name = entity.name || entity.entity_id
    const groupName = extractGroupName(name)
    
    if (groupName) {
      groupStats[groupName] = (groupStats[groupName] || 0) + 1
    }
  })
  
  return Object.entries(groupStats)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
})

// Вспомогательные функции
const getTypeIcon = (type) => {
  const iconMap = {
    'temperature': 'mdi-thermometer',
    'voltage': 'mdi-lightning-bolt',
    'current': 'mdi-flash',
    'power': 'mdi-power-plug',
    'energy': 'mdi-battery',
    'frequency': 'mdi-sine-wave',
    'unknown': 'mdi-help-circle'
  }
  return iconMap[type] || 'mdi-help-circle'
}

const getTypeColor = (type) => {
  const colorMap = {
    'temperature': 'orange',
    'voltage': 'blue',
    'current': 'green',
    'power': 'red',
    'energy': 'purple',
    'frequency': 'teal',
    'unknown': 'grey'
  }
  return colorMap[type] || 'grey'
}

const getTypeName = (type) => {
  const nameMap = {
    'temperature': 'Температура',
    'voltage': 'Напряжение',
    'current': 'Ток',
    'power': 'Мощность',
    'energy': 'Энергия',
    'frequency': 'Частота',
    'unknown': 'Неизвестно'
  }
  return nameMap[type] || 'Неизвестно'
}

const getGroupIcon = (groupName) => {
  const iconMap = {
    'ADS': 'mdi-chip',
    'GPIO': 'mdi-pin',
    'LiFePo4': 'mdi-battery',
    'NTC': 'mdi-thermometer',
    'LOGS': 'mdi-file-document',
    'clock': 'mdi-clock',
    'TAC11xx': 'mdi-lightning-bolt',
    'Servo': 'mdi-cog'
  }
  
  for (const [key, icon] of Object.entries(iconMap)) {
    if (groupName.includes(key)) return icon
  }
  
  return 'mdi-folder'
}

const extractGroupName = (entityName) => {
  // Извлекаем название группы из имени сущности
  // Например: "my_home.device_1_ads1115_00_0" -> "ADS"
  const parts = entityName.split('_')
  if (parts.length > 2) {
    const groupPart = parts[2]
    if (groupPart.includes('ads')) return 'ADS'
    if (groupPart.includes('gpio')) return 'GPIO'
    if (groupPart.includes('jdbbms')) return 'LiFePo4'
    if (groupPart.includes('rewriter')) return 'NTC'
    if (groupPart.includes('clock')) return 'clock'
    if (groupPart.includes('tac11xx')) return 'TAC11xx'
    if (groupPart.includes('servo')) return 'Servo'
  }
  return null
}

const formatTime = (timestamp) => {
  if (!timestamp) return 'Неизвестно'
  const date = new Date(timestamp)
  return date.toLocaleTimeString()
}
</script>

<style scoped>
.ha-stats {
  margin-top: 16px;
}

.v-card-text {
  padding: 16px;
}

.v-list-item {
  min-height: 40px;
}
</style>


