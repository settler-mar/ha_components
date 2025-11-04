<template>
  <v-dialog v-model="dialog" max-width="800px" scrollable persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="me-2">mdi-cog-box</v-icon>
        Конфигурация аддона
        <v-spacer></v-spacer>
        <v-btn
          icon
          variant="text"
          @click="close"
        >
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-divider></v-divider>

      <v-card-text v-if="loading" class="text-center py-8">
        <v-progress-circular indeterminate color="primary"></v-progress-circular>
        <div class="mt-4 text-body-2">Загрузка конфигурации...</div>
      </v-card-text>

      <v-card-text v-else-if="error" class="text-center py-8">
        <v-alert type="error" variant="tonal">
          {{ error }}
        </v-alert>
        <v-btn class="mt-4" @click="loadConfig">Повторить</v-btn>
      </v-card-text>

      <v-card-text v-else>
        <v-form ref="form" v-model="valid">
          <v-alert
            v-if="schemaFields.length > 0"
            type="info"
            variant="tonal"
            class="mb-4"
          >
            Настройте параметры аддона. Изменения будут сохранены в options.json и config.yaml
          </v-alert>

          <div v-if="schemaFields.length > 0">
            <!-- Группировка по группам -->
            <div v-if="groupedFields.length > 0">
              <v-expansion-panels variant="accordion" multiple class="mb-4">
                <v-expansion-panel
                  v-for="group in groupedFields"
                  :key="group.name"
                  :title="group.name"
                  :subtitle="group.description"
                >
                <v-expansion-panel-text>
                  <!-- Таблица настроек модулей логирования -->
                  <div v-if="group.name === 'Настройки логирования'" class="mb-4">
                    <!-- Глобальные настройки -->
                    <v-row class="mb-4">
                      <v-col
                        v-for="field in group.fields.filter(f => f.key.startsWith('log_global_'))"
                        :key="field.key"
                        cols="12"
                        :md="field.type === 'bool' ? 12 : 6"
                      >
                        <!-- Boolean field -->
                        <v-switch
                          v-if="field.type === 'bool'"
                          v-model="formData[field.key]"
                          :label="field.name"
                          :hint="field.description"
                          persistent-hint
                          color="primary"
                          hide-details="auto"
                        >
                          <template v-slot:append>
                            <v-tooltip v-if="field.description" location="top">
                              <template v-slot:activator="{ props }">
                                <v-icon v-bind="props" size="small" class="ml-2">
                                  mdi-information-outline
                                </v-icon>
                              </template>
                              <span>{{ field.description }}</span>
                            </v-tooltip>
                          </template>
                        </v-switch>

                        <!-- Select field -->
                        <v-select
                          v-else-if="field.type === 'select'"
                          v-model="formData[field.key]"
                          :label="field.name"
                          :hint="field.description"
                          persistent-hint
                          variant="outlined"
                          density="compact"
                          :items="field.options || []"
                          :rules="getRules(field)"
                          hide-details="auto"
                        >
                          <template v-slot:prepend-inner>
                            <v-icon size="small" class="mt-1">mdi-format-list-bulleted</v-icon>
                          </template>
                        </v-select>
                      </v-col>
                    </v-row>

                    <!-- Таблица настроек модулей -->
                    <v-card variant="outlined" class="mb-4">
                      <v-card-title class="text-subtitle-1">
                        <v-icon class="me-2">mdi-table</v-icon>
                        Настройки модулей
                      </v-card-title>
                      <v-card-text>
                        <v-table density="compact" class="logger-modules-table">
                          <thead>
                            <tr>
                              <th class="text-left" style="width: 200px">Модуль</th>
                              <th class="text-left" style="width: 150px">Уровень</th>
                              <th class="text-center" style="width: 100px">Включен</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr
                              v-for="module in loggerModules"
                              :key="module.name"
                            >
                              <td>
                                <div class="d-flex align-center">
                                  <v-icon size="small" class="me-2">mdi-cog</v-icon>
                                  <span class="font-weight-medium me-1">{{ module.name }}</span>
                                  <v-tooltip location="top">
                                    <template v-slot:activator="{ props }">
                                      <v-btn
                                        v-bind="props"
                                        icon
                                        size="x-small"
                                        variant="text"
                                        density="compact"
                                        @click="openModuleInfo(module)"
                                        class="module-info-btn"
                                      >
                                        <v-icon size="small" color="primary">mdi-information-outline</v-icon>
                                      </v-btn>
                                    </template>
                                    <span class="text-caption">{{ module.description }}</span>
                                  </v-tooltip>
                                </div>
                              </td>
                              <td>
                                <v-select
                                  v-model="formData[module.levelKey]"
                                  :items="['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']"
                                  variant="outlined"
                                  density="compact"
                                  hide-details
                                ></v-select>
                              </td>
                              <td class="text-center">
                                <v-switch
                                  v-model="formData[module.enabledKey]"
                                  color="primary"
                                  hide-details
                                  density="compact"
                                  style="margin: 0 auto"
                                ></v-switch>
                              </td>
                            </tr>
                          </tbody>
                        </v-table>
                      </v-card-text>
                    </v-card>
                    
                    <!-- Модальное окно с информацией о модуле -->
                    <v-dialog v-model="showModuleInfoDialog" max-width="600px">
                      <v-card v-if="selectedModule">
                        <v-card-title class="d-flex align-center">
                          <v-icon class="me-2" color="primary">mdi-information</v-icon>
                          {{ selectedModule.name }}
                          <v-spacer></v-spacer>
                          <v-btn
                            icon
                            variant="text"
                            size="small"
                            @click="showModuleInfoDialog = false"
                          >
                            <v-icon>mdi-close</v-icon>
                          </v-btn>
                        </v-card-title>
                        <v-divider></v-divider>
                        <v-card-text class="pt-4">
                          <div class="mb-4">
                            <div class="text-subtitle-2 mb-2">Описание</div>
                            <div class="text-body-2">{{ selectedModule.description }}</div>
                          </div>
                          <v-divider class="my-4"></v-divider>
                          <div>
                            <div class="text-subtitle-2 mb-3">Функции модуля</div>
                            <v-list density="compact">
                              <v-list-item
                                v-for="(func, index) in selectedModule.functions"
                                :key="index"
                                class="px-0"
                              >
                                <template v-slot:prepend>
                                  <v-icon size="small" color="success" class="me-2">mdi-check-circle</v-icon>
                                </template>
                                <v-list-item-title class="text-body-2">{{ func }}</v-list-item-title>
                              </v-list-item>
                            </v-list>
                          </div>
                        </v-card-text>
                        <v-divider></v-divider>
                        <v-card-actions>
                          <v-spacer></v-spacer>
                          <v-btn
                            color="primary"
                            variant="flat"
                            @click="showModuleInfoDialog = false"
                          >
                            Закрыть
                          </v-btn>
                        </v-card-actions>
                      </v-card>
                    </v-dialog>
                  </div>

                  <!-- Google Auth блок в группе Интеграции -->
                  <div v-if="group.name === 'Интеграции' && googleAuthStatus" class="mb-4">
                    <v-card variant="outlined">
                      <v-card-title class="text-subtitle-1">
                        <v-icon class="me-2">mdi-google</v-icon>
                        Google Sheets Авторизация
                      </v-card-title>
                      <v-card-text>
                        <div class="d-flex align-center mb-2">
                          <v-icon 
                            :color="googleAuthStatus.token_exists ? 'success' : 'error'"
                            class="me-2"
                          >
                            {{ googleAuthStatus.token_exists ? 'mdi-check-circle' : 'mdi-close-circle' }}
                          </v-icon>
                          <span class="text-body-1">
                            {{ googleAuthStatus.token_exists ? 'Токен найден' : 'Токен не найден' }}
                          </span>
                        </div>
                        
                        <div class="d-flex align-center mb-2">
                          <v-icon 
                            :color="googleAuthStatus.credentials_exists ? 'success' : 'warning'"
                            class="me-2"
                          >
                            {{ googleAuthStatus.credentials_exists ? 'mdi-check-circle' : 'mdi-alert-circle' }}
                          </v-icon>
                          <span class="text-body-2">
                            {{ googleAuthStatus.credentials_exists ? 'Credentials файл найден' : 'Credentials файл не найден' }}
                          </span>
                        </div>
                        
                        <div class="d-flex gap-2 mt-3">
                          <v-btn
                            v-if="googleAuthStatus.credentials_exists"
                            color="primary"
                            prepend-icon="mdi-key"
                            @click="getGoogleToken"
                            :loading="gettingToken"
                            size="small"
                          >
                            {{ googleAuthStatus.token_exists ? 'Пересоздать токен' : 'Получить токен' }}
                          </v-btn>
                          
                          <v-btn
                            color="primary"
                            variant="outlined"
                            prepend-icon="mdi-information"
                            @click="showGoogleAuthInstructions = true"
                            size="small"
                          >
                            Инструкции
                          </v-btn>
                        </div>
                      </v-card-text>
                    </v-card>
                  </div>
                  
                  <!-- Обычные поля (кроме настроек логирования) -->
                  <v-row v-if="group.name !== 'Настройки логирования'">
                    <v-col
                      v-for="field in group.fields"
                      :key="field.key"
                      cols="12"
                      :md="field.type === 'bool' ? 12 : 6"
                    >
                <!-- Boolean field -->
                <v-switch
                  v-if="field.type === 'bool'"
                  v-model="formData[field.key]"
                  :label="field.name"
                  :hint="field.description"
                  persistent-hint
                  color="primary"
                  hide-details="auto"
                >
                  <template v-slot:append>
                    <v-tooltip v-if="field.description" location="top">
                      <template v-slot:activator="{ props }">
                        <v-icon v-bind="props" size="small" class="ml-2">
                          mdi-information-outline
                        </v-icon>
                      </template>
                      <span>{{ field.description }}</span>
                    </v-tooltip>
                  </template>
                </v-switch>

                <!-- Integer field -->
                <v-text-field
                  v-else-if="field.type === 'int'"
                  v-model.number="formData[field.key]"
                  :label="field.name"
                  :hint="field.description"
                  persistent-hint
                  type="number"
                  variant="outlined"
                  density="compact"
                  :min="field.min"
                  :max="field.max"
                  :rules="getRules(field)"
                  hide-details="auto"
                >
                  <template v-slot:prepend-inner>
                    <v-icon size="small" class="mt-1">mdi-numeric</v-icon>
                  </template>
                </v-text-field>

                <!-- Select field -->
                <v-select
                  v-else-if="field.type === 'select'"
                  v-model="formData[field.key]"
                  :label="field.name"
                  :hint="field.description"
                  persistent-hint
                  variant="outlined"
                  density="compact"
                  :items="field.options || []"
                  :rules="getRules(field)"
                  hide-details="auto"
                >
                  <template v-slot:prepend-inner>
                    <v-icon size="small" class="mt-1">mdi-format-list-bulleted</v-icon>
                  </template>
                </v-select>

                <!-- String field -->
                <v-text-field
                  v-else
                  v-model="formData[field.key]"
                  :label="field.name"
                  :hint="field.description"
                  persistent-hint
                  variant="outlined"
                  density="compact"
                  :rules="getRules(field)"
                  hide-details="auto"
                >
                  <template v-slot:prepend-inner>
                    <v-icon size="small" class="mt-1">mdi-text</v-icon>
                  </template>
                  <template v-slot:append-inner v-if="field.key === 'ha_url' || field.key === 'ha_token' || field.key === 'gsheet'">
                    <div v-if="field.key === 'gsheet'" class="d-flex align-center gap-1">
                      <v-btn
                        icon="mdi-open-in-new"
                        size="small"
                        variant="text"
                        @click="openGoogleSheet()"
                        :disabled="!formData[field.key]"
                        title="Открыть документ"
                      ></v-btn>
                      <v-btn
                        icon="mdi-check-circle"
                        size="small"
                        variant="text"
                        :loading="testingGoogleSheet"
                        @click="testGoogleSheet()"
                        :disabled="!formData[field.key]"
                        title="Проверить доступность"
                      ></v-btn>
                    </div>
                    <v-btn
                      v-else
                      :icon="field.key === 'ha_url' ? 'mdi-network' : 'mdi-key'"
                      size="small"
                      variant="text"
                      :loading="field.key === 'ha_url' ? testingHost : testingToken"
                      @click="field.key === 'ha_url' ? testHost() : testToken()"
                      :disabled="!formData[field.key]"
                      :title="field.key === 'ha_url' ? 'Проверить хост' : 'Проверить токен'"
                    ></v-btn>
                  </template>
                </v-text-field>
                      </v-col>
                    </v-row>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </div>
            
            <!-- Fallback: если группировка не удалась, показываем простой список -->
            <v-row v-else>
              <v-col
                v-for="field in schemaFields"
                :key="field.key"
                cols="12"
                :md="field.type === 'bool' ? 12 : 6"
              >
                <!-- Boolean field -->
                <v-switch
                  v-if="field.type === 'bool'"
                  v-model="formData[field.key]"
                  :label="field.name"
                  :hint="field.description"
                  persistent-hint
                  color="primary"
                  hide-details="auto"
                >
                  <template v-slot:append>
                    <v-tooltip v-if="field.description" location="top">
                      <template v-slot:activator="{ props }">
                        <v-icon v-bind="props" size="small" class="ml-2">
                          mdi-information-outline
                        </v-icon>
                      </template>
                      <span>{{ field.description }}</span>
                    </v-tooltip>
                  </template>
                </v-switch>

                <!-- Integer field -->
                <v-text-field
                  v-else-if="field.type === 'int'"
                  v-model.number="formData[field.key]"
                  :label="field.name"
                  :hint="field.description"
                  persistent-hint
                  type="number"
                  variant="outlined"
                  density="compact"
                  :min="field.min"
                  :max="field.max"
                  :rules="getRules(field)"
                  hide-details="auto"
                >
                  <template v-slot:prepend-inner>
                    <v-icon size="small" class="mt-1">mdi-numeric</v-icon>
                  </template>
                </v-text-field>

                <!-- Select field -->
                <v-select
                  v-else-if="field.type === 'select'"
                  v-model="formData[field.key]"
                  :label="field.name"
                  :hint="field.description"
                  persistent-hint
                  variant="outlined"
                  density="compact"
                  :items="field.options || []"
                  :rules="getRules(field)"
                  hide-details="auto"
                >
                  <template v-slot:prepend-inner>
                    <v-icon size="small" class="mt-1">mdi-format-list-bulleted</v-icon>
                  </template>
                </v-select>

                <!-- String field -->
                <v-text-field
                  v-else
                  v-model="formData[field.key]"
                  :label="field.name"
                  :hint="field.description"
                  persistent-hint
                  variant="outlined"
                  density="compact"
                  :rules="getRules(field)"
                  hide-details="auto"
                >
                  <template v-slot:prepend-inner>
                    <v-icon size="small" class="mt-1">mdi-text</v-icon>
                  </template>
                  <template v-slot:append-inner v-if="field.key === 'ha_url' || field.key === 'ha_token' || field.key === 'gsheet'">
                    <div v-if="field.key === 'gsheet'" class="d-flex align-center gap-1">
                      <v-btn
                        icon="mdi-open-in-new"
                        size="small"
                        variant="text"
                        @click="openGoogleSheet()"
                        :disabled="!formData[field.key]"
                        title="Открыть документ"
                      ></v-btn>
                      <v-btn
                        icon="mdi-check-circle"
                        size="small"
                        variant="text"
                        :loading="testingGoogleSheet"
                        @click="testGoogleSheet()"
                        :disabled="!formData[field.key]"
                        title="Проверить доступность"
                      ></v-btn>
                    </div>
                    <v-btn
                      v-else
                      :icon="field.key === 'ha_url' ? 'mdi-network' : 'mdi-key'"
                      size="small"
                      variant="text"
                      :loading="field.key === 'ha_url' ? testingHost : testingToken"
                      @click="field.key === 'ha_url' ? testHost() : testToken()"
                      :disabled="!formData[field.key]"
                      :title="field.key === 'ha_url' ? 'Проверить хост' : 'Проверить токен'"
                    ></v-btn>
                  </template>
                </v-text-field>
              </v-col>
            </v-row>
          </div>

          <v-alert v-else type="warning" variant="tonal">
            Схема конфигурации не найдена
          </v-alert>
        </v-form>
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions>
        <v-btn
          variant="text"
          prepend-icon="mdi-refresh"
          :loading="loading"
          @click="reloadConfig"
          :disabled="loading || saving"
        >
          Перезагрузить
        </v-btn>
        <v-spacer></v-spacer>
        <v-btn
          variant="text"
          @click="close"
        >
          Отмена
        </v-btn>
        <v-btn
          color="primary"
          :loading="saving"
          :disabled="!valid || saving"
          @click="save"
        >
          Сохранить
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Диалог инструкций по Google авторизации -->
  <v-dialog v-model="showGoogleAuthInstructions" max-width="800px" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="me-2">mdi-google</v-icon>
        Настройка Google Sheets Авторизации
        <v-spacer></v-spacer>
        <v-btn icon variant="text" @click="showGoogleAuthInstructions = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-divider></v-divider>
      <v-card-text>
        <div v-if="googleAuthInstructions">
          <v-timeline density="compact" side="end" class="mt-2">
            <v-timeline-item
              v-for="instruction in googleAuthInstructions.instructions"
              :key="instruction.step"
              :dot-color="instruction.step === 1 && !googleAuthInstructions.credentials_exists ? 'warning' : 'primary'"
              size="small"
            >
              <div class="mb-4">
                <div class="text-h6 mb-2">
                  Шаг {{ instruction.step }}: {{ instruction.title }}
                </div>
                <div class="text-body-2 mb-2">{{ instruction.description }}</div>
                <v-list v-if="instruction.details" density="compact" class="bg-transparent">
                  <v-list-item
                    v-for="(detail, idx) in instruction.details"
                    :key="idx"
                    class="px-0 py-1"
                  >
                    <template v-if="detail.trim()">
                      <v-list-item-title class="text-caption">
                        {{ detail }}
                      </v-list-item-title>
                    </template>
                    <v-divider v-else class="my-2"></v-divider>
                  </v-list-item>
                </v-list>
              </div>
            </v-timeline-item>
          </v-timeline>
          
          <v-alert type="info" variant="tonal" class="mt-4">
            <div class="text-body-2">
              <strong>Путь к файлам:</strong><br>
              Credentials: <code>{{ googleAuthInstructions.credentials_path }}</code><br>
              Token: <code>{{ googleAuthStatus?.paths?.token || 'N/A' }}</code>
            </div>
          </v-alert>
        </div>
        
        <div v-else class="text-center py-4">
          <v-progress-circular indeterminate></v-progress-circular>
        </div>
      </v-card-text>
      <v-divider></v-divider>
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn @click="showGoogleAuthInstructions = false">Закрыть</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { secureFetch } from '@/services/fetch'
import useMessageStore from '@/store/messages'
import { webSocketService } from '@/services/websocket'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const messageStore = useMessageStore()

