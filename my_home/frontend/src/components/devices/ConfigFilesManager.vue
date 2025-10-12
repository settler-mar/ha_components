<template>
  <v-card variant="outlined">
    <v-card-title class="text-subtitle-1 d-flex align-center justify-space-between">
      <span>Файлы конфигураций</span>
      <v-btn size="small" @click="loadConfigFiles" :loading="loadingFiles">
        <v-icon size="14" class="me-1">mdi-refresh</v-icon>
        Обновить
      </v-btn>
    </v-card-title>
    
    <v-card-text>
      <div v-if="configFiles.length">
        <div v-for="file in configFiles" :key="file.name" class="config-file-item">
          <div class="d-flex align-center justify-space-between py-2">
            <div class="d-flex align-center">
              <v-icon size="16" color="orange" class="me-2">mdi-file-cog</v-icon>
              <span class="text-body-2 font-weight-medium">{{ file.name }}</span>
              <v-chip size="x-small" variant="tonal" color="info" class="ms-2">
                {{ file.versions }} версий
              </v-chip>
            </div>
            <div>
              <v-btn size="x-small" variant="outlined" @click="showFileHistory(file)" class="me-1">
                <v-icon size="10">mdi-history</v-icon>
              </v-btn>
              <v-btn size="x-small" variant="outlined" @click="downloadLatestFile(file)" class="me-1">
                <v-icon size="10">mdi-download</v-icon>
              </v-btn>
              <v-btn size="x-small" variant="outlined" @click="viewLatestFile(file)">
                <v-icon size="10">mdi-eye</v-icon>
              </v-btn>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="text-grey text-center py-4">
        Файлы конфигураций не найдены
      </div>
    </v-card-text>
  </v-card>

  <!-- Модалка истории файла -->
  <v-dialog v-model="showHistoryModal" max-width="900px" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="me-2">mdi-history</v-icon>
        История файла: {{ selectedFile?.name }}
      </v-card-title>
      
      <v-card-text style="max-height: 600px;">
        <div v-if="fileVersions.length" class="versions-list">
          <div v-for="version in fileVersions" :key="version.timestamp" 
               class="version-item" 
               :class="{ 'selected-for-comparison': isVersionSelected(version) }"
               @click="toggleVersionSelection(version)">
            <div class="d-flex align-center justify-space-between py-2">
              <div class="d-flex align-center">
                <v-checkbox 
                  :model-value="isVersionSelected(version)"
                  @click.stop
                  @update:model-value="toggleVersionSelection(version)"
                  :disabled="!isVersionSelected(version) && selectedVersions.length >= 2"
                  hide-details
                  class="me-2"
                  size="small"
                />
                <v-icon size="14" color="primary" class="me-2">mdi-clock</v-icon>
                <span class="text-body-2">{{ formatTimestamp(version.timestamp) }}</span>
                <v-chip size="x-small" variant="tonal" class="ms-2">
                  {{ formatFileSize(version.size) }}
                </v-chip>
              </div>
              <div @click.stop>
                <v-btn size="x-small" variant="outlined" @click="downloadVersion(version)" class="me-1">
                  <v-icon size="10">mdi-download</v-icon>
                </v-btn>
                <v-btn size="x-small" variant="outlined" @click="viewVersion(version)">
                  <v-icon size="10">mdi-eye</v-icon>
                </v-btn>
              </div>
            </div>
          </div>
          
          <!-- Кнопки сравнения -->
          <div v-if="selectedVersions.length === 2" class="comparison-controls mt-4">
            <v-btn color="primary" @click="showComparison">
              <v-icon class="me-1">mdi-compare</v-icon>
              Сравнить выбранные версии
            </v-btn>
            <v-btn variant="outlined" @click="clearSelection" class="ms-2">
              Очистить выбор
            </v-btn>
          </div>
        </div>
        <div v-else class="text-grey text-center py-4">
          История версий не найдена
        </div>
      </v-card-text>
      
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn @click="showHistoryModal = false">Закрыть</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Модалка сравнения версий -->
  <v-dialog v-model="showComparisonModal" max-width="1200px" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="me-2">mdi-compare</v-icon>
        Сравнение версий: {{ selectedFile?.name }}
      </v-card-title>
      
      <v-card-text style="max-height: 700px;">
        <!-- Информация о различиях -->
        <div v-if="diffInfo" class="diff-info mb-3">
          <v-alert 
            :type="diffInfo.hasDifferences ? 'info' : 'success'" 
            variant="tonal" 
            class="mb-2"
          >
            <div v-if="diffInfo.hasDifferences">
              <div class="mb-2">
                <strong>Найдено различий:</strong>
              </div>
              <div class="d-flex flex-wrap gap-2">
                <v-chip v-if="diffInfo.changedLines" size="small" color="orange" variant="tonal">
                  Изменено: {{ diffInfo.changedLines }}
                </v-chip>
                <v-chip v-if="diffInfo.newKeys?.length" size="small" color="green" variant="tonal">
                  Новых ключей: {{ diffInfo.newKeys.length }}
                </v-chip>
                <v-chip v-if="diffInfo.removedKeys?.length" size="small" color="red" variant="tonal">
                  Удалено ключей: {{ diffInfo.removedKeys.length }}
                </v-chip>
              </div>
            </div>
            <div v-else>
              Файлы идентичны
            </div>
          </v-alert>
        </div>
        
        <div class="comparison-view">
          <v-row>
            <v-col cols="6">
              <div class="comparison-header">
                <h4 class="text-h6 mb-2">
                  <v-icon size="16" class="me-1">mdi-file-document-outline</v-icon>
                  {{ formatTimestamp(selectedVersions[0]?.timestamp) }}
                </h4>
                <v-chip size="x-small" color="blue" variant="outlined">
                  Версия 1
                </v-chip>
              </div>
              <div class="file-content-wrapper">
                <pre class="file-content" v-html="highlightedContent[0]"></pre>
              </div>
            </v-col>
            <v-col cols="6">
              <div class="comparison-header">
                <h4 class="text-h6 mb-2">
                  <v-icon size="16" class="me-1">mdi-file-document</v-icon>
                  {{ formatTimestamp(selectedVersions[1]?.timestamp) }}
                </h4>
                <v-chip size="x-small" color="green" variant="outlined">
                  Версия 2
                </v-chip>
              </div>
              <div class="file-content-wrapper">
                <pre class="file-content" v-html="highlightedContent[1]"></pre>
              </div>
            </v-col>
          </v-row>
        </div>
        
        <!-- Легенда подсветки -->
        <div class="diff-legend mt-4">
          <v-card variant="outlined">
            <v-card-title class="text-subtitle-2">Легенда различий</v-card-title>
            <v-card-text class="py-2">
              <div class="d-flex flex-wrap gap-3">
                <div class="legend-item">
                  <span class="diff-key-new legend-sample">ключ</span>
                  <span class="text-caption ms-1">Новый ключ</span>
                </div>
                <div class="legend-item">
                  <span class="diff-key-removed legend-sample">ключ</span>
                  <span class="text-caption ms-1">Удаленный ключ</span>
                </div>
                <div class="legend-item">
                  <span class="diff-value-changed legend-sample">значение</span>
                  <span class="text-caption ms-1">Измененное значение</span>
                </div>
                <div class="legend-item">
                  <span class="diff-char-changed legend-sample">текст</span>
                  <span class="text-caption ms-1">Измененный текст</span>
                </div>
              </div>
            </v-card-text>
          </v-card>
        </div>
      </v-card-text>
      
      <v-card-actions>
        <v-btn size="small" variant="outlined" @click="testHighlighting">
          <v-icon size="14" class="me-1">mdi-test-tube</v-icon>
          Тест подсветки
        </v-btn>
        <v-spacer></v-spacer>
        <v-btn @click="showComparisonModal = false">Закрыть</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Модалка просмотра версии -->
  <v-dialog v-model="showVersionModal" max-width="800px" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="me-2">mdi-file-code</v-icon>
        {{ selectedFile?.name }} - {{ formatTimestamp(selectedVersion?.timestamp) }}
      </v-card-title>
      
      <v-card-text style="max-height: 500px;">
        <pre class="file-content">{{ versionContent }}</pre>
      </v-card-text>
      
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn @click="showVersionModal = false">Закрыть</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import {ref, computed} from 'vue'
import {secureFetch} from '@/services/fetch'

