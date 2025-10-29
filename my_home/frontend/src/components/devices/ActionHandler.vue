<template>
  <v-chip
    v-for="action in stateActions"
    :key="action.name"
    class="ml-2"
    :color="action?.color || 'info'"
    size="small"
  >
    <v-icon start small :icon="action.icon"/>
    {{ params[action.key] || '—' }}
  </v-chip>
  <v-spacer/>

  <div class="d-flex align-center">

    <template v-for="(action, index) in inlineActions" :key="index">
      <v-btn
        v-if="['request', 'json_form', 'table_modal'].includes(action.type)"
        :icon="!!action.icon"
        :loading="loadingAction === action.name"
        @click="handleAction(action)"
        class="mr-1"
        :class="{ 'ha-config-active': action.id === 'ha-config' && props.haConfigMode }"
        :title="action.name"
        :disabled="loadingAction === action.name"
        :color="action.id === 'ha-config' && props.haConfigMode ? 'orange' : undefined"
        :variant="action.id === 'ha-config' && props.haConfigMode ? 'elevated' : 'outlined'"
      >
        <v-icon v-if="action.icon" :icon="action.icon"/>
        <span v-else>{{ action.name }}</span>

        <!-- Badge для кнопки НАСТРОЙКА HA -->
        <v-badge
          v-if="action.id === 'ha-config' && props.haChangesCount > 0"
          :content="props.haChangesCount"
          color="primary"
          class="ha-config-badge"
          overlap
        >
        </v-badge>
      </v-btn>
    </template>

    <slot/>

    <v-menu v-if="menuActions && menuActions.length" location="bottom">
      <template #activator="{ props }">
        <v-btn icon v-bind="props">
          <v-icon icon="mdi-dots-vertical"/>
        </v-btn>
      </template>
      <v-list>
        <v-list-item
          v-for="(action, index) in menuActions"
          :key="index"
          @click="handleAction(action)"
        >
          <v-icon start :icon="action.icon || 'mdi-play-circle'"/>
          {{ action.name }}
        </v-list-item>
      </v-list>
    </v-menu>

    <template v-for="(action, index) in filteredActions" :key="'state-' + index">
      <v-chip
        v-if="action.type === 'state' && showState(action)"
        :color="action?.color || 'info'"
        size="small"
        class="ml-1"
      >
        <v-icon small :icon="action.icon"/>
        {{ liveState[action.key] || '—' }}
      </v-chip>
    </template>

    <JsonFormDialog
      v-if="jsonFormDialog"
      :action="activeAction"
      :params="params"
      @close="jsonFormDialog = false"
      @executed="emit('executed', $event)"
    />

    <TableModalDialog
      v-if="tableModalDialog"
      :action="activeAction"
      :params="params"
      @close="tableModalDialog = false"
      @executed="emit('executed', $event)"
    />

    <!-- Подтверждение и ввод -->
    <v-dialog v-model="inputDialog" max-width="500">
      <v-card>
        <v-card-title>{{ activeAction?.name }}</v-card-title>
        <v-card-text>
          <v-form>
            <v-container>
              <v-row>
                <v-col
                  v-for="(config, key) in activeAction?.input"
                  :key="key"
                  cols="12"
                >
                  <v-select
                    v-if="config.type === 'select'"
                    v-model="inputValues[key]"
                    :label="config.label || key"
                    :items="Object.entries(config.options || {}).map(([value, text]) => ({ title: text, value }))"
                    item-title="title"
                    item-value="value"
                    :required="config.required"
                    :disabled="loadingAction === activeAction?.name"
                  />
                  <v-text-field
                    v-else
                    v-model="inputValues[key]"
                    :label="config.label || key"
                    :type="config.type === 'int' ? 'number' : 'text'"
                    :min="config.min"
                    :max="config.max"
                    :required="config.required"
                    :disabled="loadingAction === activeAction?.name"
                  />
                </v-col>
              </v-row>
            </v-container>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer/>
          <v-btn text @click="inputDialog = false" :disabled="loadingAction === activeAction?.name">Отмена</v-btn>
          <v-btn color="primary" @click="submitAction" :loading="loadingAction === activeAction?.name">Отправить</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="confirmDialog" max-width="400">
      <v-card>
        <v-card-title class="text-h6">Подтверждение</v-card-title>
        <v-card-text>Вы уверены, что хотите выполнить действие: <b>{{ activeAction?.name }}</b>?</v-card-text>
        <v-card-actions>
          <v-spacer/>
          <v-btn text @click="confirmDialog = false" :disabled="loadingAction === activeAction?.name">Отмена</v-btn>
          <v-btn color="red darken-1" text @click="confirmAndExecute" :loading="loadingAction === activeAction?.name">
            Подтвердить
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Модалка для изменений HA -->
    <v-dialog v-model="haChangesModal" max-width="1200" scrollable>
      <v-card>
        <v-card-title class="text-h6">
          <v-icon icon="mdi-home-assistant" class="me-2"></v-icon>
          Управление портами Home Assistant
        </v-card-title>
        <v-card-text>
          <!-- Фильтры с легендой -->
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="py-2">
              <v-icon class="me-2">mdi-filter</v-icon>
              Фильтры и типы портов
            </v-card-title>
            <v-card-text class="pt-0">
              <v-row>
                <v-col cols="12" md="4">
                  <v-text-field
                    v-model="modalFilters.searchQuery"
                    label="Поиск портов"
                    prepend-inner-icon="mdi-magnify"
                    variant="outlined"
                    density="compact"
                    clearable
                  ></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-select
                    v-model="modalFilters.deviceId"
                    :items="deviceOptions"
                    label="Устройство"
                    variant="outlined"
                    density="compact"
                    clearable
                  ></v-select>
                </v-col>
                <v-col cols="12" md="4">
                  <div class="text-caption text-grey mb-2">Всего портов: {{ portCounts.total }}</div>
                </v-col>
              </v-row>
              
              <!-- Фильтры по типам действий -->
              <v-row>
                <v-col cols="12">
                  <div class="d-flex flex-wrap gap-2">
                    <v-chip
                      :color="modalFilters.showAdd ? 'success' : 'default'"
                      :variant="modalFilters.showAdd ? 'elevated' : 'outlined'"
                      @click="modalFilters.showAdd = !modalFilters.showAdd"
                      clickable
                    >
                      <v-icon start :icon="modalFilters.showAdd ? 'mdi-check-circle' : 'mdi-circle-outline'"></v-icon>
                      Новые ({{ portCounts.add }})
                    </v-chip>
                    
                    <v-chip
                      :color="modalFilters.showRemove ? 'error' : 'default'"
                      :variant="modalFilters.showRemove ? 'elevated' : 'outlined'"
                      @click="modalFilters.showRemove = !modalFilters.showRemove"
                      clickable
                    >
                      <v-icon start :icon="modalFilters.showRemove ? 'mdi-check-circle' : 'mdi-circle-outline'"></v-icon>
                      Удаляемые ({{ portCounts.remove }})
                    </v-chip>
                    
                    <v-chip
                      :color="modalFilters.showUpdate ? 'info' : 'default'"
                      :variant="modalFilters.showUpdate ? 'elevated' : 'outlined'"
                      @click="modalFilters.showUpdate = !modalFilters.showUpdate"
                      clickable
                    >
                      <v-icon start :icon="modalFilters.showUpdate ? 'mdi-check-circle' : 'mdi-circle-outline'"></v-icon>
                      Обновляемые ({{ portCounts.update }})
                    </v-chip>
                    
                    <v-spacer></v-spacer>
                    
                    <v-btn
                      size="small"
                      variant="text"
                      @click="selectAllTypes"
                      :disabled="modalFilters.showAdd && modalFilters.showRemove && modalFilters.showUpdate"
                    >
                      <v-icon start>mdi-check-all</v-icon>
                      Выбрать все
                    </v-btn>
                    
                    <v-btn
                      size="small"
                      variant="text"
                      @click="deselectAllTypes"
                      :disabled="!modalFilters.showAdd && !modalFilters.showRemove && !modalFilters.showUpdate"
                    >
                      <v-icon start>mdi-close-circle</v-icon>
                      Снять все
                    </v-btn>
                  </div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>


          <!-- Структурированный список изменений -->
          <div v-for="device in filteredStructuredChanges" :key="device.id" class="mb-4">
            <v-card variant="outlined" class="mb-2">
              <v-card-title class="text-subtitle-1 pa-3">
                <div class="d-flex align-center">
                  <v-checkbox
                    :model-value="isAllDevicePortsSelected(device.id)"
                    :indeterminate="isSomeDevicePortsSelected(device.id)"
                    @update:model-value="toggleAllDevicePorts(device.id)"
                    hide-details
                    density="compact"
                    class="me-2"
                  ></v-checkbox>
                  <v-icon icon="mdi-devices" class="me-2"></v-icon>
                  {{ device.name }}
                  <v-chip size="small" class="ml-2">{{ device.groups.length }} групп</v-chip>
                </div>
              </v-card-title>

              <v-card-text class="pa-3">
                <div v-if="device.groups.length === 0" class="text-grey">
                  Нет групп с изменениями
                </div>
                <div v-for="group in device.groups" :key="group.title" class="mb-3">
                  <div class="text-subtitle-2 mb-2">
                    <v-icon icon="mdi-folder" class="me-1"></v-icon>
                    {{ group.title }}
                    <v-chip size="small" class="ml-2">{{ group.ports.length }} портов</v-chip>
                  </div>

                  <div v-if="group.ports.length === 0" class="ml-4 text-grey text-caption">
                    Нет портов с изменениями в этой группе
                  </div>

                  <!-- Таблица портов -->
                  <v-table v-else class="ml-4" density="compact">
                    <thead>
                    <tr>
                      <th width="50">
                        <v-checkbox
                          :model-value="isAllGroupPortsSelected(device.id, group)"
                          @update:model-value="toggleAllGroupPorts(device.id, group)"
                          hide-details
                          density="compact"
                          indeterminate
                        ></v-checkbox>
                      </th>
                      <th width="50"></th>
                      <th>Название</th>
                      <th v-if="group.ports.some(p => p.action === 'add' || p.action === 'update')">Entity ID</th>
                      <th v-if="group.ports.some(p => p.action === 'add' || p.action === 'update')">Дружественное имя</th>
                      <th v-if="group.ports.some(p => p.action === 'add' || p.action === 'update')">Класс</th>
                      <th v-if="group.ports.some(p => p.action === 'add' || p.action === 'update')">Единица</th>
                      <th v-if="group.ports.some(p => p.action === 'add' || p.action === 'update')">Иконка</th>
                      <th v-if="group.ports.some(p => p.action === 'add' || p.action === 'update')" width="120">Действия</th>
                    </tr>
                    </thead>
                    <tbody>
                    <template v-for="port in group.ports" :key="port.code">
                      <tr
                        :class="{
                          'success-row': port.action === 'add',
                          'error-row': port.action === 'remove',
                          'info-row': port.action === 'update'
                        }"
                      >
                        <!-- Чекбокс выбора -->
                        <td>
                          <v-checkbox
                            v-model="selectedPorts"
                            :value="`${device.id}-${port.code}`"
                            hide-details
                            density="compact"
                          ></v-checkbox>
                        </td>

                        <!-- Действие -->
                        <td>
                          <v-icon
                            :icon="getActionIcon(port.action)"
                            :color="getActionColor(port.action)"
                            size="small"
                          ></v-icon>
                        </td>

                        <!-- Название -->
                        <td>
                          <v-tooltip location="top">
                            <template #activator="{ props: tooltipProps }">
                              <span v-bind="tooltipProps" class="font-weight-medium">{{ port.name }}</span>
                            </template>
                            <span>Название порта из системы устройства</span>
                          </v-tooltip>
                        </td>

                        <!-- Entity ID для добавляемых/обновляемых портов -->
                        <td v-if="group.ports.some(p => p.action === 'add' || p.action === 'update')">
                          <div v-if="port.action === 'add' || port.action === 'update'">
                            <v-tooltip location="top">
                              <template #activator="{ props: tooltipProps }">
                                <v-text-field
                                  v-bind="tooltipProps"
                                  v-model="getPortParameters(device.id, port.code).entity_id"
                                  @update:model-value="onParamChange(device.id, port.code)"
                                  density="compact"
                                  variant="outlined"
                                  hide-details
                                  class="port-parameter-field"
                                ></v-text-field>
                              </template>
                              <span>Уникальный идентификатор сущности в Home Assistant (например: switch.myhome2_gpio_27_0)</span>
                            </v-tooltip>
                          </div>
                          <div v-else class="text-grey text-caption">
                            —
                          </div>
                        </td>

                        <!-- Дружественное имя -->
                        <td v-if="group.ports.some(p => p.action === 'add' || p.action === 'update')">
                          <div v-if="port.action === 'add' || port.action === 'update'">
                            <v-tooltip location="top">
                              <template #activator="{ props: tooltipProps }">
                                <v-text-field
                                  v-bind="tooltipProps"
                                  v-model="getPortParameters(device.id, port.code).friendly_name"
                                  @update:model-value="onParamChange(device.id, port.code)"
                                  density="compact"
                                  variant="outlined"
                                  hide-details
                                  class="port-parameter-field"
                                  placeholder="Дружественное имя"
                                ></v-text-field>
                              </template>
                              <span>Дружественное имя для отображения в Home Assistant</span>
                            </v-tooltip>
                          </div>
                          <div v-else class="text-grey text-caption">
                            —
                          </div>
                        </td>

                        <!-- Класс устройства -->
                        <td v-if="group.ports.some(p => p.action === 'add' || p.action === 'update')">
                          <div v-if="port.action === 'add' || port.action === 'update'">
                            <v-tooltip location="top">
                              <template #activator="{ props: tooltipProps }">
                                <v-select
                                  v-bind="tooltipProps"
                                  v-model="getPortParameters(device.id, port.code).device_class"
                                  :items="deviceClassOptions"
                                  @update:model-value="onParamChange(device.id, port.code)"
                                  density="compact"
                                  variant="outlined"
                                  hide-details
                                  class="port-parameter-field"
                                  clearable
                                ></v-select>
                              </template>
                              <span>Класс устройства для определения типа и иконки (temperature, humidity, pressure, switch и т.д.)</span>
                            </v-tooltip>
                          </div>
                          <div v-else class="text-grey text-caption">
                            —
                          </div>
                        </td>

                        <!-- Единица измерения -->
                        <td v-if="group.ports.some(p => p.action === 'add' || p.action === 'update')">
                          <div v-if="port.action === 'add' || port.action === 'update'">
                            <v-tooltip location="top">
                              <template #activator="{ props: tooltipProps }">
                                <v-select
                                  v-bind="tooltipProps"
                                  v-model="getPortParameters(device.id, port.code).unit_of_measurement"
                                  :items="unitOptions"
                                  @update:model-value="onParamChange(device.id, port.code)"
                                  density="compact"
                                  variant="outlined"
                                  hide-details
                                  class="port-parameter-field"
                                  clearable
                                ></v-select>
                              </template>
                              <span>Единица измерения значения (ºC, %, hPa, V, A, W, kWh и т.д.)</span>
                            </v-tooltip>
                          </div>
                          <div v-else class="text-grey text-caption">
                            —
                          </div>
                        </td>

                        <!-- Иконка -->
                        <td v-if="group.ports.some(p => p.action === 'add' || p.action === 'update')">
                          <div v-if="port.action === 'add' || port.action === 'update'">
                            <v-tooltip location="top">
                              <template #activator="{ props: tooltipProps }">
                                <v-text-field
                                  v-bind="tooltipProps"
                                  v-model="getPortParameters(device.id, port.code).icon"
                                  @update:model-value="onParamChange(device.id, port.code)"
                                  density="compact"
                                  variant="outlined"
                                  hide-details
                                  class="port-parameter-field"
                                  placeholder="mdi:icon-name"
                                ></v-text-field>
                              </template>
                              <span>Material Design Icons (MDI) иконка. Формат: mdi:icon-name</span>
                            </v-tooltip>
                          </div>
                          <div v-else class="text-grey text-caption">
                            —
                          </div>
                        </td>

                        <!-- Действия для новых и обновляемых портов -->
                        <td v-if="group.ports.some(p => p.action === 'add' || p.action === 'update')">
                          <div v-if="port.action === 'add' || port.action === 'update'" class="d-flex gap-1">
                            <!-- Кнопка дополнительных параметров -->
                            <v-btn
                              icon
                              size="small"
                              variant="text"
                              @click="togglePortExpansion(device.id, port.code)"
                              :color="isPortExpanded(device.id, port.code) ? 'primary' : 'default'"
                              :title="port.action === 'add' ? 'Дополнительные настройки' : 'Дополнительные свойства'"
                            >
                              <v-icon
                                :icon="isPortExpanded(device.id, port.code) ? 'mdi-cog' : 'mdi-cog-outline'"
                                size="small"
                              ></v-icon>
                            </v-btn>
                            
                            <!-- Кнопка сброса -->
                            <v-btn
                              icon
                              size="small"
                              variant="text"
                              @click="resetPortParameters(device.id, port.code, port.action)"
                              :title="port.action === 'add' ? 'Сбросить в дефолт' : 'Сбросить к текущей версии'"
                              color="warning"
                            >
                              <v-icon
                                :icon="port.action === 'add' ? 'mdi-restore' : 'mdi-refresh'"
                                size="small"
                              ></v-icon>
                            </v-btn>
                          </div>
                          <div v-else class="text-grey text-caption">
                            —
                          </div>
                        </td>
                      </tr>

                      <!-- Разворачивающийся блок с параметрами -->
                      <tr
                        v-if="(port.action === 'add' || port.action === 'update') && isPortExpanded(device.id, port.code)"
                        class="port-parameters-row"
                      >
                        <td :colspan="group.ports.some(p => p.action === 'add' || p.action === 'update') ? 7 : 6">
                          <v-card variant="tonal" class="ma-2">
                            <v-card-text>
                              <div class="text-h6 mb-3">
                                <v-icon icon="mdi-cog" class="me-2"></v-icon>
                                Параметры порта: {{ port.name }}
                              </div>

                              <v-row>
                                <v-col cols="12" md="6">
                                  <v-tooltip location="top">
                                    <template #activator="{ props: tooltipProps }">
                                      <v-text-field
                                        v-bind="tooltipProps"
                                        v-model="getPortParameters(device.id, port.code).name"
                                        @update:model-value="onParamChange(device.id, port.code)"
                                        label="Название"
                                        hint="Отображаемое название"
                                        persistent-hint
                                        density="compact"
                                      ></v-text-field>
                                    </template>
                                    <span>Отображаемое название сущности в Home Assistant</span>
                                  </v-tooltip>
                                </v-col>


                                <v-col cols="12" md="6">
                                  <v-tooltip location="top">
                                    <template #activator="{ props: tooltipProps }">
                                      <v-select
                                        v-bind="tooltipProps"
                                        v-model="getPortParameters(device.id, port.code).state_class"
                                        @update:model-value="onParamChange(device.id, port.code)"
                                        label="Класс состояния"
                                        :items="stateClassOptions"
                                        hint="Выберите класс состояния"
                                        persistent-hint
                                        density="compact"
                                        clearable
                                      ></v-select>
                                    </template>
                                    <span>Класс состояния для отображения в графиках Home Assistant (measurement, total, total_increasing, total_decreasing)</span>
                                  </v-tooltip>
                                </v-col>

                                <v-col cols="12" md="6">
                                  <v-tooltip location="top">
                                    <template #activator="{ props: tooltipProps }">
                                      <v-select
                                        v-bind="tooltipProps"
                                        v-model="getPortParameters(device.id, port.code).entity_category"
                                        label="Категория сущности"
                                        :items="entityCategoryOptions"
                                        hint="Выберите категорию"
                                        persistent-hint
                                        density="compact"
                                        clearable
                                      ></v-select>
                                    </template>
                                    <span>Категория сущности: config (настройки), diagnostic (диагностика), measurement (измерения)</span>
                                  </v-tooltip>
                                </v-col>

                                <v-col cols="12" md="6">
                                  <v-tooltip location="top">
                                    <template #activator="{ props: tooltipProps }">
                                      <v-text-field
                                        v-bind="tooltipProps"
                                        v-model="getPortParameters(device.id, port.code).icon"
                                        label="Иконка"
                                        hint="MDI иконка (например: mdi:thermometer)"
                                        persistent-hint
                                        density="compact"
                                        placeholder="mdi:icon-name"
                                      ></v-text-field>
                                    </template>
                                    <span>Material Design Icons (MDI) иконка для отображения в Home Assistant. Формат: mdi:icon-name</span>
                                  </v-tooltip>
                                </v-col>

                                <v-col cols="12" md="6">
                                  <v-tooltip location="top">
                                    <template #activator="{ props: tooltipProps }">
                                      <v-select
                                        v-bind="tooltipProps"
                                        v-model="getPortParameters(device.id, port.code).enabled_by_default"
                                        label="Включен по умолчанию"
                                        :items="booleanOptions"
                                        hint="Включен ли по умолчанию"
                                        persistent-hint
                                        density="compact"
                                      ></v-select>
                                    </template>
                                    <span>Если включено, сущность будет отображаться в Home Assistant по умолчанию</span>
                                  </v-tooltip>
                                </v-col>

                                <v-col cols="12" md="6">
                                  <v-tooltip location="top">
                                    <template #activator="{ props: tooltipProps }">
                                      <v-select
                                        v-bind="tooltipProps"
                                        v-model="getPortParameters(device.id, port.code).force_update"
                                        label="Принудительное обновление"
                                        :items="booleanOptions"
                                        hint="Принудительное обновление"
                                        persistent-hint
                                        density="compact"
                                      ></v-select>
                                    </template>
                                    <span>Если включено, Home Assistant будет обновлять состояние даже если значение не изменилось</span>
                                  </v-tooltip>
                                </v-col>

                                <v-col cols="12" md="6">
                                  <v-tooltip location="top">
                                    <template #activator="{ props: tooltipProps }">
                                      <v-text-field
                                        v-bind="tooltipProps"
                                        v-model="getPortParameters(device.id, port.code).suggested_display_precision"
                                        label="Точность отображения"
                                        hint="Количество знаков после запятой"
                                        persistent-hint
                                        density="compact"
                                        type="number"
                                      ></v-text-field>
                                    </template>
                                    <span>Количество знаков после запятой для отображения значения в Home Assistant</span>
                                  </v-tooltip>
                                </v-col>

                                <v-col cols="12">
                                  <div class="mb-2">
                                    <label class="text-caption text-grey">Дополнительные атрибуты (JSON)</label>
                                  </div>
                                  <JsonEditorVue
                                    v-model="getPortParameters(device.id, port.code).attributes"
                                    :show-btns="false"
                                    :expandedOnStart="true"
                                    :mode="'code'"
                                    :main-menu-bar="false"
                                    :navigation-bar="false"
                                    :status-bar="false"
                                    class="json-editor"
                                  />
                                </v-col>

                                <v-col cols="12">
                                  <v-expansion-panels variant="accordion">
                                    <v-expansion-panel>
                                      <v-expansion-panel-title>
                                        <v-icon icon="mdi-eye" class="me-2"></v-icon>
                                        Предварительный просмотр конфигурации
                                      </v-expansion-panel-title>
                                      <v-expansion-panel-text>
                                        <pre class="text-caption">{{
                                            JSON.stringify(getFormattedPortParameters(device.id, port.code), null, 2)
                                          }}</pre>
                                      </v-expansion-panel-text>
                                    </v-expansion-panel>
                                  </v-expansion-panels>
                                </v-col>
                              </v-row>
                            </v-card-text>
                          </v-card>
                        </td>
                      </tr>
                    </template>
                    </tbody>
                  </v-table>
                </div>
              </v-card-text>
            </v-card>
          </div>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            text
            @click="haChangesModal = false"
            color="grey"
          >
            Отмена
          </v-btn>
          <v-btn
            color="error"
            @click="discardChanges"
          >
            Отменить все изменения
          </v-btn>
          <v-btn
            color="primary"
            @click="saveSelectedChanges"
            :disabled="selectedPorts.length === 0 || savingChanges"
            :loading="savingChanges"
          >
            <span v-if="!savingChanges">Сохранить выбранные ({{ selectedPorts.length }})</span>
            <span v-else>Сохранение...</span>
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Диалог редактирования параметров порта -->
    <v-dialog v-model="showPortEditDialog" max-width="600px">
      <v-card>
        <v-card-title>
          <v-icon icon="mdi-cog" class="me-2"></v-icon>
          Редактирование параметров порта
        </v-card-title>

        <v-card-text>
          <v-form>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="portParameters.entity_id"
                  label="Entity ID"
                  hint="Уникальный идентификатор в Home Assistant"
                  persistent-hint
                ></v-text-field>
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="portParameters.name"
                  label="Название"
                  hint="Отображаемое название"
                  persistent-hint
                ></v-text-field>
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="portParameters.device_class"
                  label="Класс устройства"
                  hint="Например: temperature, humidity, power"
                  persistent-hint
                ></v-text-field>
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="portParameters.unit_of_measurement"
                  label="Единица измерения"
                  hint="Например: °C, %, W, V"
                  persistent-hint
                ></v-text-field>
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="portParameters.icon"
                  label="Иконка"
                  hint="Например: mdi:thermometer, mdi:gauge"
                  persistent-hint
                ></v-text-field>
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="portParameters.state_class"
                  label="Класс состояния"
                  hint="Например: measurement, total_increasing"
                  persistent-hint
                ></v-text-field>
              </v-col>

              <v-col cols="12">
                <v-textarea
                  v-model="portParameters.attributes"
                  label="Дополнительные атрибуты (JSON)"
                  hint="Дополнительные параметры в формате JSON"
                  persistent-hint
                  rows="3"
                ></v-textarea>
              </v-col>
            </v-row>
          </v-form>

          <!-- Предварительный просмотр конфигурации -->
          <v-expansion-panels class="mt-4">
            <v-expansion-panel>
              <v-expansion-panel-title>
                <v-icon icon="mdi-eye" class="me-2"></v-icon>
                Предварительный просмотр конфигурации
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <pre class="text-caption">{{
                    JSON.stringify({
                      entity_id: portParameters.entity_id,
                      name: portParameters.name,
                      device_class: portParameters.device_class,
                      unit_of_measurement: portParameters.unit_of_measurement,
                      icon: portParameters.icon,
                      state_class: portParameters.state_class,
                      attributes: portParameters.attributes
                    }, null, 2)
                  }}</pre>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn @click="cancelPortEdit">
            Отмена
          </v-btn>
          <v-btn color="primary" @click="savePortParameters">
            Сохранить
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import {ref, computed} from 'vue'
import {secureFetch} from '@/services/fetch'
import useMessageStore from '@/store/messages'
import JsonFormDialog from '@/components/devices/JsonFormDialog.vue'
import TableModalDialog from '@/components/devices/TableModalDialog.vue'
import {useTableStore} from '@/store/tables'
import {useHAChangesStore} from '@/store/haChangesStore'
import {objectToFlat} from '@/utils/array'
import JsonEditorVue from 'json-editor-vue'

