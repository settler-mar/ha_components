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
              <v-btn size="x-small" variant="outlined" @click="openProtectionEditor(file)" class="ms-1">
                <v-icon size="10">{{ isFileProtected(file.name) ? 'mdi-lock' : 'mdi-lock-outline' }}</v-icon>
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
      
      <v-card-text style="max-height: 650px;">
        <div v-if="structuredView" class="mb-2 d-flex justify-end">
          <v-btn-toggle v-model="versionViewMode" mandatory density="compact" color="primary" variant="outlined">
            <v-btn value="structured" size="small" prepend-icon="mdi-file-tree">Визуальный</v-btn>
            <v-btn value="raw" size="small" prepend-icon="mdi-code-tags">Текст</v-btn>
          </v-btn-toggle>
        </div>
        <div v-if="structuredView && versionViewMode === 'structured'" class="structured-view">
          <div class="structured-toolbar">
            <span class="text-caption text-medium-emphasis">Структурированный просмотр</span>
            <v-chip size="x-small" color="info" variant="tonal">{{ structuredNodeCount }} полей</v-chip>
            <v-btn size="x-small" variant="text" @click="expandStructuredView(true)">Развернуть</v-btn>
            <v-btn size="x-small" variant="text" @click="expandStructuredView(false)">Свернуть</v-btn>
          </div>
          <div class="structured-tree">
            <div v-for="node in visibleStructuredNodes" :key="node.id"
                 class="structured-row" :class="[`kind-${structuredKind(node)}`, { 'is-container': node.isContainer }]"
                 :style="{ paddingLeft: `${node.depth * 22 + 8}px` }">
              <v-btn v-if="node.children.length" icon size="x-small" variant="text"
                     @click="toggleStructuredNode(node.id)">
                <v-icon size="18">{{ isStructuredExpanded(node.id) ? 'mdi-chevron-down' : 'mdi-chevron-right' }}</v-icon>
              </v-btn>
              <span v-else class="tree-indent"></span>
              <v-icon size="16" class="me-2 structured-icon">
                {{ node.isArray ? 'mdi-code-brackets' : node.isContainer ? 'mdi-code-braces' : 'mdi-circle-small' }}
              </v-icon>
              <code class="structured-path">{{ node.label }}</code>
              <v-chip size="x-small" variant="flat" class="ms-2 structured-type-chip">{{ node.typeLabel }}</v-chip>
              <span v-if="!node.isContainer" class="structured-separator">:</span>
              <span class="structured-value ms-2">{{ node.displayValue }}</span>
              <v-icon v-if="isViewerProtected(node.path)" size="16" color="warning" class="ms-auto" title="Поле защищено">
                mdi-lock
              </v-icon>
            </div>
          </div>
        </div>
        <pre v-if="!structuredView || versionViewMode === 'raw'" class="file-content">{{ versionContent }}</pre>
      </v-card-text>
      
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn @click="showVersionModal = false">Закрыть</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Визуальная настройка защищённых файлов и полей -->
  <v-dialog v-model="showProtectionModal" max-width="900px" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="me-2">mdi-lock-outline</v-icon>
        Защита конфигурации
      </v-card-title>
      <v-card-text>
        <v-alert variant="tonal" type="info" class="mb-4">
          Защищённые значения сравниваются с последней версией бэкапа. При изменении выполняется откат, причина записывается в журнал.
        </v-alert>
        <v-select v-model="protectionFileName" :items="configFiles" item-title="name" item-value="name"
                  label="Файл конфигурации" variant="outlined" density="compact" />
        <v-checkbox v-model="protectWholeFile" label="Защищать весь файл" color="primary" hide-details class="mb-2" />
        <div v-if="!isJsonProtectionFile" class="text-body-2 text-medium-emphasis mb-3">
          Для текстового файла доступна только защита целиком.
        </div>
        <div v-else class="protection-fields">
          <div class="protection-toolbar">
            <v-text-field
              v-model="protectionSearch"
              density="compact"
              variant="outlined"
              hide-details
              clearable
              placeholder="Поиск по пути или значению"
              prepend-inner-icon="mdi-magnify"
              class="protection-search"
            />
            <v-chip size="small" :color="protectedCount ? 'primary' : 'default'" variant="tonal">
              Защищено: {{ protectedCount }} / {{ protectionFields.length }}
            </v-chip>
            <v-btn-toggle v-model="protectionFilter" density="compact" variant="outlined" mandatory>
              <v-btn size="small" value="all">Все</v-btn>
              <v-btn size="small" value="protected" prepend-icon="mdi-lock">Выбранные</v-btn>
            </v-btn-toggle>
            <v-btn size="small" variant="text" prepend-icon="mdi-check-all" @click="toggleProtectionAll(true)">Выбрать видимые</v-btn>
            <v-btn size="small" variant="text" prepend-icon="mdi-close-box-multiple-outline" @click="toggleProtectionAll(false)">Снять видимые</v-btn>
          </div>
          <div class="protection-subheader">
            Поля {{ protectionFileName.endsWith('.jsonl') ? 'JSONL' : 'JSON' }} · отметьте защищённые значения
          </div>
          <v-virtual-scroll
            v-if="filteredProtectionFields.length"
            :items="filteredProtectionFields"
            :item-height="48"
            height="420"
            class="protection-scroll"
          >
            <template #default="{ item: field }">
              <div
                class="protection-row"
                :class="{ 'is-protected': field.protected }"
                @click="field.protected = !field.protected"
              >
                <v-checkbox
                  :model-value="field.protected"
                  color="primary"
                  hide-details
                  density="compact"
                  class="me-2"
                  @click.stop
                  @update:model-value="val => field.protected = val"
                />
                <div class="protection-path-col" :style="{ paddingLeft: `${field.depth * 14}px` }">
                  <div class="d-flex align-center">
                    <v-icon size="15" class="me-1 protection-type-icon">{{ field.typeIcon }}</v-icon>
                    <code class="protection-path">{{ field.path }}</code>
                    <v-chip size="x-small" variant="flat" class="ms-2 protection-type-chip">{{ field.type }}</v-chip>
                  </div>
                  <div v-if="field.preview" class="protection-preview">{{ field.preview }}</div>
                </div>
                <v-icon v-if="field.protected" size="16" color="primary" class="ms-auto">mdi-lock</v-icon>
              </div>
            </template>
          </v-virtual-scroll>
          <div v-else class="text-medium-emphasis pa-4 text-center">
            {{ protectionFields.length ? 'Нет полей по текущему фильтру' : 'В файле нет доступных JSON-полей' }}
          </div>
        </div>
        <v-alert v-if="protectionMessage" :type="protectionMessageType" variant="tonal" class="mt-3">
          {{ protectionMessage }}
        </v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="showProtectionModal = false">Отмена</v-btn>
        <v-btn color="primary" :loading="protectionLoading" @click="saveProtectionPolicy">Сохранить</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import {ref, computed, watch, onMounted} from 'vue'
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
const structuredView = ref(null)
const versionViewMode = ref('structured')
const structuredExpanded = ref({'$': true})