const props = defineProps({
  deviceId: {
    type: Number,
    required: true
  },
  backupHistory: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['refresh', 'download', 'view', 'notification'])

// Состояние компонента
const configFiles = ref([])
const loadingFiles = ref(false)
const showHistoryModal = ref(false)
const showComparisonModal = ref(false)
const showVersionModal = ref(false)

// Данные для модалок
const selectedFile = ref(null)
const fileVersions = ref([])
const selectedVersions = ref([])
const versionContents = ref(['', ''])
const selectedVersion = ref(null)
const versionContent = ref('')

// Данные для сравнения
const highlightedContent = ref(['', ''])
const diffInfo = ref(null)

// Сортируем историю - новые записи сверху
const sortedBackupHistory = computed(() => {
  return [...props.backupHistory].sort((a, b) => {
    const dateA = new Date(a.timestamp)
    const dateB = new Date(b.timestamp)
    return dateB - dateA
  })
})

// Форматирование временной метки
const formatTimestamp = (timestamp) => {
  try {
    let date
    if (timestamp.includes('T')) {
      date = new Date(timestamp)
    } else if (timestamp.includes('-') && timestamp.includes(':')) {
      date = new Date(timestamp.replace(' ', 'T'))
    } else {
      date = new Date(timestamp)
    }
    
    if (isNaN(date.getTime())) {
      return timestamp
    }
    
    return date.toLocaleString('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch (error) {
    return timestamp
  }
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// Загрузка списка конфигурационных файлов
const loadConfigFiles = async () => {
  loadingFiles.value = true
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/config/files`)
    if (response.ok) {
      const data = await response.json()
      configFiles.value = data.files || []
    }
  } catch (error) {
    console.error('Error loading config files:', error)
    emit('notification', 'Ошибка загрузки списка файлов конфигурации', 'error')
  } finally {
    loadingFiles.value = false
  }
}

// Просмотр истории файла
const showFileHistory = async (file) => {
  selectedFile.value = file
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/config/history/${file.name}`)
    if (response.ok) {
      const data = await response.json()
      fileVersions.value = data.versions || []
      showHistoryModal.value = true
    }
  } catch (error) {
    console.error('Error loading file history:', error)
    emit('notification', `Ошибка загрузки истории файла ${file.name}`, 'error')
  }
}

// Скачивание последней версии файла
const downloadLatestFile = async (file) => {
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/config/download/${file.name}`)
    if (response.ok) {
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = file.name
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      emit('notification', `Файл ${file.name} успешно скачан`, 'success')
    }
  } catch (error) {
    console.error('Error downloading file:', error)
    emit('notification', `Ошибка скачивания файла ${file.name}`, 'error')
  }
}

// Просмотр последней версии файла
const viewLatestFile = async (file) => {
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/config/content/${file.name}`)
    if (response.ok) {
      const data = await response.json()
      if (data.success) {
        selectedFile.value = file
        selectedVersion.value = { timestamp: 'latest' }
        versionContent.value = data.content
        showVersionModal.value = true
      }
    }
  } catch (error) {
    console.error('Error viewing file:', error)
    emit('notification', `Ошибка просмотра файла ${file.name}`, 'error')
  }
}