const dialog = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const loading = ref(false)
const saving = ref(false)
const error = ref(null)
const valid = ref(false)
const form = ref(null)
const schemaInfo = ref(null)
const formData = ref({})
const googleAuthStatus = ref(null)
const googleAuthInstructions = ref(null)
const gettingToken = ref(false)
const showGoogleAuthInstructions = ref(false)
const showModuleInfoDialog = ref(false)
const selectedModule = ref(null)
const testingHost = ref(false)
const testingToken = ref(false)
const testingGoogleSheet = ref(false)

const schemaFields = computed(() => {
  if (!schemaInfo.value) {
    console.debug('AddonConfigDialog: schemaInfo.value is null')
    return []
  }
  
  if (!schemaInfo.value.schema) {
    console.debug('AddonConfigDialog: schemaInfo.value.schema is missing', schemaInfo.value)
    return []
  }
  
  const schema = schemaInfo.value.schema
  
  if (typeof schema !== 'object') {
    console.debug('AddonConfigDialog: schema is not an object', typeof schema, schema)
    return []
  }
  
  const keys = Object.keys(schema)
  if (keys.length === 0) {
    console.debug('AddonConfigDialog: schema is empty')
    return []
  }
  
  console.debug('AddonConfigDialog: Found schema fields:', keys.length, keys)
  
  return Object.values(schema).sort((a, b) => {
    // Сортируем: обязательные поля первыми, затем по группе, затем по имени
    if (a.required && !b.required) return -1
    if (!a.required && b.required) return 1
    if (a.group && b.group && a.group !== b.group) {
      return a.group.localeCompare(b.group)
    }
    return a.name.localeCompare(b.name)
  })
})