// Данные для сравнения
const highlightedContent = ref(['', ''])
const diffInfo = ref(null)
const showProtectionModal = ref(false)
const protectionFileName = ref('')
const protectionContent = ref('')
const protectionFields = ref([])
const protectionSearch = ref('')
const protectionFilter = ref('all')
const protectWholeFile = ref(false)
const configPolicy = ref({version: 1, devices: {}})
const protectionLoading = ref(false)
const protectionMessage = ref('')
const protectionMessageType = ref('info')

const devicePolicyFiles = computed(() => configPolicy.value?.devices?.[String(props.deviceId)]?.files || {})
const selectedProtectionRule = computed(() => devicePolicyFiles.value[protectionFileName.value] || {})
const isJsonProtectionFile = computed(() => /\.(json|jsonl)$/i.test(protectionFileName.value))
const protectedCount = computed(() => protectionFields.value.filter(f => f.protected).length)
const filteredProtectionFields = computed(() => {
  const q = (protectionSearch.value || '').trim().toLowerCase()
  return protectionFields.value.filter(f => {
    if (protectionFilter.value === 'protected' && !f.protected) return false
    if (!q) return true
    return f.path.toLowerCase().includes(q) || String(f.preview || '').toLowerCase().includes(q)
  })
})
const toggleProtectionAll = value => {
  const targets = filteredProtectionFields.value
  targets.forEach(field => { field.protected = value })
}
const viewerFileRule = computed(() => devicePolicyFiles.value[selectedFile.value?.name] || {})
const structuredNodeCount = computed(() => {
  const count = nodes => nodes.reduce((total, node) => total + 1 + count(node.children), 0)
  return structuredView.value ? count(structuredView.value) : 0
})
const visibleStructuredNodes = computed(() => {
  const result = []
  const append = nodes => nodes.forEach(node => {
    result.push(node)
    if (node.children.length && structuredExpanded.value[node.id]) append(node.children)
  })
  append(structuredView.value || [])
  return result
})