// Работа с версиями для сравнения
const isVersionSelected = (version) => {
  return selectedVersions.value.some(v => v.timestamp === version.timestamp)
}

const toggleVersionSelection = (version) => {
  const index = selectedVersions.value.findIndex(v => v.timestamp === version.timestamp)
  
  if (index >= 0) {
    // Убираем из выделения
    selectedVersions.value.splice(index, 1)
  } else if (selectedVersions.value.length < 2) {
    // Добавляем в выделение
    selectedVersions.value.push(version)
  }
}

const clearSelection = () => {
  selectedVersions.value = []
  versionContents.value = ['', '']
}

const showComparison = async () => {
  try {
    // Загружаем содержимое обеих версий
    const promises = selectedVersions.value.map(version => 
      secureFetch(`/api/devices/${props.deviceId}/config/version/${selectedFile.value.name}/${version.timestamp}`)
    )
    
    const responses = await Promise.all(promises)
    const contents = await Promise.all(responses.map(r => r.json()))
    
    versionContents.value = contents.map(c => c.success ? c.content : 'Ошибка загрузки')
    
    // Создаем diff и подсветку
    createDiffHighlight()
    
    showComparisonModal.value = true
    
  } catch (error) {
    console.error('Error loading versions for comparison:', error)
    emit('notification', 'Ошибка загрузки версий для сравнения', 'error')
  }
}