// Группировка полей по группам
const groupedFields = computed(() => {
  if (!schemaInfo.value || !schemaInfo.value.groups) {
    return []
  }
  
  const groups = schemaInfo.value.groups
  const schema = schemaInfo.value.schema || {}
  
  // Формируем список групп с полями
  const grouped = []
  
  for (const [groupKey, groupData] of Object.entries(groups)) {
    const groupFields = []
    const groupName = groupData.name || groupKey
    
    // Получаем поля для этой группы из плоской схемы
    // Используем два способа сопоставления:
    // 1. По полю group в fieldData
    // 2. По наличию поля в groupData.fields
    for (const [fieldKey, fieldData] of Object.entries(schema)) {
      let belongsToGroup = false
      
      // Проверяем по полю group
      if (fieldData.group === groupName) {
        belongsToGroup = true
      }
      // Проверяем по наличию в groupData.fields
      else if (groupData.fields && fieldKey in groupData.fields) {
        belongsToGroup = true
      }
      
      if (belongsToGroup) {
        groupFields.push(fieldData)
      }
    }
    
    if (groupFields.length > 0) {
      // Сортируем поля внутри группы: обязательные первыми, затем по имени
      groupFields.sort((a, b) => {
        if (a.required && !b.required) return -1
        if (!a.required && b.required) return 1
        return a.name.localeCompare(b.name)
      })
      
      grouped.push({
        key: groupKey,
        name: groupName,
        description: groupData.description || '',
        fields: groupFields
      })
    }
  }
  
  // Сортируем группы по порядку в исходном объекте groups
  return grouped
})