// Сортируем историю - новые записи сверху
const sortedBackupHistory = computed(() => {
  return [...props.backupHistory].sort((a, b) => {
    const dateA = parseBackupTimestamp(a.timestamp)
    const dateB = parseBackupTimestamp(b.timestamp)
    return dateB - dateA
  })
})

const parseBackupTimestamp = (timestamp) => {
  const parsed = new Date(String(timestamp || '').replace('_', 'T'))
  return Number.isNaN(parsed.getTime()) ? new Date(0) : parsed
}

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

const loadConfigPolicy = async () => {
  const response = await secureFetch('/api/diagnostics/config-policy')
  const data = await response.json()
  configPolicy.value = data.policy || {version: 1, devices: {}}
}

const previewValue = (value) => {
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  return text.length > 100 ? `${text.slice(0, 100)}…` : text
}

const collectJsonFields = (value, path = '', result = []) => {
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectJsonFields(item, `${path}.${index}`.replace(/^\./, ''), result))
    if (!value.length && path) result.push({path, preview: '[]', protected: false,
      depth: path.split('.').length - 1, type: 'массив', typeIcon: 'mdi-code-brackets'})
    return result
  }
  if (value && typeof value === 'object') {
    const keys = Object.keys(value)
    if (!keys.length && path) result.push({path, preview: '{}', protected: false,
      depth: path.split('.').length - 1, type: 'объект', typeIcon: 'mdi-code-braces'})
    keys.forEach(key => collectJsonFields(value[key], path ? `${path}.${key}` : key, result))
    return result
  }
  if (path) {
    const type = structuredType(value)
    result.push({path, preview: previewValue(value), protected: false,
      depth: path.split('.').length - 1, type: type.label.split(' · ')[0], typeIcon: type.icon})
  }
  return result
}

const parseProtectionDocument = (content, fileName) => {
  if (/\.jsonl$/i.test(fileName)) {
    return content.split(/\r?\n/).filter(line => line.trim()).map(line => JSON.parse(line))
  }
  return JSON.parse(content)
}

const structuredType = value => {
  if (value === null) return {label: 'null', icon: 'mdi-null'}
  if (Array.isArray(value)) return {label: `массив · ${value.length}`, icon: 'mdi-code-brackets'}
  if (typeof value === 'object') return {label: `объект · ${Object.keys(value).length}`, icon: 'mdi-code-braces'}
  return {label: typeof value, icon: typeof value === 'boolean' ? 'mdi-toggle-switch-outline' : 'mdi-circle-small'}
}

const buildStructuredNodes = (value, path = '$', label = 'корень', depth = 0) => {
  const type = structuredType(value)
  const isContainer = value !== null && typeof value === 'object'
  const children = []
  if (isContainer) {
    const entries = Array.isArray(value)
      ? value.map((item, index) => [String(index), item])
      : Object.entries(value)
    entries.forEach(([key, child]) => {
      const childPath = path === '$' ? key : `${path}.${key}`
      children.push(...buildStructuredNodes(child, childPath, key, depth + 1))
    })
  }
  const displayValue = isContainer ? '' : typeof value === 'string' ? JSON.stringify(value) : String(value)
  return [{id: path, path: path === '$' ? '' : path, label, depth, children,
    isContainer, isArray: Array.isArray(value), typeLabel: type.label, typeIcon: type.icon, displayValue}]
}

const structuredKind = node => {
  if (node.isArray) return 'array'
  if (node.isContainer) return 'object'
  const label = String(node.typeLabel || '').toLowerCase()
  if (label.startsWith('string')) return 'string'
  if (label.startsWith('number')) return 'number'
  if (label.startsWith('boolean')) return 'boolean'
  if (label.startsWith('null')) return 'null'
  return 'other'
}

const isStructuredExpanded = id => Boolean(structuredExpanded.value[id])
const toggleStructuredNode = id => { structuredExpanded.value[id] = !structuredExpanded.value[id] }
const expandStructuredView = expanded => {
  const next = {}
  const visit = nodes => nodes.forEach(node => {
    if (node.children.length) {
      next[node.id] = expanded
      visit(node.children)
    }
  })
  visit(structuredView.value || [])
  structuredExpanded.value = next
}

const prepareStructuredView = (content, fileName) => {
  if (!/\.(json|jsonl)$/i.test(fileName)) {
    structuredView.value = null
    return
  }
  try {
    const parsed = parseProtectionDocument(content, fileName)
    structuredView.value = buildStructuredNodes(parsed)
    structuredExpanded.value = {'$': true}
    structuredView.value[0]?.children.forEach(node => { structuredExpanded.value[node.id] = true })
  } catch {
    structuredView.value = null
  }
}