// Определение типа файла
const detectFileType = (filename, content) => {
  if (filename.endsWith('.json')) {
    return 'json'
  }
  if (filename.endsWith('.jsonl')) {
    return 'jsonl'
  }
  
  // Пробуем определить по содержимому
  try {
    JSON.parse(content)
    return 'json'
  } catch {
    // Проверяем JSONL - каждая строка должна быть валидным JSON
    const lines = content.split('\n').filter(line => line.trim())
    if (lines.length > 0 && lines.every(line => {
      try {
        JSON.parse(line)
        return true
      } catch {
        return false
      }
    })) {
      return 'jsonl'
    }
  }
  
  return 'text'
}

// Создание diff и подсветки различий
const createDiffHighlight = () => {
  const content1 = versionContents.value[0] || ''
  const content2 = versionContents.value[1] || ''
  
  // Определяем тип файла
  const fileType = detectFileType(selectedFile.value?.name || '', content1)
  
  if (fileType === 'json') {
    createJsonDiff(content1, content2)
  } else if (fileType === 'jsonl') {
    createJsonlDiff(content1, content2)
  } else {
    createTextDiff(content1, content2)
  }
}

// Сравнение обычных текстовых файлов
const createTextDiff = (content1, content2) => {
  const lines1 = content1.split('\n')
  const lines2 = content2.split('\n')
  
  const maxLines = Math.max(lines1.length, lines2.length)
  let changedLines = 0
  
  const highlighted1 = []
  const highlighted2 = []
  
  for (let i = 0; i < maxLines; i++) {
    const line1 = lines1[i] || ''
    const line2 = lines2[i] || ''
    
    if (line1 !== line2) {
      changedLines++
      const diffResult = createInlineDiff(line1, line2)
      highlighted1.push(`<span class="diff-line-changed">${diffResult.highlighted1}</span>`)
      highlighted2.push(`<span class="diff-line-changed">${diffResult.highlighted2}</span>`)
    } else {
      highlighted1.push(escapeHtml(line1))
      highlighted2.push(escapeHtml(line2))
    }
  }
  
  highlightedContent.value = [
    highlighted1.join('\n'),
    highlighted2.join('\n')
  ]
  
  diffInfo.value = {
    hasDifferences: changedLines > 0,
    changedLines: changedLines,
    totalLines: maxLines
  }
}

// Сравнение JSON файлов
const createJsonDiff = (content1, content2) => {
  try {
    const json1 = JSON.parse(content1)
    const json2 = JSON.parse(content2)
    
    // Создаем структурированное сравнение
    const diff = compareJsonObjects(json1, json2)
    
    // Форматируем JSON с подсветкой различий
    const formatted1 = formatJsonWithHighlight(json1, diff, 'left')
    const formatted2 = formatJsonWithHighlight(json2, diff, 'right')
    
    highlightedContent.value = [formatted1, formatted2]
    
    diffInfo.value = {
      hasDifferences: diff.hasChanges,
      changedLines: diff.changedKeys.length,
      totalLines: Object.keys(json1).length + Object.keys(json2).length,
      newKeys: diff.newKeys,
      removedKeys: diff.removedKeys,
      changedKeys: diff.changedKeys
    }
    
  } catch (error) {
    // Если не удалось распарсить JSON, используем текстовое сравнение
    console.warn('Failed to parse JSON, falling back to text diff:', error)
    createTextDiff(content1, content2)
  }
}