// Список модулей логирования для таблицы
const loggerModules = computed(() => {
  const modules = [
    'HA-Manager',
    'MyHome',
    'Database',
    'WebSocket',
    'API',
    'Config',
    'Device',
    'Port',
    'GoogleConnector',
    'Singleton'
  ]
  
  // Получаем описания модулей из схемы
  const descriptions = schemaInfo.value?.logger_module_descriptions || {}
  
  return modules.map(name => {
    const moduleInfo = descriptions[name] || {
      description: 'Модуль логирования',
      functions: []
    }
    return {
      name,
      levelKey: `log_module_${name}_level`,
      enabledKey: `log_module_${name}_enabled`,
      description: moduleInfo.description || 'Модуль логирования',
      functions: moduleInfo.functions || []
    }
  })
})

const getRules = (field) => {
  const rules = []
  
  if (field.required && field.type !== 'bool') {
    rules.push(v => !!v || `${field.name} обязательно для заполнения`)
  }
  
  if (field.type === 'int') {
    rules.push(v => !isNaN(v) || 'Должно быть числом')
    if (field.min !== undefined) {
      rules.push(v => v >= field.min || `Минимальное значение: ${field.min}`)
    }
    if (field.max !== undefined) {
      rules.push(v => v <= field.max || `Максимальное значение: ${field.max}`)
    }
  }
  
  if (field.type === 'str' && field.pattern) {
    try {
      const regex = new RegExp(field.pattern)
      rules.push(v => !v || regex.test(v) || 'Неверный формат')
    } catch (e) {
      console.warn('Invalid regex pattern:', field.pattern)
    }
  }
  
  return rules
}