const props = defineProps({
  actions: Array,
  params: Object,
  haConfigMode: {
    type: Boolean,
    default: false
  },
  haChangesCount: {
    type: Number,
    default: 0
  },
  hasHAChanges: {
    type: Boolean,
    default: false
  },
  devices: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['executed', 'toggle-ha-config', 'update:haConfigMode'])
const messageStore = useMessageStore()
const haChangesStore = useHAChangesStore()

const loadingAction = ref(null)
const inputDialog = ref(false)
const confirmDialog = ref(false)
const jsonFormDialog = ref(false)
const tableModalDialog = ref(false)
const haChangesModal = ref(false)
const selectedPorts = ref([])
const savingChanges = ref(false)

// Редактирование параметров порта
const editingPort = ref(null)
const portParameters = ref({
  entity_id: '',
  name: '',
  device_class: '',
  unit_of_measurement: '',
  icon: '',
  state_class: '',
  attributes: {}
})
const showPortEditDialog = ref(false)

// Управление разворачиванием портов
const expandedPorts = ref(new Set())
const portParametersData = ref({})

// Фильтры для модалки
const modalFilters = ref({
  searchQuery: '',
  actionType: null,
  deviceId: null,
  showAdd: true,
  showRemove: true,
  showUpdate: true
})

// Опции для фильтров
const deviceOptions = computed(() => {
  return props.devices.map(device => ({
    title: device.name,
    value: device.id
  }))
})

// Опции для выпадающих списков
const deviceClassOptions = [
  'battery',
  'current',
  'energy',
  'frequency',
  'gas',
  'humidity',
  'illuminance',
  'monetary',
  'nitrogen_dioxide',
  'nitrogen_monoxide',
  'nitrous_oxide',
  'ozone',
  'pm1',
  'pm10',
  'pm25',
  'power',
  'power_factor',
  'pressure',
  'signal_strength',
  'sulphur_dioxide',
  'temperature',
  'timestamp',
  'volatile_organic_compounds',
  'voltage'
]

const unitOptions = [
  '°C', '°F', 'K',
  '%', 'ppm', 'ppb',
  'W', 'kW', 'MW',
  'V', 'A', 'mA',
  'Hz', 'kHz', 'MHz',
  'Pa', 'hPa', 'kPa', 'MPa',
  'bar', 'mbar', 'μbar',
  'psi', 'mmHg', 'inHg',
  'lux', 'lx',
  'dB', 'dBm',
  's', 'min', 'h', 'd',
  'm', 'km', 'cm', 'mm',
  'm²', 'm³', 'L', 'mL',
  'kg', 'g', 'mg', 'μg',
  'J', 'kJ', 'MJ', 'kWh', 'MWh'
]

const iconOptions = [
  'mdi:thermometer',
  'mdi:gauge',
  'mdi:lightbulb',
  'mdi:power',
  'mdi:battery',
  'mdi:water',
  'mdi:weather-windy',
  'mdi:weather-rainy',
  'mdi:weather-sunny',
  'mdi:weather-cloudy',
  'mdi:home',
  'mdi:car',
  'mdi:phone',
  'mdi:laptop',
  'mdi:monitor',
  'mdi:television',
  'mdi:speaker',
  'mdi:microphone',
  'mdi:camera',
  'mdi:lock',
  'mdi:unlock',
  'mdi:door',
  'mdi:window',
  'mdi:fan',
  'mdi:air-conditioner',
  'mdi:heater',
  'mdi:fire',
  'mdi:smoke',
  'mdi:water-pump',
  'mdi:valve',
  'mdi:switch',
  'mdi:button',
  'mdi:knob',
  'mdi:slider',
  'mdi:toggle-switch',
  'mdi:checkbox',
  'mdi:radio',
  'mdi:checkbox-marked',
  'mdi:checkbox-blank',
  'mdi:radiobox-marked',
  'mdi:radiobox-blank'
]

const stateClassOptions = [
  'measurement',
  'total',
  'total_increasing',
  'total_decreasing'
]

const entityCategoryOptions = [
  'config',
  'diagnostic',
  'measurement'
]

const booleanOptions = [
  {title: 'Да', value: 'true'},
  {title: 'Нет', value: 'false'}
]

const activeAction = ref(null)
const inputValues = ref({})
let deferredSubmit = null

const filteredActions = computed(() => props.actions)
const inlineActions = computed(() => props.actions?.filter(a => a.type !== 'state' && a.menu !== 1))
const menuActions = computed(() => props.actions?.filter(a => a.menu === 1))
const stateActions = computed(() => props.actions?.filter(a => a.type === 'state'))

const tableStore = useTableStore()

const liveState = computed(() => objectToFlat(props.params || {}))

// Данные устройств с портами, загруженные из API
const devicesWithPorts = ref({})

// Загрузка данных устройства с портами из API
const loadDevicePorts = async (deviceId) => {
  // Проверяем, есть ли уже загруженные данные
  if (devicesWithPorts.value[deviceId]) {
    return devicesWithPorts.value[deviceId]
  }

  const device = props.devices.find(d => d.id == deviceId)
  if (!device || !device.params?.ip) {
    return null
  }

  try {
    const response = await secureFetch(`/api/live/${device.params.ip}/get_value`)
    const data = await response.json()
    
    // Сохраняем загруженные данные
    devicesWithPorts.value[deviceId] = {
      ...device,
      apiData: data
    }
    
    return devicesWithPorts.value[deviceId]
  } catch (error) {
    console.error('Failed to load device ports:', error)
    return null
  }
}

// Структурированные данные изменений HA
const structuredChanges = computed(() => {
  const changes = haChangesStore.getAllChanges()
  console.log('HA Changes from store:', changes)
  console.log('Available devices:', props.devices)
  console.log('Devices with ports:', devicesWithPorts.value)

  const result = []

  // Проходим по всем устройствам
  props.devices.forEach(device => {
    const deviceId = device.id
    const deviceChanges = changes[deviceId] || {}
    
    // Используем загруженные данные устройства с портами
    const deviceWithPorts = devicesWithPorts.value[deviceId] || device
    console.log(`Processing device ${deviceId}:`, deviceWithPorts)

    const deviceData = {
      id: device.id,
      name: device.name,
      groups: []
    }

    // Группируем порты по группам
    const groupsMap = new Map()

    // 1. Добавляем порты с изменениями (новые/удаленные)
    Object.keys(deviceChanges).forEach(portCode => {
      const action = deviceChanges[portCode]
      const port = findPortInDevice(deviceWithPorts, portCode)
      console.log(`Looking for port ${portCode} in device ${deviceId}:`, port)
      if (!port) return

      // Определяем название группы на основе порта
      const groupTitle = getGroupTitleForPort(deviceWithPorts, port)
      console.log(`Group title for port ${portCode}:`, groupTitle)

      if (!groupsMap.has(groupTitle)) {
        groupsMap.set(groupTitle, {
          title: groupTitle,
          ports: []
        })
      }

      console.log(`Adding changed port to group ${groupTitle}:`, {
        code: portCode,
        name: port.name,
        type: port.type,
        unit: port.unit,
        port: port
      })
      
      groupsMap.get(groupTitle).ports.push({
        code: portCode,
        name: port.name || portCode,
        action: action,
        port: port
      })
    })

    // 2. Добавляем порты, которые уже есть в HA (для обновления)
    const existingHAPorts = findExistingHAPorts(deviceWithPorts)
    existingHAPorts.forEach(port => {
      const portCode = port.code
      
      // Пропускаем порты, которые уже есть в изменениях
      if (deviceChanges[portCode]) return

      // Определяем название группы на основе порта
      const groupTitle = getGroupTitleForPort(deviceWithPorts, port)
      console.log(`Group title for existing HA port ${portCode}:`, groupTitle)

      if (!groupsMap.has(groupTitle)) {
        groupsMap.set(groupTitle, {
          title: groupTitle,
          ports: []
        })
      }

      console.log(`Adding existing HA port to group ${groupTitle}:`, {
        code: portCode,
        name: port.name,
        type: port.type,
        unit: port.unit,
        port: port
      })
      
      groupsMap.get(groupTitle).ports.push({
        code: portCode,
        name: port.name || portCode,
        action: 'update', // Новый тип действия
        port: port
      })
    })

    // Преобразуем Map в массив
    deviceData.groups = Array.from(groupsMap.values())
    console.log(`Final device data for ${deviceId}:`, deviceData)
    
    // Добавляем устройство только если есть группы с портами
    if (deviceData.groups.length > 0) {
      result.push(deviceData)
    }
  })

  console.log('Final structured changes:', result)
  return result
})

// Фильтрованные данные для модалки
const filteredStructuredChanges = computed(() => {
  let filtered = structuredChanges.value

  // Фильтр по устройству
  if (modalFilters.value.deviceId) {
    filtered = filtered.filter(device => device.id == modalFilters.value.deviceId)
  }

  // Фильтр по типу действия и поисковому запросу
  filtered = filtered.map(device => {
    const filteredGroups = device.groups.map(group => {
      const filteredPorts = group.ports.filter(port => {
        // Фильтр по типу действия (новые фильтры)
        if (port.action === 'add' && !modalFilters.value.showAdd) return false
        if (port.action === 'remove' && !modalFilters.value.showRemove) return false
        if (port.action === 'update' && !modalFilters.value.showUpdate) return false

        // Фильтр по поисковому запросу
        if (modalFilters.value.searchQuery) {
          const query = modalFilters.value.searchQuery.toLowerCase()
          const name = (port.name || '').toLowerCase()
          const code = (port.code || '').toLowerCase()
          const deviceName = (device.name || '').toLowerCase()
          
          if (!name.includes(query) && !code.includes(query) && !deviceName.includes(query)) {
            return false
          }
        }

        return true
      })

      return {
        ...group,
        ports: filteredPorts
      }
    }).filter(group => group.ports.length > 0)

    return {
      ...device,
      groups: filteredGroups
    }
  }).filter(device => device.groups.length > 0)

  return filtered
})

// Подсчет портов по типам действий
const portCounts = computed(() => {
  const counts = {
    add: 0,
    remove: 0,
    update: 0,
    total: 0
  }

  structuredChanges.value.forEach(device => {
    device.groups.forEach(group => {
      group.ports.forEach(port => {
        counts[port.action]++
        counts.total++
      })
    })
  })

  return counts
})

// Функция для поиска порта в устройстве
function findPortInDevice(device, portCode) {
  console.log(`Searching for port ${portCode} in device:`, device)
  console.log('Device groups:', device.groups)
  console.log('Device apiData:', device.apiData)

  // Если есть данные из API (apiData), ищем в них
  if (device.apiData && Array.isArray(device.apiData)) {
    console.log('Searching in apiData...')
    
    // Рекурсивная функция поиска в структуре данных
    const findPortRecursive = (data) => {
      if (!data) return null
      
      // Если это массив, проверяем каждый элемент
      if (Array.isArray(data)) {
        for (const item of data) {
          const found = findPortRecursive(item)
          if (found) return found
        }
      } 
      // Если это объект
      else if (typeof data === 'object') {
        // Проверяем, является ли это портом с нужным кодом
        if (data.code === portCode) {
          console.log('Found port in apiData:', data)
          return data
        }
        
        // Ищем в полях data и items
        if (data.data) {
          const found = findPortRecursive(data.data)
          if (found) return found
        }
        if (data.items) {
          const found = findPortRecursive(data.items)
          if (found) return found
        }
      }
      
      return null
    }
    
    const port = findPortRecursive(device.apiData)
    if (port) {
      return port
    }
  }

  // Если есть группы, ищем в них
  if (device.groups) {
    for (const group of device.groups) {
      console.log('Checking group:', group)
      if (group.items) {
        console.log('Group items:', group.items)
        const port = group.items.find(item => item.code === portCode)
        if (port) {
          console.log('Found port in group:', port)
          return port
        }
      }
    }
  }

  // Если нет групп или не нашли в группах, ищем в других местах
  console.log('Port not found in groups, trying other locations...')

  // Проверяем, есть ли порты напрямую в устройстве
  if (device.ports) {
    console.log('Checking device.ports:', device.ports)
    const port = device.ports.find(p => p.code === portCode)
    if (port) {
      console.log('Found port in device.ports:', port)
      return port
    }
  }

  // Проверяем, есть ли порты в других структурах
  if (device.data && device.data.ports) {
    console.log('Checking device.data.ports:', device.data.ports)
    const port = device.data.ports.find(p => p.code === portCode)
    if (port) {
      console.log('Found port in device.data.ports:', port)
      return port
    }
  }

  // Если ничего не нашли, создаем базовый объект порта
  console.log(`Port ${portCode} not found, creating basic port object`)
  return {
    code: portCode,
    name: portCode,
    type: 'unknown',
    group: 'Без группы'
  }
}

// Функция для редактирования параметров порта
function editPortParameters(deviceId, portCode) {
  console.log('Editing port parameters:', deviceId, portCode)

  // Находим порт в структурированных изменениях
  const device = structuredChanges.value.find(d => d.id == deviceId)
  if (!device) return

  const port = device.groups
    .flatMap(g => g.ports)
    .find(p => p.code === portCode)

  if (!port) return

  editingPort.value = {deviceId, portCode}

  // Инициализируем параметры порта
  if (port.port) {
    portParameters.value = {
      entity_id: port.port.entity_id || portCode,
      name: port.port.name || port.name,
      device_class: port.port.device_class || '',
      unit_of_measurement: port.port.unit_of_measurement || port.port.unit || '',
      icon: port.port.icon || '',
      state_class: port.port.state_class || '',
      attributes: port.port.attributes || {}
    }
  } else {
    portParameters.value = {
      entity_id: portCode,
      name: port.name,
      device_class: '',
      unit_of_measurement: '',
      icon: '',
      state_class: '',
      attributes: {}
    }
  }

  showPortEditDialog.value = true
}

// Функция для сохранения параметров порта
function savePortParameters() {
  if (!editingPort.value) return

  console.log('Saving port parameters:', editingPort.value, portParameters.value)

  // Здесь можно добавить логику сохранения параметров в store
  // Пока просто закрываем диалог
  showPortEditDialog.value = false
  editingPort.value = null
}

// Функция для отмены редактирования
function cancelPortEdit() {
  showPortEditDialog.value = false
  editingPort.value = null
}

// Функции для управления разворачиванием портов
function togglePortExpansion(deviceId, portCode) {
  const key = `${deviceId}-${portCode}`
  if (expandedPorts.value.has(key)) {
    expandedPorts.value.delete(key)
  } else {
    expandedPorts.value.add(key)
    // Инициализируем параметры порта при первом разворачивании
    initializePortParameters(deviceId, portCode)
  }
}

function isPortExpanded(deviceId, portCode) {
  return expandedPorts.value.has(`${deviceId}-${portCode}`)
}

// Функция для инициализации параметров порта
// Функция для определения дефолтных параметров на основе типа порта
function getDefaultPortParameters(portType, portName, portUnit = '') {
  const type = (portType || '').toLowerCase()
  const name = portName || ''
  const unit = (portUnit || '').toLowerCase()
  
  console.log('Getting default parameters for:', { portType, portName, portUnit, type })
  
  const defaults = {
    entity_id: '',
    name: name,
    device_class: '',
    unit_of_measurement: unit,
    icon: '',
    state_class: 'measurement',
    entity_category: '',
    enabled_by_default: 'true',
    force_update: 'false',
    suggested_display_precision: '',
    attributes: {}
  }
  
  // Определяем device_class на основе типа порта
  if (type.includes('out.didgi') || type === 'out.didgi') {
    // Выходной цифровой порт - это switch
    defaults.device_class = 'switch'
    defaults.icon = 'mdi:toggle-switch'
    defaults.state_class = ''
    defaults.entity_category = ''
  } else if (type.includes('in.didgi') || type === 'in.didgi') {
    // Входной цифровой порт - это binary_sensor
    defaults.device_class = 'motion'
    defaults.icon = 'mdi:circle-outline'
    defaults.state_class = ''
    defaults.entity_category = ''
  } else if (type.includes('temp')) {
    defaults.device_class = 'temperature'
    defaults.unit_of_measurement = defaults.unit_of_measurement || '°C'
    defaults.icon = 'mdi:thermometer'
  } else if (type.includes('humidity')) {
    defaults.device_class = 'humidity'
    defaults.unit_of_measurement = defaults.unit_of_measurement || '%'
    defaults.icon = 'mdi:water-percent'
  } else if (type.includes('pressure')) {
    defaults.device_class = 'pressure'
    defaults.unit_of_measurement = defaults.unit_of_measurement || 'hPa'
    defaults.icon = 'mdi:gauge'
  } else if (type.includes('voltage')) {
    defaults.device_class = 'voltage'
    defaults.unit_of_measurement = defaults.unit_of_measurement || 'V'
    defaults.icon = 'mdi:lightning-bolt'
  } else if (type.includes('current')) {
    defaults.device_class = 'current'
    defaults.unit_of_measurement = defaults.unit_of_measurement || 'A'
    defaults.icon = 'mdi:flash'
  } else if (type.includes('power') && !type.includes('energy')) {
    defaults.device_class = 'power'
    defaults.unit_of_measurement = defaults.unit_of_measurement || 'W'
    defaults.icon = 'mdi:power'
  } else if (type.includes('energy')) {
    defaults.device_class = 'energy'
    defaults.unit_of_measurement = defaults.unit_of_measurement || 'kWh'
    defaults.icon = 'mdi:battery'
  } else if (type.includes('switch')) {
    defaults.device_class = 'switch'
    defaults.icon = 'mdi:toggle-switch'
    defaults.state_class = ''
  } else if (type.includes('button')) {
    defaults.device_class = 'button'
    defaults.icon = 'mdi:button-cursor'
  } else if (type.includes('sensor') || type.includes('motion')) {
    defaults.device_class = 'motion'
    defaults.icon = 'mdi:motion-sensor'
    defaults.state_class = ''
  }
  
  return defaults
}

// Функция для генерации дефолтного entity_id
function generateDefaultEntityId(deviceId, portCode) {
  // Формат: myhome{deviceId}_{portCode}
  // Заменяем точки и специальные символы на подчеркивания
  const cleanPortCode = portCode.replace(/[^a-zA-Z0-9]/g, '_')
  return `myhome${deviceId}_${cleanPortCode}`
}

function initializePortParameters(deviceId, portCode) {
  const key = `${deviceId}-${portCode}`

  // Находим порт в структурированных изменениях
  const device = structuredChanges.value.find(d => d.id == deviceId)
  if (!device) return

  const port = device.groups
    .flatMap(g => g.ports)
    .find(p => p.code === portCode)

  if (!port) return

  // Инициализируем параметры, если их еще нет
  if (!portParametersData.value[key]) {
    // Используем port напрямую, а не port.port
    const actualPort = port.port || port
    
    console.log(`Initializing parameters for port ${portCode}:`, { 
      port, 
      actualPort,
      hasType: !!actualPort.type,
      type: actualPort.type 
    })
    
    // Получаем дефолтные параметры на основе типа порта
    const defaultParams = getDefaultPortParameters(
      actualPort.type || '', 
      actualPort.name || port.name, 
      actualPort.unit || actualPort.unit_of_measurement
    )
    
    // Генерируем дефолтный entity_id если он не установлен
    const defaultEntityId = actualPort.entity_id || generateDefaultEntityId(deviceId, portCode)
    
    // Объединяем дефолтные параметры с параметрами из порта
    portParametersData.value[key] = {
      entity_id: defaultEntityId,
      name: actualPort.name || port.name || defaultParams.name,
      friendly_name: actualPort.friendly_name || port.name || actualPort.name || defaultParams.name,
      device_class: actualPort.device_class || defaultParams.device_class,
      unit_of_measurement: actualPort.unit_of_measurement || actualPort.unit || defaultParams.unit_of_measurement,
      icon: actualPort.icon || defaultParams.icon,
      state_class: actualPort.state_class || defaultParams.state_class,
      entity_category: actualPort.entity_category || '',
      enabled_by_default: actualPort.enabled_by_default || 'true',
      force_update: actualPort.force_update || 'false',
      suggested_display_precision: actualPort.suggested_display_precision || '',
      attributes: actualPort.attributes || {}
    }
    
    console.log(`Initialized parameters for ${portCode}:`, portParametersData.value[key])
  }
}

// Функция для получения параметров порта
function getPortParameters(deviceId, portCode) {
  const key = `${deviceId}-${portCode}`

  // Автоматически инициализируем параметры, если их еще нет
  if (!portParametersData.value[key]) {
    initializePortParameters(deviceId, portCode)
  }

  return portParametersData.value[key] || {}
}

// Функция для получения отформатированных параметров порта для предварительного просмотра
function getFormattedPortParameters(deviceId, portCode) {
  const params = getPortParameters(deviceId, portCode)
  const formatted = {...params}

  // Если атрибуты являются строкой, парсим их в объект
  if (typeof formatted.attributes === 'string') {
    try {
      formatted.attributes = JSON.parse(formatted.attributes)
    } catch (e) {
      // Если не удалось распарсить, оставляем как есть
      console.warn('Failed to parse attributes JSON:', e)
    }
  }

  return formatted
}

// Функции для группового выбора портов
function isAllGroupPortsSelected(deviceId, group) {
  const groupPortKeys = group.ports.map(port => `${deviceId}-${port.code}`)
  return groupPortKeys.every(key => selectedPorts.value.includes(key))
}

function isSomeGroupPortsSelected(deviceId, group) {
  const groupPortKeys = group.ports.map(port => `${deviceId}-${port.code}`)
  const selectedCount = groupPortKeys.filter(key => selectedPorts.value.includes(key)).length
  return selectedCount > 0 && selectedCount < groupPortKeys.length
}

function toggleAllGroupPorts(deviceId, group) {
  const groupPortKeys = group.ports.map(port => `${deviceId}-${port.code}`)
  const isAllSelected = isAllGroupPortsSelected(deviceId, group)

  if (isAllSelected) {
    // Снимаем выбор со всех портов группы
    selectedPorts.value = selectedPorts.value.filter(key => !groupPortKeys.includes(key))
  } else {
    // Выбираем все порты группы
    groupPortKeys.forEach(key => {
      if (!selectedPorts.value.includes(key)) {
        selectedPorts.value.push(key)
      }
    })
  }
}

function isAllDevicePortsSelected(deviceId) {
  const device = structuredChanges.value.find(d => d.id == deviceId)
  if (!device) return false

  const allDevicePortKeys = device.groups
    .flatMap(group => group.ports)
    .map(port => `${deviceId}-${port.code}`)

  return allDevicePortKeys.every(key => selectedPorts.value.includes(key))
}

function isSomeDevicePortsSelected(deviceId) {
  const device = structuredChanges.value.find(d => d.id == deviceId)
  if (!device) return false

  const allDevicePortKeys = device.groups
    .flatMap(group => group.ports)
    .map(port => `${deviceId}-${port.code}`)

  const selectedCount = allDevicePortKeys.filter(key => selectedPorts.value.includes(key)).length
  return selectedCount > 0 && selectedCount < allDevicePortKeys.length
}

function toggleAllDevicePorts(deviceId) {
  const device = structuredChanges.value.find(d => d.id == deviceId)
  if (!device) return

  const allDevicePortKeys = device.groups
    .flatMap(group => group.ports)
    .map(port => `${deviceId}-${port.code}`)

  const isAllSelected = isAllDevicePortsSelected(deviceId)

  if (isAllSelected) {
    // Снимаем выбор со всех портов устройства
    selectedPorts.value = selectedPorts.value.filter(key => !allDevicePortKeys.includes(key))
  } else {
    // Выбираем все порты устройства
    allDevicePortKeys.forEach(key => {
      if (!selectedPorts.value.includes(key)) {
        selectedPorts.value.push(key)
      }
    })
  }
}

// Функция для определения названия группы на основе порта
function getGroupTitleForPort(device, port) {
  console.log('Getting group title for port:', port)

  // Если у порта есть поле group, используем его
  if (port.group && port.group !== 'Без группы') {
    console.log('Port has group field:', port.group)
    return port.group
  }

  // Ищем группу, в которой находится порт
  if (device.groups) {
    for (const group of device.groups) {
      if (group.items && group.items.includes(port)) {
        console.log('Found group for port:', group.title)
        return group.title || 'Без названия'
      }
    }
  }

  // Если не нашли группу, используем тип порта или общее название
  if (port.type && port.type !== 'unknown') {
    console.log('Using port type as group:', port.type)
    return port.type
  }

  // Группируем по типу порта на основе кода
  const portCode = port.code
  if (portCode.includes('gpio')) {
    return 'GPIO порты'
  } else if (portCode.includes('analog')) {
    return 'Аналоговые порты'
  } else if (portCode.includes('digital')) {
    return 'Цифровые порты'
  } else if (portCode.includes('servo')) {
    return 'Сервоприводы'
  } else if (portCode.includes('rewriter')) {
    return 'Переписчики'
  } else if (portCode.includes('wifi') || portCode.includes('ip') || portCode.includes('rssi')) {
    return 'Сетевые параметры'
  } else if (portCode.includes('millis')) {
    return 'Системные параметры'
  }

  console.log('Using default group name')
  return 'Другие порты'
}

function showState(action) {
  const value = liveState?.[action.key]
  return action.show_if_empty || (value !== null && value !== undefined && value !== '')
}

// Функция для проверки наличия ранее добавленных портов в HA
function hasExistingHAPorts() {
  // Проверяем все устройства на наличие портов с меткой HA
  for (const device of props.devices) {
    // Проверяем данные из API (если загружены)
    const deviceWithPorts = devicesWithPorts.value[device.id]
    if (deviceWithPorts?.apiData) {
      if (hasHAPortsInData(deviceWithPorts.apiData)) {
        return true
      }
    }
    
    // Проверяем локальные данные устройства
    if (device.ports) {
      for (const port of device.ports) {
        // Проверяем, есть ли у порта метка HA
        if (port.ha?.ha_published) {
          return true
        }
      }
    }
  }
  return false
}

// Вспомогательная функция для проверки HA портов в данных API
function hasHAPortsInData(data) {
  if (Array.isArray(data)) {
    return data.some(item => hasHAPortsInData(item))
  } else if (data && typeof data === 'object') {
    // Проверяем, есть ли у элемента метка HA
    if (data.ha?.ha_published) {
      return true
    }
    // Рекурсивно проверяем вложенные данные
    if (data.data && Array.isArray(data.data)) {
      return data.data.some(item => hasHAPortsInData(item))
    }
  }
  return false
}

// Функция для поиска портов, которые уже есть в HA
function findExistingHAPorts(device) {
  const haPorts = []
  
  // Рекурсивная функция поиска HA портов
  const findHAPortsRecursive = (data) => {
    if (!data) return
    
    // Если это массив, проверяем каждый элемент
    if (Array.isArray(data)) {
      data.forEach(item => findHAPortsRecursive(item))
    } 
    // Если это объект
    else if (typeof data === 'object') {
      // Проверяем, является ли это портом с меткой HA
      if (data.code && data.ha?.ha_published) {
        haPorts.push(data)
      }
      
      // Рекурсивно проверяем вложенные данные
      if (data.data && Array.isArray(data.data)) {
        data.data.forEach(item => findHAPortsRecursive(item))
      }
    }
  }
  
  // Ищем в данных из API
  if (device.apiData) {
    findHAPortsRecursive(device.apiData)
  }
  
  // Ищем в локальных данных устройства
  if (device.ports) {
    device.ports.forEach(port => {
      if (port.ha?.ha_published) {
        haPorts.push(port)
      }
    })
  }
  
  return haPorts
}

// Функции для отображения действий
function getActionIcon(action) {
  const icons = {
    'add': 'mdi-plus-circle',
    'remove': 'mdi-minus-circle',
    'update': 'mdi-pencil-circle'
  }
  return icons[action] || 'mdi-help-circle'
}

function getActionColor(action) {
  const colors = {
    'add': 'success',
    'remove': 'error',
    'update': 'info'
  }
  return colors[action] || 'grey'
}

// Автоматический выбор порта при изменении параметров
function ensurePortSelected(deviceId, portCode) {
  const key = `${deviceId}-${portCode}`
  if (!selectedPorts.value.includes(key)) {
    selectedPorts.value.push(key)
  }
}

function onParamChange(deviceId, portCode) {
  ensurePortSelected(deviceId, portCode)
}

// Функции для управления фильтрами по типам
function selectAllTypes() {
  modalFilters.value.showAdd = true
  modalFilters.value.showRemove = true
  modalFilters.value.showUpdate = true
}

function deselectAllTypes() {
  modalFilters.value.showAdd = false
  modalFilters.value.showRemove = false
  modalFilters.value.showUpdate = false
}


async function handleAction(action) {
  activeAction.value = action
  console.log('Handle action', action)
  // Специальная обработка для настройки HA
  if (action.id === 'ha-config') {
    // Кастомная логика для кнопки НАСТРОЙКА HA
    if (props.haConfigMode) {
      // Если режим редактирования включен - проверяем нужно ли показать модалку
      const hasChanges = props.hasHAChanges
      
      // Загружаем данные всех устройств для проверки наличия HA портов
      await Promise.all(props.devices.map(device => loadDevicePorts(device.id)))
      
      const hasExistingPorts = hasExistingHAPorts()
      
      if (hasChanges || hasExistingPorts) {
        // Если есть изменения или ранее добавленные порты - открыть модалку
        haChangesModal.value = true
      } else {
        // Если нет изменений и нет ранее добавленных портов - просто отключаем режим редактирования
        emit('toggle-ha-config')
      }
    } else {
      // Если режим редактирования выключен - включаем его
      emit('toggle-ha-config')
    }
    return
  }

  if (action.type === 'json_form') return (jsonFormDialog.value = true)
  if (action.type === 'table_modal') return (tableModalDialog.value = true)

  if (action.input) {
    inputValues.value = Object.fromEntries(Object.entries(action.input).map(([k, v]) => [k, v?.default ?? null]))
    inputDialog.value = true
    return
  }

  if (action.confirm) {
    confirmDialog.value = true
    deferredSubmit = () => executeAction(action)
    return
  }

  executeAction(action)
}

function submitAction() {
  const action = activeAction.value
  // test required
  for (const [key, config] of Object.entries(action.input)) {
    if (config.required && !inputValues.value[key]) {
      messageStore.addMessage({type: 'error', text: `Поле «${config.label || key}» обязательно для заполнения.`})
      return
    }
  }
  if (action.confirm) {
    confirmDialog.value = true
    deferredSubmit = () => executeAction(action, inputValues.value)
    return
  }
  executeAction(action, inputValues.value)
}

function confirmAndExecute() {
  if (deferredSubmit) {
    deferredSubmit()
    deferredSubmit = null
  }
}


async function executeAction(action, body = {}) {
  loadingAction.value = action.name
  let success = false
  try {
    // add parameters to body from props.params[key]
    body = {...body, ...props.params}
    const endpoint = action.endpoint.replace(/\{(\w+?)\}/g, (_, key) => body[key] ?? '')
    const method = (action.method || 'POST').toUpperCase()
    await secureFetch(endpoint, {
      method,
      headers: {'Content-Type': 'application/json'},
      body: ['POST', 'PUT', 'PATCH'].includes(method) ? JSON.stringify(body) : undefined
    })
    inputDialog.value = false
    confirmDialog.value = false
    messageStore.addMessage({type: 'info', text: `Действие «${action.name}» успешно выполнено.`})
    emit('executed', {action})
    if (action?.update_after) {
      for (let do_after of action.update_after.split('|')) {
        if (do_after === 'reload') {
          loadData()
          continue
        }
        if (do_after === 'close') {
          visible.value = false
          continue
        }
        if (do_after.startsWith('table.')) {
          const tableName = do_after.split('.').slice(1).join('.')
          tableStore.reloadTableData(tableName)
        }
      }
    }
    success = true
  } catch (e) {
    console.warn('Action failed', e)
  } finally {
    if (success) confirmDialog.value = false
    loadingAction.value = null
  }
}

// Функции для работы с изменениями HA
function discardChanges() {
  haChangesModal.value = false
  haChangesStore.clearAllChanges() // Очищаем все изменения
  emit('toggle-ha-config') // Отключаем режим редактирования
  messageStore.addMessage({type: 'info', text: 'Изменения Home Assistant отменены.'})
}

function saveChanges() {
  haChangesModal.value = false
  emit('toggle-ha-config') // Отключаем режим редактирования
  // Здесь можно добавить логику для сохранения изменений на сервер
  // emit('save-ha-changes')
  messageStore.addMessage({type: 'info', text: 'Изменения Home Assistant сохранены.'})
}

async function saveSelectedChanges() {
  if (selectedPorts.value.length === 0) {
    messageStore.addMessage({type: 'warning', text: 'Выберите порты для сохранения'})
    return
  }

  savingChanges.value = true

  try {
    // Подготавливаем данные для отправки
    const changesToSave = prepareChangesForSave()

    if (changesToSave.length === 0) {
      messageStore.addMessage({type: 'warning', text: 'Нет изменений для сохранения'})
      return
    }

    console.log('Saving changes:', changesToSave)

    // Отправляем данные на сервер
    const response = await secureFetch('/api/ha/save-changes', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        changes: changesToSave,
        selectedPorts: selectedPorts.value
      })
    })

    if (response.ok) {
      const result = await response.json()
      console.log('Save result:', result)
      
      messageStore.addMessage({type: 'success', text: `Сохранено ${result.savedCount || changesToSave.length} изменений`})

      // Очищаем store от сохраненных изменений
      haChangesStore.clearAllChanges()

      // Закрываем модальное окно
      haChangesModal.value = false
      selectedPorts.value = []

      // Переключаем режим редактирования
      emit('update:haConfigMode', false)
    } else {
      const error = await response.json().catch(() => ({ message: 'Неизвестная ошибка сервера' }))
      console.error('Save error:', error)
      messageStore.addMessage({type: 'error', text: `Ошибка сохранения: ${error.message}`})
    }
  } catch (error) {
    console.error('Error saving changes:', error)
    messageStore.addMessage({type: 'error', text: 'Ошибка при сохранении изменений'})
  } finally {
    savingChanges.value = false
  }
}