// Сравнение JSONL файлов
const createJsonlDiff = (content1, content2) => {
  try {
    const lines1 = content1.split('\n').filter(line => line.trim())
    const lines2 = content2.split('\n').filter(line => line.trim())
    
    const json1 = lines1.map(line => JSON.parse(line))
    const json2 = lines2.map(line => JSON.parse(line))
    
    const maxLines = Math.max(json1.length, json2.length)
    let changedLines = 0
    const highlighted1 = []
    const highlighted2 = []
    
    for (let i = 0; i < maxLines; i++) {
      const obj1 = json1[i] || null
      const obj2 = json2[i] || null
      
      if (!obj1 && obj2) {
        // Новая строка
        highlighted1.push(`<span class="diff-line-added">// Строка добавлена</span>`)
        highlighted2.push(`<span class="diff-line-added">${escapeHtml(JSON.stringify(obj2, null, 2))}</span>`)
        changedLines++
      } else if (obj1 && !obj2) {
        // Удаленная строка
        highlighted1.push(`<span class="diff-line-removed">${escapeHtml(JSON.stringify(obj1, null, 2))}</span>`)
        highlighted2.push(`<span class="diff-line-removed">// Строка удалена</span>`)
        changedLines++
      } else if (obj1 && obj2) {
        // Сравниваем объекты
        const diff = compareJsonObjects(obj1, obj2)
        if (diff.hasChanges) {
          changedLines++
          const formatted1 = formatJsonWithHighlight(obj1, diff, 'left')
          const formatted2 = formatJsonWithHighlight(obj2, diff, 'right')
          highlighted1.push(`<span class="diff-line-changed">${formatted1}</span>`)
          highlighted2.push(`<span class="diff-line-changed">${formatted2}</span>`)
        } else {
          highlighted1.push(escapeHtml(JSON.stringify(obj1, null, 2)))
          highlighted2.push(escapeHtml(JSON.stringify(obj2, null, 2)))
        }
      }
    }
    
    highlightedContent.value = [
      highlighted1.join('\n'),
      highlighted2.join('\n')
    ]
    
    diffInfo.value = {
      hasDifferences: changedLines > 0,
      changedLines: changedLines,
      totalLines: maxLines
    }
    
  } catch (error) {
    console.warn('Failed to parse JSONL, falling back to text diff:', error)
    createTextDiff(content1, content2)
  }
}

// Сравнение JSON объектов
const compareJsonObjects = (obj1, obj2, path = '') => {
  const result = {
    hasChanges: false,
    newKeys: [],
    removedKeys: [],
    changedKeys: [],
    arrayChanges: {}
  }
  
  const keys1 = Object.keys(obj1 || {})
  const keys2 = Object.keys(obj2 || {})
  const allKeys = new Set([...keys1, ...keys2])
  
  for (const key of allKeys) {
    const currentPath = path ? `${path}.${key}` : key
    const val1 = obj1?.[key]
    const val2 = obj2?.[key]
    
    if (!(key in (obj1 || {}))) {
      // Новый ключ
      result.newKeys.push(currentPath)
      result.hasChanges = true
    } else if (!(key in (obj2 || {}))) {
      // Удаленный ключ
      result.removedKeys.push(currentPath)
      result.hasChanges = true
    } else if (Array.isArray(val1) && Array.isArray(val2)) {
      // Сравнение массивов
      const arrayDiff = compareArrays(val1, val2)
      if (arrayDiff.hasChanges) {
        result.arrayChanges[currentPath] = arrayDiff
        result.changedKeys.push(currentPath)
        result.hasChanges = true
      }
    } else if (typeof val1 === 'object' && typeof val2 === 'object' && val1 !== null && val2 !== null) {
      // Рекурсивное сравнение объектов
      const nestedDiff = compareJsonObjects(val1, val2, currentPath)
      if (nestedDiff.hasChanges) {
        result.newKeys.push(...nestedDiff.newKeys)
        result.removedKeys.push(...nestedDiff.removedKeys)
        result.changedKeys.push(...nestedDiff.changedKeys)
        Object.assign(result.arrayChanges, nestedDiff.arrayChanges)
        result.hasChanges = true
      }
    } else if (val1 !== val2) {
      // Изменено значение
      result.changedKeys.push(currentPath)
      result.hasChanges = true
    }
  }
  
  return result
}