const loadConfig = async () => {
  loading.value = true
  error.value = null
  
  try {
    // Загружаем схему
    const schemaResponseRaw = await secureFetch('/api/addon/config/schema')
    const schemaResponse = await schemaResponseRaw.json()
    console.debug('AddonConfigDialog: Schema response:', schemaResponse)
    schemaInfo.value = schemaResponse
    
    // Проверяем структуру ответа
    if (!schemaResponse || !schemaResponse.schema) {
      console.error('AddonConfigDialog: Invalid schema response structure:', schemaResponse)
      error.value = 'Неверная структура ответа от сервера'
      return
    }
    
    console.debug('AddonConfigDialog: Schema loaded, fields count:', Object.keys(schemaResponse.schema).length)
    
    // Загружаем текущие опции
    const optionsResponseRaw = await secureFetch('/api/addon/config/options')
    const optionsResponse = await optionsResponseRaw.json()
    console.debug('AddonConfigDialog: Options response:', optionsResponse)
    
    if (optionsResponse.success) {
      // Объединяем значения по умолчанию из схемы с текущими опциями
      const defaults = schemaInfo.value.defaults || {}
      formData.value = {
        ...defaults,
        ...optionsResponse.options
      }
      console.debug('AddonConfigDialog: Form data initialized:', Object.keys(formData.value).length, 'fields')
    } else {
      // Используем только значения по умолчанию
      formData.value = { ...(schemaInfo.value.defaults || {}) }
    }
    
    // Загружаем статус Google авторизации
    await loadGoogleAuthStatus()
  } catch (err) {
    console.error('Error loading config:', err)
    error.value = err.message || 'Ошибка загрузки конфигурации'
  } finally {
    loading.value = false
  }
}