// Функция для подготовки данных к сохранению
function prepareChangesForSave() {
  const changes = haChangesStore.getAllChanges()
  const result = []

  Object.keys(changes).forEach(deviceId => {
    const deviceChanges = changes[deviceId]
    const device = props.devices.find(d => d.id == deviceId)
    if (!device) return

    Object.keys(deviceChanges).forEach(portCode => {
      const action = deviceChanges[portCode]
      const portKey = `${deviceId}-${portCode}`

      // Проверяем, выбран ли этот порт для сохранения
      if (selectedPorts.value.includes(portKey)) {
        const portParams = getFormattedPortParameters(deviceId, portCode)

        result.push({
          deviceId: parseInt(deviceId),
          portCode: portCode,
          action: action,
          parameters: portParams
        })
      }
    })
  })

  return result
}

// Функция для сброса параметров порта в дефолтные значения
function resetPortParameters(deviceId, portCode, actionType = 'add') {
  const key = `${deviceId}-${portCode}`
  
  // Находим порт в структурированных изменениях
  const device = structuredChanges.value.find(d => d.id == deviceId)
  if (!device) return
  
  const port = device.groups
    .flatMap(g => g.ports)
    .find(p => p.code === portCode)
  
  if (!port) return
  
  if (actionType === 'update') {
    // Для обновляемых портов сбрасываем к текущей версии из HA
    if (port.port) {
      portParametersData.value[key] = {
        entity_id: port.port.entity_id || portCode,
        name: port.port.name || port.name,
        friendly_name: port.port.friendly_name || port.port.name || port.name,
        device_class: port.port.device_class || '',
        unit_of_measurement: port.port.unit_of_measurement || port.port.unit || '',
        icon: port.port.icon || '',
        state_class: port.port.state_class || '',
        entity_category: port.port.entity_category || '',
        enabled_by_default: port.port.enabled_by_default || 'true',
        force_update: port.port.force_update || 'false',
        suggested_display_precision: port.port.suggested_display_precision || '',
        attributes: port.port.attributes || {}
      }
      
      // Убираем порт из выбранных (снимаем чекбокс)
      const selectedIndex = selectedPorts.value.indexOf(key)
      if (selectedIndex > -1) {
        selectedPorts.value.splice(selectedIndex, 1)
      }
      
      console.log('Reset parameters to current HA version:', portParametersData.value[key])
    }
  } else {
    // Для новых портов сбрасываем к дефолтным значениям
    const actualPort = port.port || port
    
    // Получаем дефолтные параметры
    const defaultParams = getDefaultPortParameters(
      actualPort.type || '',
      actualPort.name || port.name,
      actualPort.unit || actualPort.unit_of_measurement
    )
    
    // Генерируем дефолтный entity_id для сброса
    const defaultEntityId = generateDefaultEntityId(deviceId, portCode)
    
    // Сбрасываем параметры в дефолтные значения
    portParametersData.value[key] = {
      entity_id: defaultEntityId,
      name: actualPort.name || port.name || defaultParams.name,
      friendly_name: actualPort.name || port.name || defaultParams.name,
      device_class: defaultParams.device_class,
      unit_of_measurement: defaultParams.unit_of_measurement,
      icon: defaultParams.icon,
      state_class: defaultParams.state_class,
      entity_category: defaultParams.entity_category,
      enabled_by_default: defaultParams.enabled_by_default,
      force_update: defaultParams.force_update,
      suggested_display_precision: defaultParams.suggested_display_precision,
      attributes: defaultParams.attributes
    }
    
    console.log(`Reset parameters for ${portCode} to defaults:`, portParametersData.value[key])
  }
}
</script>