// Сравнение массивов
const compareArrays = (arr1, arr2) => {
  const result = {
    hasChanges: false,
    added: [],
    removed: [],
    modified: []
  }
  
  const maxLength = Math.max(arr1.length, arr2.length)
  
  for (let i = 0; i < maxLength; i++) {
    if (i >= arr1.length) {
      result.added.push({ index: i, value: arr2[i] })
      result.hasChanges = true
    } else if (i >= arr2.length) {
      result.removed.push({ index: i, value: arr1[i] })
      result.hasChanges = true
    } else if (JSON.stringify(arr1[i]) !== JSON.stringify(arr2[i])) {
      result.modified.push({ index: i, oldValue: arr1[i], newValue: arr2[i] })
      result.hasChanges = true
    }
  }
  
  return result
}

// Форматирование JSON с подсветкой
const formatJsonWithHighlight = (obj, diff, side) => {
  try {
    // Рекурсивно обходим объект и создаем подсвеченную версию
    const formatValue = (value, path = '', indent = 0) => {
      const spaces = '  '.repeat(indent)
      
      if (value === null) {
        return 'null'
      } else if (typeof value === 'string') {
        const isChanged = diff.changedKeys.includes(path)
        const escaped = escapeHtml(`"${value}"`)
        return isChanged ? `<span class="diff-value-changed">${escaped}</span>` : escaped
      } else if (typeof value === 'number' || typeof value === 'boolean') {
        const isChanged = diff.changedKeys.includes(path)
        const escaped = escapeHtml(String(value))
        return isChanged ? `<span class="diff-value-changed">${escaped}</span>` : escaped
      } else if (Array.isArray(value)) {
        const arrayPath = path
        const arrayDiff = diff.arrayChanges[arrayPath]
        
        let result = '[\n'
        value.forEach((item, index) => {
          const itemPath = `${path}[${index}]`
          let itemFormatted = formatValue(item, itemPath, indent + 1)
          
          // Подсвечиваем изменения в массиве
          if (arrayDiff) {
            if (arrayDiff.added.some(a => a.index === index)) {
              itemFormatted = `<span class="diff-array-added">${itemFormatted}</span>`
            } else if (arrayDiff.removed.some(r => r.index === index)) {
              itemFormatted = `<span class="diff-array-removed">${itemFormatted}</span>`
            } else if (arrayDiff.modified.some(m => m.index === index)) {
              itemFormatted = `<span class="diff-array-modified">${itemFormatted}</span>`
            }
          }
          
          result += `${'  '.repeat(indent + 1)}${itemFormatted}`
          if (index < value.length - 1) result += ','
          result += '\n'
        })
        result += `${spaces}]`
        return result
      } else if (typeof value === 'object') {
        let result = '{\n'
        const keys = Object.keys(value)
        
        keys.forEach((key, index) => {
          const keyPath = path ? `${path}.${key}` : key
          const isNewKey = diff.newKeys.includes(keyPath) && side === 'right'
          const isRemovedKey = diff.removedKeys.includes(keyPath) && side === 'left'
          
          let keyFormatted = escapeHtml(`"${key}"`)
          if (isNewKey) {
            keyFormatted = `<span class="diff-key-new">${keyFormatted}</span>`
          } else if (isRemovedKey) {
            keyFormatted = `<span class="diff-key-removed">${keyFormatted}</span>`
          }
          
          const valueFormatted = formatValue(value[key], keyPath, indent + 1)
          result += `${'  '.repeat(indent + 1)}${keyFormatted}: ${valueFormatted}`
          if (index < keys.length - 1) result += ','
          result += '\n'
        })
        
        result += `${spaces}}`
        return result
      }
      
      return escapeHtml(String(value))
    }
    
    return formatValue(obj)
  } catch (error) {
    return escapeHtml(JSON.stringify(obj, null, 2))
  }
}