// Обработчик WebSocket сообщений для обновления статуса Google авторизации
const handleGoogleAuthUpdate = (data) => {
  console.log('WebSocket: Google auth status updated', data)
  // Обновляем статус
  if (googleAuthStatus.value) {
    googleAuthStatus.value.token_exists = data.token_exists ?? true
  } else {
    // Если статус еще не загружен, загружаем его
    loadGoogleAuthStatus()
  }
  // Убираем индикатор загрузки
  gettingToken.value = false
  messageStore.showSuccess('Токен Google успешно получен и сохранен!')
}

// Подписка на WebSocket события при монтировании компонента
onMounted(() => {
  webSocketService.onMessage('addon_config', 'google_auth_updated', handleGoogleAuthUpdate)
})

// Отписка от WebSocket событий при размонтировании
onUnmounted(() => {
  webSocketService.offMessage('addon_config', 'google_auth_updated', handleGoogleAuthUpdate)
})

// Функция открытия модального окна с информацией о модуле
const openModuleInfo = (module) => {
  selectedModule.value = module
  showModuleInfoDialog.value = true
}

const loadGoogleAuthStatus = async () => {
  try {
    const statusResponseRaw = await secureFetch('/api/addon/config/google-auth/status')
    const statusResponse = await statusResponseRaw.json()
    googleAuthStatus.value = statusResponse
  } catch (err) {
    console.warn('Error loading Google auth status:', err)
  }
}