<style scoped>
/* Стили для кнопки HA в режиме редактирования */
.ha-config-active {
  animation: ha-pulse 2s infinite;
  box-shadow: 0 0 8px rgba(255, 152, 0, 0.5);
}

@keyframes ha-pulse {
  0% {
    box-shadow: 0 0 8px rgba(255, 152, 0, 0.5);
  }
  50% {
    box-shadow: 0 0 16px rgba(255, 152, 0, 0.8);
  }
  100% {
    box-shadow: 0 0 8px rgba(255, 152, 0, 0.5);
  }
}

.ha-config-badge {
  position: absolute;
  top: 6px;
  right: 0px;
}

/* Цветовое выделение строк таблицы */
.success-row {
  background-color: rgba(76, 175, 80, 0.1) !important;
  border-left: 4px solid #4caf50;
}

.error-row {
  background-color: rgba(244, 67, 54, 0.1) !important;
  border-left: 4px solid #f44336;
}

.info-row {
  background-color: rgba(33, 150, 243, 0.1) !important;
  border-left: 4px solid #2196f3;
}

.port-parameters-row {
  background-color: rgba(33, 150, 243, 0.05) !important;
}

.port-parameters-row td {
  padding: 0 !important;
}

/* Стили для полей параметров в таблице */
.port-parameter-field {
  min-width: 120px;
  max-width: 200px;
}

.port-parameter-field .v-field {
  font-size: 0.75rem;
}

.port-parameter-field .v-field__input {
  padding: 4px 8px;
}

/* Уменьшение отступов между столбцами */
.v-table th,
.v-table td {
  padding: 8px 4px !important;
}

.v-table th:first-child,
.v-table td:first-child {
  padding-left: 8px !important;
}

.v-table th:last-child,
.v-table td:last-child {
  padding-right: 8px !important;
}

/* Стили для JSON-редактора */
.json-editor {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  min-height: 200px;
}

.json-editor .jsoneditor {
  border: none !important;
}

.json-editor .jsoneditor-menu {
  display: none !important;
}
</style>