const isViewerProtected = path => Boolean(
  viewerFileRule.value.protect_all || (path && viewerFileRule.value.keys?.includes(path))
)

const isFileProtected = (fileName) => {
  const rule = devicePolicyFiles.value[fileName]
  return Boolean(rule?.protect_all || rule?.keys?.length)
}

const openProtectionEditor = async (file) => {
  protectionMessage.value = ''
  protectionSearch.value = ''
  protectionFilter.value = 'all'
  protectionFileName.value = file.name
  showProtectionModal.value = true
  protectionLoading.value = true
  try {
    await loadConfigPolicy()
    const response = await secureFetch(`/api/devices/${props.deviceId}/config/content/${file.name}`)
    const data = await response.json()
    protectionContent.value = data.success ? data.content : ''
    const rule = selectedProtectionRule.value
    protectWholeFile.value = Boolean(rule.protect_all)
    let parsed = null
    try { parsed = parseProtectionDocument(protectionContent.value, file.name) } catch { parsed = null }
    const protectedKeys = new Set(rule.keys || [])
    protectionFields.value = parsed === null ? [] : collectJsonFields(parsed).map(field => ({
      ...field,
      protected: protectedKeys.has(field.path),
    }))
  } catch (error) {
    protectionMessageType.value = 'error'
    protectionMessage.value = 'Не удалось загрузить содержимое файла или политику'
  } finally {
    protectionLoading.value = false
  }
}

watch(protectionFileName, async (fileName, previous) => {
  if (!showProtectionModal.value || !fileName || fileName === previous) return
  const file = configFiles.value.find(item => item.name === fileName)
  if (file) await openProtectionEditor(file)
})

const saveProtectionPolicy = async () => {
  protectionLoading.value = true
  protectionMessage.value = ''
  try {
    await loadConfigPolicy()
    const policy = JSON.parse(JSON.stringify(configPolicy.value || {version: 1, devices: {}}))
    policy.version = 1
    policy.devices ||= {}
    policy.devices[String(props.deviceId)] ||= {files: {}}
    policy.devices[String(props.deviceId)].files ||= {}
    const keys = protectionFields.value.filter(field => field.protected).map(field => field.path)
    if (protectWholeFile.value || keys.length) {
      policy.devices[String(props.deviceId)].files[protectionFileName.value] = {
        protect_all: protectWholeFile.value,
        keys: protectWholeFile.value ? [] : keys,
      }
    } else {
      delete policy.devices[String(props.deviceId)].files[protectionFileName.value]
    }
    const response = await secureFetch('/api/diagnostics/config-policy', {method: 'PUT', data: policy})
    const data = await response.json()
    configPolicy.value = data.policy
    protectionMessageType.value = 'success'
    protectionMessage.value = 'Защита сохранена. Изменение записано в журнал.'
  } catch (error) {
    protectionMessageType.value = 'error'
    protectionMessage.value = 'Не удалось сохранить защиту'
  } finally {
    protectionLoading.value = false
  }
}

onMounted(() => {
  loadConfigPolicy().catch(() => {})
})

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
        prepareStructuredView(data.content, file.name)
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
        prepareStructuredView(data.content, filename)
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
        prepareStructuredView(data.content, selectedFile.value.name)
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

.field-list {
  border: 1px solid #e0e0e0;
  max-height: 360px;
  overflow-y: auto;
}

.field-row {
  border-bottom: 1px solid #eeeeee;
}

.field-row:last-child {
  border-bottom: none;
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

.structured-view {
  --sv-border: rgba(var(--v-border-color), 0.35);
  --sv-row-alt: rgba(var(--v-theme-on-surface), 0.035);
  --sv-row-hover: rgba(var(--v-theme-primary), 0.1);
  --sv-key: rgb(var(--v-theme-on-surface));
  --sv-string: #15803d;
  --sv-number: #1d4ed8;
  --sv-boolean: #b45309;
  --sv-null: #94a3b8;
  --sv-container: rgb(var(--v-theme-primary));
  border: 1px solid var(--sv-border);
  border-radius: 10px;
  overflow: hidden;
  background: rgb(var(--v-theme-surface));
}

:root:not([data-theme="light"]) .structured-view,
:root[data-theme="dark"] .structured-view {
  --sv-string: #4ade80;
  --sv-number: #60a5fa;
  --sv-boolean: #fbbf24;
  --sv-null: #94a3b8;
}

.structured-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(var(--v-theme-primary), 0.08);
  border-bottom: 1px solid var(--sv-border);
}