const loadGoogleAuthInstructions = async () => {
  if (googleAuthInstructions.value) return
  
  try {
    const instructionsResponseRaw = await secureFetch('/api/addon/config/google-auth/instructions')
    const instructionsResponse = await instructionsResponseRaw.json()
    googleAuthInstructions.value = instructionsResponse
  } catch (err) {
    console.error('Error loading Google auth instructions:', err)
    messageStore.showError('Ошибка загрузки инструкций')
  }
}

watch(showGoogleAuthInstructions, (newVal) => {
  if (newVal && !googleAuthInstructions.value) {
    loadGoogleAuthInstructions()
  }
})

const testHost = async () => {
  const haUrl = formData.value.ha_url
  if (!haUrl || !haUrl.trim()) {
    messageStore.showError('Введите URL Home Assistant')
    return
  }
  
  testingHost.value = true
  try {
    const responseRaw = await secureFetch(`/api/addon/config/homeassistant/test-host?ha_url=${encodeURIComponent(haUrl)}`, {
      method: 'POST'
    })
    const response = await responseRaw.json()
    
    if (response.success) {
      messageStore.showSuccess(response.message || 'Хост доступен')
    } else {
      messageStore.showError(response.error || 'Ошибка проверки хоста')
    }
  } catch (err) {
    console.error('Error testing HA host:', err)
    messageStore.showError(err.message || 'Ошибка при проверке хоста')
  } finally {
    testingHost.value = false
  }
}

const testToken = async () => {
  const haUrl = formData.value.ha_url
  const haToken = formData.value.ha_token
  
  // Проверка на пустоту токена
  if (!haToken || !haToken.trim()) {
    messageStore.showError('Токен не может быть пустым')
    return
  }
  
  if (!haUrl || !haUrl.trim()) {
    messageStore.showError('Введите URL Home Assistant')
    return
  }
  
  testingToken.value = true
  try {
    const responseRaw = await secureFetch(`/api/addon/config/homeassistant/test-token?ha_url=${encodeURIComponent(haUrl)}&ha_token=${encodeURIComponent(haToken)}`, {
      method: 'POST'
    })
    const response = await responseRaw.json()
    
    if (response.success) {
      messageStore.showSuccess(response.message || 'Токен валиден')
    } else {
      messageStore.showError(response.error || 'Ошибка проверки токена')
    }
  } catch (err) {
    console.error('Error testing HA token:', err)
    messageStore.showError(err.message || 'Ошибка при проверке токена')
  } finally {
    testingToken.value = false
  }
}

const extractGoogleSheetId = (value) => {
  if (!value) return null
  
  // Если это URL, извлекаем ID
  if (value.includes('/spreadsheets/d/')) {
    const parts = value.split('/spreadsheets/d/')
    if (parts.length > 1) {
      return parts[1].split('/')[0].split('?')[0].split('#')[0]
    }
  }
  
  // Если это просто ID (длинная строка без слешей)
  if (value.length > 20 && !value.includes('/')) {
    return value
  }
  
  return null
}

const getGoogleSheetUrl = (value) => {
  const id = extractGoogleSheetId(value)
  if (id) {
    return `https://docs.google.com/spreadsheets/d/${id}/edit`
  }
  return null
}