// Создание подсветки различий в строке (по словам и символам)
const createInlineDiff = (str1, str2) => {
  // Сначала попробуем найти общие части в начале и конце
  const commonPrefix = findCommonPrefix(str1, str2)
  const commonSuffix = findCommonSuffix(str1, str2)
  
  // Извлекаем различающиеся части
  const prefixLen = commonPrefix.length
  const suffixLen = commonSuffix.length
  
  const diff1 = str1.slice(prefixLen, str1.length - suffixLen)
  const diff2 = str2.slice(prefixLen, str2.length - suffixLen)
  
  // Формируем результат
  let highlighted1 = escapeHtml(commonPrefix)
  let highlighted2 = escapeHtml(commonPrefix)
  
  if (diff1 || diff2) {
    highlighted1 += `<span class="diff-char-changed">${escapeHtml(diff1)}</span>`
    highlighted2 += `<span class="diff-char-changed">${escapeHtml(diff2)}</span>`
  }
  
  highlighted1 += escapeHtml(commonSuffix)
  highlighted2 += escapeHtml(commonSuffix)
  
  return {
    highlighted1,
    highlighted2
  }
}

// Находим общий префикс двух строк
const findCommonPrefix = (str1, str2) => {
  let i = 0
  while (i < str1.length && i < str2.length && str1[i] === str2[i]) {
    i++
  }
  return str1.slice(0, i)
}

// Находим общий суффикс двух строк
const findCommonSuffix = (str1, str2) => {
  let i = 0
  while (i < str1.length && i < str2.length && 
         str1[str1.length - 1 - i] === str2[str2.length - 1 - i]) {
    i++
  }
  return str1.slice(str1.length - i)
}

// Экранирование HTML
const escapeHtml = (text) => {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// Просмотр конкретной версии из истории
const viewConfigFile = async (filename, timestamp) => {
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/config/version/${filename}/${timestamp}`)
    if (response.ok) {
      const data = await response.json()
      if (data.success) {
        selectedFile.value = { name: filename }
        selectedVersion.value = { timestamp }
        versionContent.value = data.content
        showVersionModal.value = true
      }
    }
  } catch (error) {
    console.error('Error viewing config file version:', error)
    emit('notification', `Ошибка просмотра версии файла ${filename}`, 'error')
  }
}

// Скачивание конкретной версии из истории
const downloadConfigFile = async (filename, timestamp) => {
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/config/download/${filename}/${timestamp}`)
    if (response.ok) {
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${filename}_${timestamp.replace(/[:\s]/g, '_')}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      emit('notification', `Версия файла ${filename} успешно скачана`, 'success')
    }
  } catch (error) {
    console.error('Error downloading config file version:', error)
    emit('notification', `Ошибка скачивания версии файла ${filename}`, 'error')
  }
}