.structured-tree {
  max-height: 540px;
  overflow: auto;
  padding: 4px 0;
  font-size: 13.5px;
}

.structured-row {
  min-height: 34px;
  display: flex;
  align-items: center;
  padding-top: 4px;
  padding-bottom: 4px;
  padding-right: 12px;
  border-bottom: 1px solid var(--sv-border);
  line-height: 1.35;
}

.structured-row:nth-child(even) {
  background: var(--sv-row-alt);
}

.structured-row:hover {
  background: var(--sv-row-hover);
}

.structured-row.is-container .structured-path {
  color: var(--sv-container);
  font-weight: 700;
}

.structured-icon {
  color: var(--sv-null);
}

.is-container .structured-icon { color: var(--sv-container); }
.kind-string .structured-icon { color: var(--sv-string); }
.kind-number .structured-icon { color: var(--sv-number); }
.kind-boolean .structured-icon { color: var(--sv-boolean); }

.tree-indent {
  width: 32px;
  flex: 0 0 32px;
}

.structured-path {
  font-size: 13px;
  font-weight: 600;
  color: var(--sv-key);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.structured-type-chip {
  font-weight: 500 !important;
  font-size: 10.5px !important;
  letter-spacing: 0.02em;
  text-transform: lowercase;
  background: rgba(var(--v-theme-on-surface), 0.08) !important;
  color: rgb(var(--v-theme-on-surface)) !important;
  opacity: 0.85;
}

.kind-string .structured-type-chip { background: rgba(21, 128, 61, 0.15) !important; color: var(--sv-string) !important; opacity: 1; }
.kind-number .structured-type-chip { background: rgba(29, 78, 216, 0.15) !important; color: var(--sv-number) !important; opacity: 1; }
.kind-boolean .structured-type-chip { background: rgba(180, 83, 9, 0.15) !important; color: var(--sv-boolean) !important; opacity: 1; }
.is-container .structured-type-chip { background: rgba(var(--v-theme-primary), 0.15) !important; color: var(--sv-container) !important; opacity: 1; }

.structured-separator {
  margin-left: 6px;
  color: rgb(var(--v-theme-on-surface));
  opacity: 0.45;
  font-weight: 600;
}

.structured-value {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  font-weight: 500;
  white-space: pre-wrap;
  word-break: break-word;
  color: rgb(var(--v-theme-on-surface));
}

.kind-string .structured-value { color: var(--sv-string); }
.kind-number .structured-value { color: var(--sv-number); }
.kind-boolean .structured-value { color: var(--sv-boolean); }
.kind-null .structured-value { color: var(--sv-null); font-style: italic; }

.protection-fields {
  border: 1px solid rgba(var(--v-border-color), 0.35);
  border-radius: 10px;
  overflow: hidden;
  background: rgb(var(--v-theme-surface));
}

.protection-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 12px;
  background: rgba(var(--v-theme-primary), 0.06);
  border-bottom: 1px solid rgba(var(--v-border-color), 0.35);
}

.protection-search {
  flex: 1 1 260px;
  min-width: 220px;
}

.protection-subheader {
  padding: 8px 14px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: rgb(var(--v-theme-on-surface));
  opacity: 0.7;
  background: rgba(var(--v-theme-on-surface), 0.03);
  border-bottom: 1px solid rgba(var(--v-border-color), 0.35);
}

.protection-scroll {
  background: rgb(var(--v-theme-surface));
}

.protection-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  min-height: 48px;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.25);
  cursor: pointer;
  transition: background 0.1s;
}

.protection-row:hover {
  background: rgba(var(--v-theme-primary), 0.08);
}

.protection-row.is-protected {
  background: rgba(var(--v-theme-primary), 0.1);
}

.protection-row.is-protected:hover {
  background: rgba(var(--v-theme-primary), 0.16);
}

.protection-path-col {
  flex: 1 1 auto;
  min-width: 0;
}

.protection-path {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
}

.protection-type-chip {
  background: rgba(var(--v-theme-on-surface), 0.08) !important;
  color: rgb(var(--v-theme-on-surface)) !important;
  font-size: 10.5px !important;
}

.protection-type-icon { color: rgb(var(--v-theme-primary)); opacity: 0.8; }

.protection-preview {
  margin-top: 2px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface));
  opacity: 0.65;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