const openGoogleSheet = () => {
  const gsheetValue = formData.value.gsheet
  if (!gsheetValue) {
    messageStore.showError('Введите ID или URL Google таблицы')
    return
  }
  
  const url = getGoogleSheetUrl(gsheetValue)
  if (url) {
    window.open(url, '_blank')
  } else {
    messageStore.showError('Неверный формат ID или URL Google таблицы')
  }
}

const testGoogleSheet = async () => {
  const gsheetValue = formData.value.gsheet
  
  if (!gsheetValue || !gsheetValue.trim()) {
    messageStore.showError('Введите ID или URL Google таблицы')
    return
  }
  
  testingGoogleSheet.value = true
  try {
    const responseRaw = await secureFetch(`/api/addon/config/googlesheet/test?gsheet_id=${encodeURIComponent(gsheetValue)}`, {
      method: 'POST'
    })
    const response = await responseRaw.json()
    
    if (response.success) {
      messageStore.showSuccess(response.message || 'Таблица доступна')
      // Если получили URL, обновляем значение на ID
      if (response.spreadsheet_id && response.spreadsheet_id !== gsheetValue) {
        formData.value.gsheet = response.spreadsheet_id
      }
    } else {
      messageStore.showError(response.error || 'Ошибка проверки таблицы')
    }
  } catch (err) {
    console.error('Error testing Google Sheet:', err)
    messageStore.showError(err.message || 'Ошибка при проверке таблицы')
  } finally {
    testingGoogleSheet.value = false
  }
}

const getGoogleToken = async () => {
  if (!googleAuthStatus.value?.credentials_exists) {
    messageStore.showError('Сначала необходимо добавить файл google_credentials.json')
    showGoogleAuthInstructions.value = true
    return
  }
  
  gettingToken.value = true
  try {
    // Генерируем OAuth URL
    const urlResponseRaw = await secureFetch('/api/addon/config/google-auth/get-url')
    const urlResponse = await urlResponseRaw.json()
    
    if (!urlResponse.success || !urlResponse.auth_url) {
      throw new Error(urlResponse.message || 'Не удалось получить URL авторизации')
    }
    
    // Открываем URL в новой вкладке
    // После авторизации Google перенаправит на callback endpoint,
    // который автоматически обменяет код на токен и отправит WebSocket уведомление
    window.open(urlResponse.auth_url, '_blank', 'width=800,height=600')
    
    messageStore.showInfo('Откройте страницу авторизации в браузере. После авторизации токен будет сохранен автоматически и статус обновится.')
    
    // Статус обновится автоматически через WebSocket при успешном сохранении токена
    
  } catch (err) {
    console.error('Error getting Google token:', err)
    messageStore.showError(err.message || 'Ошибка при получении URL авторизации')
    gettingToken.value = false
  }
}

const save = async () => {
  if (!form.value) return
  if (!form.value.validate()) return
  
  saving.value = true
  
  try {
    const responseRaw = await secureFetch('/api/addon/config/options', {
      method: 'POST',
      data: formData.value
    })
    const response = await responseRaw.json()
    
    if (response.success) {
      messageStore.showSuccess('Конфигурация сохранена успешно')
      emit('saved', response.options)
      close()
    } else {
      throw new Error(response.message || 'Ошибка сохранения')
    }
  } catch (err) {
    console.error('Error saving config:', err)
    messageStore.showError(err.message || 'Ошибка сохранения конфигурации')
  } finally {
    saving.value = false
  }
}

const reloadConfig = async () => {
  await loadConfig()
  messageStore.showSuccess('Настройки перезагружены с сервера')
}

const close = () => {
  dialog.value = false
  formData.value = {}
  error.value = null
}

watch(dialog, (newVal) => {
  if (newVal) {
    loadConfig()
  }
})
</script>

<style scoped>
.logger-modules-table {
  font-size: 0.875rem;
}

.module-info-btn {
  opacity: 0.6;
  transition: opacity 0.2s;
}

.module-info-btn:hover {
  opacity: 1;
}

.logger-modules-table :deep(.v-table__wrapper) {
  overflow-x: auto;
}

.logger-modules-table :deep(.v-table th),
.logger-modules-table :deep(.v-table td) {
  padding: 8px 12px;
}
</style>

<style scoped>
.v-card-text {
  padding-top: 16px;
}
</style>