// Просмотр версии из модалки истории
const viewVersion = async (version) => {
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/config/version/${selectedFile.value.name}/${version.timestamp}`)
    if (response.ok) {
      const data = await response.json()
      if (data.success) {
        selectedVersion.value = version
        versionContent.value = data.content
        showVersionModal.value = true
      }
    }
  } catch (error) {
    console.error('Error viewing version:', error)
    emit('notification', 'Ошибка просмотра версии файла', 'error')
  }
}

// Скачивание версии из модалки истории
const downloadVersion = async (version) => {
  try {
    const response = await secureFetch(`/api/devices/${props.deviceId}/config/download/${selectedFile.value.name}/${version.timestamp}`)
    if (response.ok) {
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${selectedFile.value.name}_${version.timestamp.replace(/[:\s]/g, '_')}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      emit('notification', `Версия файла успешно скачана`, 'success')
    }
  } catch (error) {
    console.error('Error downloading version:', error)
    emit('notification', 'Ошибка скачивания версии файла', 'error')
  }
}

// Тестовая функция для проверки подсветки
const testHighlighting = () => {
  // Создаем тестовые данные с различными типами изменений
  const testContent1 = `{
  "timeout": 5000,
  "servers": ["api1", "api2"],
  "debug": false,
  "oldKey": "will be removed"
}`

  const testContent2 = `{
  "timeout": 3000,
  "servers": ["api1", "api3", "api4"],
  "debug": false,
  "newKey": "was added"
}`

  versionContents.value = [testContent1, testContent2]
  selectedFile.value = { name: 'test.json' }
  
  // Принудительно создаем подсветку
  createDiffHighlight()
  
  emit('notification', 'Тестовая подсветка применена', 'info')
}
</script>

<style scoped>
.config-file-item {
  border-bottom: 1px solid #e0e0e0;
}

.config-file-item:last-child {
  border-bottom: none;
}

.versions-list {
  max-height: 400px;
  overflow-y: auto;
}

.version-item {
  border-bottom: 1px solid #e0e0e0;
  padding: 8px 0;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.version-item:last-child {
  border-bottom: none;
}

.version-item:hover {
  background-color: #f5f5f5;
}

.selected-for-comparison {
  background-color: #e3f2fd !important;
  border: 2px solid #2196f3;
  margin: 2px 0;
}

.comparison-controls {
  border-top: 2px solid #e3f2fd;
  padding-top: 16px;
  text-align: center;
}

.file-content {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  background-color: #f5f5f5;
  padding: 16px;
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  border: 1px solid #ddd;
}

.comparison-view .file-content {
  max-height: 500px;
}

:deep(.diff-line-changed) {
  background-color: #f8f9fa !important;
  padding: 2px 4px !important;
  border-radius: 2px !important;
  display: block !important;
  margin: 1px 0 !important;
  border-left: 2px solid #e0e0e0 !important;
}

/* JSON специфичные стили - используем deep селекторы для v-html контента */
:deep(.diff-key-new) {
  background-color: #4caf50 !important;
  color: white !important;
  padding: 1px 3px !important;
  border-radius: 2px !important;
  font-weight: bold !important;
}

:deep(.diff-key-removed) {
  background-color: #f44336 !important;
  color: white !important;
  padding: 1px 3px !important;
  border-radius: 2px !important;
  font-weight: bold !important;
  text-decoration: line-through !important;
}

:deep(.diff-value-changed) {
  background-color: #ff9800 !important;
  color: white !important;
  padding: 1px 3px !important;
  border-radius: 2px !important;
  font-weight: bold !important;
}

:deep(.diff-line-added) {
  background-color: #e8f5e8 !important;
  color: #2e7d2e !important;
  border-left: 3px solid #4caf50 !important;
  padding: 2px 4px !important;
  display: block !important;
  margin: 1px 0 !important;
}

:deep(.diff-line-removed) {
  background-color: #fdeaea !important;
  color: #c62828 !important;
  border-left: 3px solid #f44336 !important;
  padding: 2px 4px !important;
  display: block !important;
  margin: 1px 0 !important;
  text-decoration: line-through !important;
}

:deep(.diff-char-changed) {
  background-color: #ff5722 !important;
  color: white !important;
  padding: 1px 3px !important;
  border-radius: 3px !important;
  font-weight: bold !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.2) !important;
}

.file-content-wrapper {
  border: 1px solid #ddd;
  border-radius: 4px;
  overflow: hidden;
}

.comparison-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding: 8px;
  background-color: #f8f9fa;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
}

.diff-legend {
  background-color: #fafafa;
  border-radius: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
}

.legend-sample {
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 11px;
  font-weight: bold;
}

/* Стили для массивов - используем deep селекторы */
:deep(.diff-array-added) {
  background-color: #e8f5e8 !important;
  color: #2e7d2e !important;
  padding: 1px 3px !important;
  border-radius: 2px !important;
  border-left: 2px solid #4caf50 !important;
}

:deep(.diff-array-removed) {
  background-color: #fdeaea !important;
  color: #c62828 !important;
  padding: 1px 3px !important;
  border-radius: 2px !important;
  border-left: 2px solid #f44336 !important;
  text-decoration: line-through !important;
}

:deep(.diff-array-modified) {
  background-color: #fff3e0 !important;
  color: #e65100 !important;
  padding: 1px 3px !important;
  border-radius: 2px !important;
  border-left: 2px solid #ff9800 !important;
}
</style>
