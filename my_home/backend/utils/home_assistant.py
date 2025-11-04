"""
Home Assistant WebSocket клиент с максимальным функционалом
"""
import asyncio
import json
import logging
import os
import socket
import yaml
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, Callable, Set, List
import websockets
import aiohttp
from websockets.exceptions import ConnectionClosed, WebSocketException
from utils.configs import config
from utils.logger import ws_logger as logger


# Настройка логирования
# logger = logging.getLogger(__name__)  # Заменен на глобальный логгер


class ControlType(Enum):
  """Типы управления портом"""
  AUTO = "auto"  # Автоматический выбор метода (по умолчанию)
  UI = "ui"  # Только изменение в UI (states API)
  HARD = "hard"  # Управление физическим устройством (services API)


class PortType(Enum):
  """Типы портов для максимального покрытия"""
  # Сенсоры
  TEMPERATURE = "temperature"
  HUMIDITY = "humidity"
  PRESSURE = "pressure"
  LIGHT = "light"
  MOTION = "motion"
  DOOR = "door"
  WINDOW = "window"
  SMOKE = "smoke"
  GAS = "gas"
  WATER = "water"
  POWER = "power"
  ENERGY = "energy"
  VOLTAGE = "voltage"
  CURRENT = "current"
  FREQUENCY = "frequency"
  SIGNAL_STRENGTH = "signal_strength"
  BATTERY = "battery"
  TIMESTAMP = "timestamp"
  DATE = "date"
  DURATION = "duration"
  DISTANCE = "distance"
  SPEED = "speed"
  WEIGHT = "weight"
  VOLUME = "volume"
  AREA = "area"
  LENGTH = "length"
  MASS = "mass"
  TEMPERATURE_DIFFERENTIAL = "temperature_differential"
  ENUM = "enum"
  COUNT = "count"
  MONEY = "money"
  DATA_SIZE = "data_size"
  DATA_RATE = "data_rate"
  IRRADIANCE = "irradiance"
  PRECIPITATION = "precipitation"
  PRECIPITATION_INTENSITY = "precipitation_intensity"
  CONCENTRATION = "concentration"
  CONDUCTIVITY = "conductivity"
  PH = "ph"
  OXIDIZING = "oxidizing"
  REDUCING = "reducing"
  NITROGEN_MONOXIDE = "nitrogen_monoxide"
  NITROGEN_DIOXIDE = "nitrogen_dioxide"
  SULPHUR_DIOXIDE = "sulphur_dioxide"
  PM_1 = "pm1"
  PM_2_5 = "pm25"
  PM_10 = "pm10"
  VOLATILE_ORGANIC_COMPOUNDS = "volatile_organic_compounds"
  VOLATILE_ORGANIC_COMPOUNDS_PARTS = "volatile_organic_compounds_parts"
  CARBON_MONOXIDE = "carbon_monoxide"
  CARBON_DIOXIDE = "carbon_dioxide"
  NITROGEN = "nitrogen"
  OZONE = "ozone"
  AMMONIA = "ammonia"
  SULPHIDE = "sulphide"
  NITROGEN_OXIDE = "nitrogen_oxide"
  NON_METHANE_HYDROCARBONS = "non_methane_hydrocarbons"
  NON_METHANE_HYDROCARBONS_PPBE = "non_methane_hydrocarbons_ppbe"
  HYDROGEN_SULPHIDE = "hydrogen_sulphide"
  TOTAL_VOLATILE_ORGANIC_COMPOUNDS = "total_volatile_organic_compounds"
  TOTAL_VOLATILE_ORGANIC_COMPOUNDS_PPBE = "total_volatile_organic_compounds_ppbe"
  OXYGEN = "oxygen"
  REACTIVE_POWER = "reactive_power"
  APPARENT_POWER = "apparent_power"
  COST = "cost"
  GAS_CONSUMPTION = "gas_consumption"
  WATER_CONSUMPTION = "water_consumption"
  NITROGEN_DIOXIDE_NO2 = "nitrogen_dioxide_no2"
  NITROGEN_MONOXIDE_NO = "nitrogen_monoxide_no"
  NITROGEN_OXIDES_NOX = "nitrogen_oxides_nox"
  NITROUS_OXIDE = "nitrous_oxide"
  OZONE_O3 = "ozone_o3"
  PARTICULATE_MATTER_1 = "particulate_matter_1"
  PARTICULATE_MATTER_2_5 = "particulate_matter_2_5"
  PARTICULATE_MATTER_10 = "particulate_matter_10"
  SULFUR_DIOXIDE = "sulfur_dioxide"
  AMMONIA_NH3 = "ammonia_nh3"
  BUTANE = "butane"
  CARBON_DIOXIDE_CO2 = "carbon_dioxide_co2"
  CARBON_MONOXIDE_CO = "carbon_monoxide_co"
  ETHANE = "ethane"
  ETHANOL = "ethanol"
  ETHYLENE = "ethylene"
  HYDROGEN = "hydrogen"
  HYDROGEN_SULFIDE = "hydrogen_sulfide"
  METHANE = "methane"
  METHANOL = "methanol"
  NITROGEN_DIOXIDE_NO2_ALT = "nitrogen_dioxide_no2_alt"
  NITROGEN_MONOXIDE_NO_ALT = "nitrogen_monoxide_no_alt"
  NITROUS_OXIDE_N2O = "nitrous_oxide_n2o"
  OZONE_O3_ALT = "ozone_o3_alt"
  PROPANE = "propane"
  SULFUR_DIOXIDE_SO2 = "sulfur_dioxide_so2"
  TOTAL_NITROGEN_OXIDES = "total_nitrogen_oxides"
  TOTAL_VOLATILE_ORGANIC_COMPOUNDS_TVOC = "total_volatile_organic_compounds_tvoc"
  VOLATILE_ORGANIC_COMPOUNDS_VOC = "volatile_organic_compounds_voc"

  # Переключатели
  SWITCH = "switch"
  LIGHT_SWITCH = "light_switch"
  FAN = "fan"
  HEATER = "heater"
  COOLER = "cooler"
  PUMP = "pump"
  VALVE = "valve"
  LOCK = "lock"
  GARAGE_DOOR = "garage_door"
  RELAY = "relay"
  OUTLET = "outlet"
  SOCKET = "socket"

  # Двоичные сенсоры
  BINARY_SENSOR = "binary_sensor"
  CONNECTIVITY = "connectivity"
  DOOR_WINDOW = "door_window"
  GARAGE_DOOR_SENSOR = "garage_door_sensor"
  GAS_SENSOR = "gas_sensor"
  HEAT_SENSOR = "heat_sensor"
  LIGHT_SENSOR = "light_sensor"
  LOCK_SENSOR = "lock_sensor"
  MOISTURE_SENSOR = "moisture_sensor"
  MOTION_SENSOR = "motion_sensor"
  MOVING_SENSOR = "moving_sensor"
  OCCUPANCY_SENSOR = "occupancy_sensor"
  OPENING_SENSOR = "opening_sensor"
  PLUG_SENSOR = "plug_sensor"
  POWER_SENSOR = "power_sensor"
  PRESENCE_SENSOR = "presence_sensor"
  PROBLEM_SENSOR = "problem_sensor"
  RUNNING_SENSOR = "running_sensor"
  SAFETY_SENSOR = "safety_sensor"
  SMOKE_SENSOR = "smoke_sensor"
  SOUND_SENSOR = "sound_sensor"
  TAMPER_SENSOR = "tamper_sensor"
  UPDATE_SENSOR = "update_sensor"
  VIBRATION_SENSOR = "vibration_sensor"
  WINDOW_SENSOR = "window_sensor"

  # Камеры
  CAMERA = "camera"

  # Климат
  CLIMATE = "climate"

  # Покрытие
  COVER = "cover"

  # Устройства
  DEVICE_TRACKER = "device_tracker"

  # Вентиляторы
  FAN_ENTITY = "fan"

  # Изображения
  IMAGE = "image"

  # Ввод
  INPUT_BOOLEAN = "input_boolean"
  INPUT_BUTTON = "input_button"
  INPUT_DATETIME = "input_datetime"
  INPUT_NUMBER = "input_number"
  INPUT_SELECT = "input_select"
  INPUT_TEXT = "input_text"

  # Свет
  LIGHT_ENTITY = "light"

  # Блокировка
  LOCK_ENTITY = "lock"

  # Медиа-плеер
  MEDIA_PLAYER = "media_player"

  # Уведомления
  NOTIFY = "notify"

  # Числа
  NUMBER = "number"

  # Персоны
  PERSON = "person"

  # Ремонт
  REPAIR = "repair"

  # Сцены
  SCENE = "scene"

  # Скрипты
  SCRIPT = "script"

  # Выбор
  SELECT = "select"

  # Сенсоры
  SENSOR = "sensor"

  # SIREN
  SIREN = "siren"

  # Текстовые поля
  TEXT = "text"

  # Таймеры
  TIMER = "timer"

  # Обновления
  UPDATE = "update"

  # Календари
  CALENDAR = "calendar"

  # Уведомления
  ALARM_CONTROL_PANEL = "alarm_control_panel"

  # Автомобили
  VEHICLE = "vehicle"

  # Погода
  WEATHER = "weather"

  # Зоны
  ZONE = "zone"


@dataclass
class PortConfig:
  """Конфигурация порта"""
  entity_id: str
  name: str
  port_type: PortType
  device_class: Optional[str] = None
  unit_of_measurement: Optional[str] = None
  icon: Optional[str] = None
  state_class: Optional[str] = None
  entity_category: Optional[str] = None
  enabled_by_default: bool = True
  force_update: bool = False
  suggested_display_precision: Optional[int] = None
  attributes: Optional[Dict[str, Any]] = None


class HomeAssistantWebSocket:
  """Home Assistant WebSocket клиент с максимальным функционалом"""

  def __init__(self):
    self.websocket = None
    self.connected = False
    self.authenticated = False
    self.message_id = 0
    self.pending_requests = {}
    self.event_handlers = {}
    self.connection_task = None
    self.port_subscriptions = {}
    self.custom_ports = set()
    self._state_changes_subscribed = False

    # Настройки переподключения
    self.reconnect_interval = 5
    self.max_reconnect_attempts = 10
    self.reconnect_attempts = 0

    # Настройки для интеграции с реальным проектом
    self.test_mode = False  # По умолчанию выключен
    self.log_level = 'INFO'
    self.log_our_ports_only = True  # Логировать только наши порты
    self.device_response_delay = 0.5  # Задержка ответа устройства

    # Колбэки для интеграции
    self.on_port_state_changed: Optional[Callable] = None
    self.on_port_created: Optional[Callable] = None
    self.on_port_deleted: Optional[Callable] = None
    self.on_service_called: Optional[Callable] = None
    self.on_connection_status_changed: Optional[Callable] = None

  def is_custom_port(self, entity_id: str) -> bool:
    """Проверка, является ли порт кастомным (созданным нами)"""
    # Проверяем по префиксу
    if entity_id.startswith('sensor.myhome') or entity_id.startswith('switch.myhome'):
      return True

    # Проверяем по списку кастомных портов
    if entity_id in self.custom_ports:
      return True

    return False

  def is_existing_device(self, entity_id: str) -> bool:
    """Проверка, является ли порт существующим устройством"""
    # Проверяем по паттернам существующих устройств
    if entity_id.startswith('switch.0x') or entity_id.startswith('sensor.0x'):
      return True

    # Проверяем по ключевым словам в имени
    if 'tuya' in entity_id.lower() or 'zigbee' in entity_id.lower():
      return True

    return False

  def _check_host_availability(self, host: str, port: int, timeout: int = 5) -> bool:
    """Проверка доступности хоста и порта"""
    try:
      logger.info(f"[HA-WebSocket] Checking host availability: {host}:{port}")
      
      # Создаем сокет
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      sock.settimeout(timeout)
      
      # Пытаемся подключиться
      result = sock.connect_ex((host, port))
      sock.close()
      
      if result == 0:
        logger.success(f"[HA-WebSocket] Host {host}:{port} is reachable")
        return True
      else:
        logger.error(f"[HA-WebSocket] Host {host}:{port} is not reachable (error code: {result})")
        return False
        
    except socket.gaierror as e:
      logger.error(f"[HA-WebSocket] DNS resolution failed for {host}: {e}")
      return False
    except Exception as e:
      logger.error(f"[HA-WebSocket] Host availability check failed: {e}")
      return False

  def _parse_url(self, url: str) -> tuple:
    """Парсинг URL для извлечения хоста и порта"""
    try:
      # Убираем протокол
      if url.startswith('http://'):
        url = url[7:]
      elif url.startswith('https://'):
        url = url[7:]
      
      # Разделяем на хост и порт
      if ':' in url:
        host, port_str = url.split(':', 1)
        port = int(port_str)
      else:
        host = url
        port = 8123  # Стандартный порт HA
      
      return host, port
    except Exception as e:
      logger.error(f"[HA-WebSocket] URL parsing failed for {url}: {e}")
      return None, None

  async def connect(self) -> bool:
    """Подключение к Home Assistant WebSocket"""
    try:
      if not config.is_ha_configured():
        logger.error("[HA-WebSocket] Home Assistant not configured")
        return False

      # Получаем URL и проверяем доступность хоста
      ha_url = config.get_ha_url()
      logger.info(f"[HA-WebSocket] HA URL: {ha_url}")
      
      # Парсим URL для получения хоста и порта
      host, port = self._parse_url(ha_url)
      if not host or not port:
        logger.error(f"[HA-WebSocket] Failed to parse HA URL: {ha_url}")
        return False
      
      # Проверяем доступность хоста
      if not self._check_host_availability(host, port):
        logger.error(f"[HA-WebSocket] Cannot connect to Home Assistant at {host}:{port}")
        return False

      # Формируем WebSocket URL
      ws_url = ha_url.replace('http://', 'ws://').replace('https://', 'wss://')
      ws_url = f"{ws_url}/api/websocket"

      logger.info(f"[HA-WebSocket] Connecting to {ws_url}")

      # Подключаемся к WebSocket
      self.websocket = await websockets.connect(
        ws_url,
        ping_interval=20,
        ping_timeout=10,
        close_timeout=10
      )
      self.connected = True

      # Аутентификация
      try:
        await self._authenticate()
        logger.success("[HA-WebSocket] Authentication successful")
      except Exception as auth_error:
        logger.warning(f"[HA-WebSocket] Authentication failed: {auth_error}")
        logger.info("[HA-WebSocket] Continuing with limited functionality")
        self.authenticated = False

      # Запускаем обработчик сообщений
      logger.info("[HA-WebSocket] Starting message handler...")
      self.connection_task = asyncio.create_task(self._message_handler())

      # Подписываемся на события только если аутентифицированы
      if self.authenticated:
        logger.info("[HA-WebSocket] Subscribing to events...")
        await self.subscribe_events('*')
        logger.success("[HA-WebSocket] Connected and authenticated to Home Assistant")
      else:
        logger.warning("[HA-WebSocket] Connected to Home Assistant without authentication (limited functionality)")

      logger.info(f"[HA-WebSocket] Final connection status: connected={self.connected}, authenticated={self.authenticated}")
      
      # Проверяем статус после всех операций
      if not self.connected:
        logger.error("[HA-WebSocket] Connection lost during setup")
        return False
      
      return True

    except Exception as e:
      logger.error(f"[HA-WebSocket] Connection failed: {e}")
      return False

  async def disconnect(self):
    """Отключение от Home Assistant WebSocket"""
    try:
      self.connected = False
      self.authenticated = False

      if self.connection_task:
        self.connection_task.cancel()
        try:
          await self.connection_task
        except asyncio.CancelledError:
          pass

      if self.websocket:
        await self.websocket.close()

      logger.info("[HA-WebSocket] Disconnected from Home Assistant")

    except Exception as e:
      logger.error(f"[HA-WebSocket] Error during disconnect: {e}")

  async def _authenticate(self):
    """Аутентификация в Home Assistant"""
    try:
      # Получаем сообщение auth_required
      message = await self.websocket.recv()
      data = json.loads(message)

      if data.get('type') == 'auth_required':
        # Проверяем наличие токена
        token = config.get_ha_token()
        if not token or token.strip() == "":
          logger.warning("[HA-WebSocket] No token configured or token is empty")
          logger.warning("[HA-WebSocket] To get a Home Assistant token:")
          logger.warning("[HA-WebSocket] 1. Open Home Assistant web interface")
          logger.warning("[HA-WebSocket] 2. Go to Profile (click on your user icon)")
          logger.warning("[HA-WebSocket] 3. Scroll down to 'Long-lived access tokens'")
          logger.warning("[HA-WebSocket] 4. Click 'Create token'")
          logger.warning("[HA-WebSocket] 5. Give it a name (e.g., 'MyHome Integration')")
          logger.warning("[HA-WebSocket] 6. Copy the generated token")
          logger.warning("[HA-WebSocket] 7. Add it to your config.yaml file:")
          logger.warning("[HA-WebSocket]    homeassistant:")
          logger.warning("[HA-WebSocket]      token: 'your_token_here'")
          logger.warning("[HA-WebSocket] Attempting connection without authentication (limited functionality)")
          # Попробуем подключиться без токена (для некоторых версий HA)
          auth_message = {
            'type': 'auth',
            'access_token': ''
          }
        else:
          logger.info("[HA-WebSocket] Token found, sending authentication request")
          # Отправляем токен
          auth_message = {
            'type': 'auth',
            'access_token': token
          }

        await self.websocket.send(json.dumps(auth_message))

        # Получаем ответ
        response = await self.websocket.recv()
        response_data = json.loads(response)

        if response_data.get('type') == 'auth_ok':
          self.authenticated = True
          logger.success("[HA-WebSocket] Authentication successful")
        elif response_data.get('type') == 'auth_invalid':
          logger.warning("[HA-WebSocket] Authentication failed - invalid token or no token configured")
          logger.info("[HA-WebSocket] Please configure Home Assistant token in settings")
          # Не прерываем соединение, продолжаем работу в ограниченном режиме
          self.authenticated = False
        else:
          logger.warning(f"[HA-WebSocket] Authentication failed: {response_data}")
          logger.info("[HA-WebSocket] Continuing with limited functionality")
          self.authenticated = False
      else:
        raise Exception("Expected auth_required message")
        
    except Exception as e:
      logger.warning(f"[HA-WebSocket] Authentication error: {e}")
      logger.info("[HA-WebSocket] Continuing with limited functionality")
      self.authenticated = False

  async def _message_handler(self):
    """Обработчик входящих сообщений"""
    try:
      logger.info("[HA-WebSocket] Message handler started")
      while self.connected:
        try:
          message = await self.websocket.recv()
          data = json.loads(message)
          await self._handle_message(data)
        except websockets.exceptions.ConnectionClosed:
          logger.warning("[HA-WebSocket] WebSocket connection closed by server")
          self.connected = False
          break
        except Exception as e:
          logger.error(f"[HA-WebSocket] Error in message handler: {e}")
          self.connected = False
          break
    except Exception as e:
      logger.error(f"[HA-WebSocket] Message handler failed: {e}")
      self.connected = False
    finally:
      logger.info("[HA-WebSocket] Message handler stopped")
      await self._handle_disconnect()

  async def _handle_message(self, data: dict):
    """Обработка входящего сообщения"""
    try:
      message_type = data.get('type')
      
      if message_type == 'result':
        # Ответ на команду
        message_id = data.get('id')
        logger.debug(f"[HA-WebSocket] Received result for command {message_id}: success={data.get('success')}")
        if message_id in self.pending_requests:
          future = self.pending_requests.pop(message_id)
          future.set_result(data)
        else:
          logger.warning(f"[HA-WebSocket] Received result for unknown command {message_id}")

      elif message_type == 'event':
        # Событие от Home Assistant
        event_data = data.get('event', {})
        event_type = event_data.get('event_type')
        
        # Добавляем отладочную информацию для всех событий
        logger.debug(f"[HA-WebSocket] Received event: {event_type}, data: {event_data}")
        
        # Фильтрация логов по нашим портам
        if self.log_our_ports_only:
          entity_id = event_data.get('entity_id')
          if entity_id and entity_id not in self.custom_ports:
            return  # Пропускаем события не наших портов
        
        if event_type == 'state_changed':
          await self._handle_state_changed(event_data)
        elif event_type == 'call_service':
          await self._handle_call_service(event_data)
        else:
          logger.debug(f"[HA-WebSocket] Unhandled event type: {event_type}")

    except Exception as e:
      logger.error(f"[HA-WebSocket] Error handling message: {e}")

  async def _handle_state_changed(self, event_data: Dict[str, Any]):
    """Обработка события state_changed"""
    try:
      entity_id = event_data.get('entity_id')
      new_state = event_data.get('new_state', {})
      old_state = event_data.get('old_state', {})

      if not entity_id or not new_state:
        return

      # Проверяем, является ли это нашей сущностью (начинается с myhome)
      if not entity_id.startswith('myhome'):
        return

      # Получаем новое состояние
      new_state_value = new_state.get('state')
      old_state_value = old_state.get('state') if old_state else None

      # Логируем изменение
      logger.info(f"[HA-State-Change] {entity_id}: {old_state_value} -> {new_state_value}")

      # Используем AppConfig для обработки изменения состояния
      await config.handle_ha_state_change(entity_id, new_state_value)

    except Exception as e:
      logger.error(f"[HA-WebSocket] State change handler error: {e}")

  async def _handle_call_service(self, event_data: Dict[str, Any]):
    """Обработка события call_service"""
    try:
      logger.debug(f"[HA-WebSocket] Processing call_service event: {event_data}")
      
      service_data = event_data.get('data', {})
      domain = service_data.get('domain')
      service = service_data.get('service')
      entity_id = service_data.get('service_data', {}).get('entity_id')

      logger.info(f"[HA-WebSocket] Service called: {domain}.{service} for {entity_id}")
      logger.debug(f"[HA-WebSocket] Service data: {service_data}")

      # Вызываем колбэк если установлен
      if self.on_service_called:
        logger.debug(f"[HA-WebSocket] Calling on_service_called callback")
        try:
          await self.on_service_called(entity_id, domain, service, service_data)
          logger.debug(f"[HA-WebSocket] on_service_called callback completed")
        except Exception as e:
          logger.error(f"[HA-WebSocket] Error in on_service_called callback: {e}")
      else:
        logger.warning(f"[HA-WebSocket] on_service_called callback not set")

      # Определяем новое состояние на основе сервиса
      new_state = 'on' if service in ['turn_on', 'turn_on'] else 'off'

      if self.test_mode:
        # В тестовом режиме отправляем ответную реакцию в UI
        await self._send_ui_response(entity_id, new_state)
      else:
        # В реальном режиме здесь должна быть логика управления физическим устройством
        logger.info(f"[HA-WebSocket] Real device control: {entity_id} -> {new_state}")
        # TODO: Добавить логику управления реальным устройством

      # Проверяем, есть ли подписка на этот порт
      if entity_id in self.port_subscriptions:
        handler = self.port_subscriptions[entity_id]
        if handler:
          try:
            # Создаем фиктивные состояния для обработчика
            fake_new_state = {'state': new_state}
            fake_old_state = {'state': 'off' if new_state == 'on' else 'on'}
            await handler(entity_id, fake_new_state, fake_old_state)
          except Exception as e:
            logger.error(f"[HA-WebSocket] Port handler error for {entity_id}: {e}")
      else:
        logger.debug(f"[HA-WebSocket] Port {entity_id} not in subscriptions, but service called")

    except Exception as e:
      logger.error(f"[HA-WebSocket] Error handling call service: {e}")

  async def _send_ui_response(self, entity_id: str, state: str):
    """Отправка ответной реакции в UI"""
    try:
      # Имитируем задержку работы с реальным устройством
      await asyncio.sleep(self.device_response_delay)

      ha_url = config.get_ha_url()
      token = config.get_ha_token()

      api_url = f"{ha_url}/api/states/{entity_id}"
      headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
      }

      # Получаем текущие атрибуты
      current_state = await self.get_state(entity_id)
      attributes = {}
      if current_state.get('success'):
        attributes = current_state.get('data', {}).get('attributes', {})

      data = {
        "state": state,
        "attributes": attributes
      }

      async with aiohttp.ClientSession() as session:
        async with session.post(api_url, headers=headers, json=data) as response:
          if response.status in [200, 201]:
            logger.info(f"[HA-WebSocket] UI response sent: {entity_id} = {state}")
          else:
            error_text = await response.text()
            logger.error(f"[HA-WebSocket] UI response failed: HTTP {response.status} - {error_text}")

    except Exception as e:
      logger.error(f"[HA-WebSocket] Error sending UI response: {e}")

  async def _handle_disconnect(self):
    """Обработка отключения"""
    logger.warning("[HA-WebSocket] Handling disconnect...")
    self.connected = False
    self.authenticated = False

    # Завершаем все ожидающие запросы
    pending_count = len(self.pending_requests)
    if pending_count > 0:
      logger.warning(f"[HA-WebSocket] Cancelling {pending_count} pending requests")
    for future in self.pending_requests.values():
      if not future.done():
        future.set_exception(ConnectionClosed("Connection lost"))
    self.pending_requests.clear()

    # Попытка переподключения
    if self.reconnect_attempts < self.max_reconnect_attempts:
      self.reconnect_attempts += 1
      logger.info(f"[HA-WebSocket] Attempting to reconnect ({self.reconnect_attempts}/{self.max_reconnect_attempts})")

      await asyncio.sleep(self.reconnect_interval)
      await self.connect()
    else:
      logger.error(f"[HA-WebSocket] Max reconnection attempts reached ({self.max_reconnect_attempts})")

  async def _send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
    """Отправка команды и ожидание ответа"""
    if not self.connected or not self.authenticated:
      if not self.connected:
        logger.error(f"[HA-WebSocket] Cannot send command: WebSocket is not connected")
      elif not self.authenticated:
        logger.error(f"[HA-WebSocket] Cannot send command: Not authenticated")
        logger.warning("[HA-WebSocket] Please configure a valid Home Assistant token")
        logger.warning("[HA-WebSocket] See previous messages for token setup instructions")
      raise Exception("Not connected or not authenticated")

    self.message_id += 1
    command['id'] = self.message_id
    logger.debug(f"[HA-WebSocket] Sending command {self.message_id}: {command.get('type')}")

    # Создаем Future для ожидания ответа
    future = asyncio.Future()
    self.pending_requests[self.message_id] = future

    try:
      # Отправляем команду
      await self.websocket.send(json.dumps(command))
      logger.debug(f"[HA-WebSocket] Command {self.message_id} sent successfully")

      # Ждем ответ с таймаутом
      timeout = config.get_ha_timeout()
      logger.debug(f"[HA-WebSocket] Waiting for response to command {self.message_id} (timeout: {timeout}s)")
      response = await asyncio.wait_for(future, timeout=timeout)
      logger.debug(f"[HA-WebSocket] Received response for command {self.message_id}: success={response.get('success')}")

      return response

    except asyncio.TimeoutError:
      self.pending_requests.pop(self.message_id, None)
      logger.error(f"[HA-WebSocket] Command {self.message_id} timeout after {timeout}s")
      raise Exception("Command timeout")
    except Exception as e:
      self.pending_requests.pop(self.message_id, None)
      logger.error(f"[HA-WebSocket] Command {self.message_id} error: {e}")
      raise e

  # Методы для интеграции с реальным проектом

  def set_callbacks(self,
                    on_port_state_changed: Optional[Callable] = None,
                    on_port_created: Optional[Callable] = None,
                    on_port_deleted: Optional[Callable] = None,
                    on_service_called: Optional[Callable] = None,
                    on_connection_status_changed: Optional[Callable] = None):
    """Установка колбэков для интеграции"""
    if on_port_state_changed:
      self.on_port_state_changed = on_port_state_changed
    if on_port_created:
      self.on_port_created = on_port_created
    if on_port_deleted:
      self.on_port_deleted = on_port_deleted
    if on_service_called:
      self.on_service_called = on_service_called
    if on_connection_status_changed:
      self.on_connection_status_changed = on_connection_status_changed

  def set_test_mode(self, enabled: bool):
    """Включение/выключение тестового режима"""
    self.test_mode = enabled
    logger.info(f"[HA-WebSocket] Test mode: {'enabled' if enabled else 'disabled'}")

  def set_log_level(self, level: str):
    """Установка уровня логирования"""
    self.log_level = level.upper()
    logger.setLevel(getattr(logging, self.log_level, logging.INFO))
    logger.info(f"[HA-WebSocket] Log level set to: {self.log_level}")

  def set_log_our_ports_only(self, enabled: bool):
    """Включение/выключение фильтрации логов по нашим портам"""
    self.log_our_ports_only = enabled
    logger.info(f"[HA-WebSocket] Log our ports only: {'enabled' if enabled else 'disabled'}")

  def set_device_response_delay(self, delay: float):
    """Установка задержки ответа устройства"""
    self.device_response_delay = delay
    logger.info(f"[HA-WebSocket] Device response delay set to: {delay}s")

  def get_connection_status(self) -> Dict[str, Any]:
    """Получение статуса подключения"""
    return {
      'connected': self.connected,
      'authenticated': self.authenticated,
      'test_mode': self.test_mode,
      'custom_ports_count': len(self.custom_ports),
      'subscriptions_count': len(self.port_subscriptions)
    }

  def get_custom_ports(self) -> List[str]:
    """Получение списка наших портов"""
    return list(self.custom_ports)

  # Основные API методы

  async def subscribe_events(self, event_type: str = '*') -> bool:
    """Подписка на события Home Assistant"""
    try:
      command = {
        'type': 'subscribe_events',
        'event_type': event_type
      }
      result = await self._send_command(command)
      return result.get('success', False)
    except Exception as e:
      logger.error(f"[HA-WebSocket] Subscribe events error: {e}")
      return False

  async def get_states(self) -> Dict[str, Any]:
    """Получение всех состояний"""
    try:
      logger.info("[HA-WebSocket] Requesting all states from Home Assistant...")
      command = {
        'type': 'get_states'
      }
      result = await self._send_command(command)
      logger.info(f"[HA-WebSocket] Get states result: success={result.get('success')}, result_count={len(result.get('result', []))}")
      return result
    except Exception as e:
      logger.error(f"[HA-WebSocket] Get states error: {e}")
      return {"success": False, "error": str(e)}

  async def get_state(self, entity_id: str) -> Dict[str, Any]:
    """Получение состояния конкретной сущности"""
    try:
      command = {
        'type': 'get_states'
      }
      result = await self._send_command(command)

      if result.get('success'):
        states = result.get('result', [])
        for state in states:
          if state.get('entity_id') == entity_id:
            return {"success": True, "data": state}
        return {"success": False, "error": "Entity not found"}
      else:
        return result
    except Exception as e:
      logger.error(f"[HA-WebSocket] Get state error: {e}")
      return {"success": False, "error": str(e)}

  async def call_service(self, domain: str, service: str, entity_id: str = None, **kwargs) -> Dict[str, Any]:
    """Вызов сервиса Home Assistant"""
    try:
      command = {
        'type': 'call_service',
        'domain': domain,
        'service': service
      }

      if entity_id:
        command['target'] = {'entity_id': entity_id}

      if kwargs:
        command['service_data'] = kwargs

      result = await self._send_command(command)
      return result
    except Exception as e:
      logger.error(f"[HA-WebSocket] Call service error: {e}")
      return {"success": False, "error": str(e)}

  async def set_state(self, entity_id: str, state: str, control_type: ControlType = ControlType.AUTO,
                      attributes: Dict[str, Any] = None) -> Dict[str, Any]:
    """Установка состояния сущности с умным выбором метода"""
    try:
      ha_url = config.get_ha_url()
      token = config.get_ha_token()

      # Формируем URL и заголовки
      headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
      }

      logger.info(
        f"[HA-WebSocket] Setting state for {entity_id} to {state} (control type: {getattr(control_type, 'value', control_type)})")

      # Определяем метод управления
      if control_type == ControlType.UI:
        # Принудительно используем UI управление
        result = await self._set_state_ui_only(entity_id, state, attributes, ha_url, headers)
      elif control_type == ControlType.HARD:
        # Принудительно используем управление устройством
        result = await self._set_state_device(entity_id, state, attributes, ha_url, headers)
      else:  # ControlType.AUTO
        # Автоматический выбор метода
        if self.is_custom_port(entity_id):
          # Кастомный порт - используем UI управление
          result = await self._set_state_ui_only(entity_id, state, attributes, ha_url, headers)
        elif self.is_existing_device(entity_id):
          # Существующее устройство - используем управление устройством
          result = await self._set_state_device(entity_id, state, attributes, ha_url, headers)
        else:
          # Неизвестный тип - пробуем сначала управление устройством, потом UI
          try:
            result = await self._set_state_device(entity_id, state, attributes, ha_url, headers)
          except Exception:
            result = await self._set_state_ui_only(entity_id, state, attributes, ha_url, headers)

      return result

    except Exception as e:
      logger.error(f"[HA-WebSocket] Set state error: {e}")
      return {"success": False, "error": str(e)}

  async def _set_state_ui_only(self, entity_id: str, state: str, attributes: Dict[str, Any], url: str,
                               headers: Dict[str, str]) -> Dict[str, Any]:
    """Установка состояния только в UI (для кастомных портов)"""
    try:
      api_url = f"{url}/api/states/{entity_id}"
      data = {"state": state}
      if attributes:
        data["attributes"] = attributes

      async with aiohttp.ClientSession() as session:
        async with session.post(api_url, headers=headers, json=data) as response:
          if response.status in [200, 201]:
            result = await response.json()
            logger.info(f"[HA-WebSocket] States API: State changed in UI")
            return {"success": True, "data": result, "method": "states_api"}
          else:
            error_text = await response.text()
            logger.error(f"[HA-WebSocket] States API: HTTP {response.status}")
            return {"success": False, "error": f"HTTP {response.status}: {error_text}", "method": "states_api"}

    except Exception as e:
      logger.error(f"[HA-WebSocket] States API: {e}")
      return {"success": False, "error": str(e), "method": "states_api"}

  async def _set_state_device(self, entity_id: str, state: str, attributes: Dict[str, Any], url: str,
                              headers: Dict[str, str]) -> Dict[str, Any]:
    """Установка состояния устройства (для существующих устройств)"""
    try:
      # Определяем сервис на основе типа сущности
      if entity_id.startswith('switch.'):
        service = 'switch/turn_on' if state.lower() in ['on', 'true', '1'] else 'switch/turn_off'
      elif entity_id.startswith('light.'):
        service = 'light/turn_on' if state.lower() in ['on', 'true', '1'] else 'light/turn_off'
      elif entity_id.startswith('fan.'):
        service = 'fan/turn_on' if state.lower() in ['on', 'true', '1'] else 'fan/turn_off'
      else:
        # Для других типов используем UI управление
        return await self._set_state_ui_only(entity_id, state, attributes, url, headers)

      api_url = f"{url}/api/services/{service}"
      data = {"entity_id": entity_id}
      if attributes:
        data.update(attributes)

      async with aiohttp.ClientSession() as session:
        async with session.post(api_url, headers=headers, json=data) as response:
          if response.status in [200, 201]:
            result = await response.json()
            logger.info(f"[HA-WebSocket] Services API: Command sent to device")
            return {"success": True, "data": result, "method": "services_api"}
          else:
            error_text = await response.text()
            logger.error(f"[HA-WebSocket] Services API: HTTP {response.status}")
            return {"success": False, "error": f"HTTP {response.status}: {error_text}", "method": "services_api"}

    except Exception as e:
      logger.error(f"[HA-WebSocket] Services API: {e}")
      return {"success": False, "error": str(e), "method": "services_api"}

  async def create_port(self, port_config: PortConfig) -> Dict[str, Any]:
    """Создание порта в Home Assistant через REST API"""
    try:
      # Формируем атрибуты
      attributes = {
        'friendly_name': port_config.name,
        'enabled_by_default': port_config.enabled_by_default,
        'force_update': port_config.force_update,
        'custom_component': 'my_home_addon',
        'source': 'websocket_client'
      }

      if port_config.device_class:
        attributes['device_class'] = port_config.device_class
      if port_config.unit_of_measurement:
        attributes['unit_of_measurement'] = port_config.unit_of_measurement
      if port_config.icon:
        attributes['icon'] = port_config.icon
      if port_config.state_class:
        attributes['state_class'] = port_config.state_class
      if port_config.entity_category:
        attributes['entity_category'] = port_config.entity_category
      if port_config.suggested_display_precision:
        attributes['suggested_display_precision'] = port_config.suggested_display_precision
      if port_config.attributes:
        attributes.update(port_config.attributes)

      # Создаем сущность через REST API
      result = await self._create_entity_via_rest(port_config.entity_id, "unknown", attributes)

      if result.get('success'):
        # Добавляем в список кастомных портов
        self.custom_ports.add(port_config.entity_id)
        logger.info(f"[HA-WebSocket] Created port: {port_config.entity_id}")
      else:
        logger.error(f"[HA-WebSocket] Failed to create port: {result.get('error')}")

      return result

    except Exception as e:
      logger.error(f"[HA-WebSocket] Create port error: {e}")
      return {"success": False, "error": str(e)}

  async def _create_entity_via_rest(self, entity_id: str, state: str, attributes: Dict[str, Any]) -> Dict[str, Any]:
    """Создание сущности через REST API"""
    try:
      ha_url = config.get_ha_url()
      token = config.get_ha_token()

      api_url = f"{ha_url}/api/states/{entity_id}"
      headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
      }

      data = {
        "state": state,
        "attributes": attributes
      }

      async with aiohttp.ClientSession() as session:
        async with session.post(api_url, headers=headers, json=data) as response:
          if response.status in [200, 201]:
            result = await response.json()
            logger.info(f"[HA-WebSocket] REST API: Entity created successfully")
            return {"success": True, "data": result, "method": "rest_api"}
          else:
            error_text = await response.text()
            logger.error(f"[HA-WebSocket] REST API: HTTP {response.status}")
            return {"success": False, "error": f"HTTP {response.status}: {error_text}", "method": "rest_api"}

    except Exception as e:
      logger.error(f"[HA-WebSocket] REST API: {e}")
      return {"success": False, "error": str(e), "method": "rest_api"}

  async def delete_port(self, entity_id: str) -> Dict[str, Any]:
    """Удаление порта из Home Assistant"""
    try:
      ha_url = config.get_ha_url()
      token = config.get_ha_token()

      api_url = f"{ha_url}/api/states/{entity_id}"
      headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
      }

      # Проверяем, существует ли сущность
      async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
          if response.status == 404:
            # Сущность не существует
            logger.info(f"[HA-WebSocket] Entity {entity_id} does not exist")
            if entity_id in self.custom_ports:
              self.custom_ports.remove(entity_id)
            return {"success": True, "message": f"Entity {entity_id} does not exist"}
          elif response.status == 200:
            # Сущность существует - удаляем через entity registry
            registry_url = f"{ha_url}/api/config/entity_registry/remove"
            registry_data = {"entity_id": entity_id}

            try:
              async with aiohttp.ClientSession() as reg_session:
                async with reg_session.post(registry_url, headers=headers, json=registry_data) as reg_response:
                  if reg_response.status in [200, 201, 204]:
                    logger.info(f"[HA-WebSocket] Entity {entity_id} removed successfully")
                    if entity_id in self.custom_ports:
                      self.custom_ports.remove(entity_id)
                    return {"success": True, "message": f"Entity {entity_id} deleted successfully"}
                  else:
                    error_text = await reg_response.text()
                    logger.error(f"[HA-WebSocket] Entity registry removal failed: HTTP {reg_response.status}")
                    # Fallback: mark as unavailable
                    return {"success": False, "error": f"HTTP {reg_response.status}: {error_text}"}
            except Exception as reg_error:
              logger.error(f"[HA-WebSocket] Entity registry error: {reg_error}")
              return {"success": False, "error": str(reg_error)}
          else:
            error_text = await response.text()
            logger.error(f"[HA-WebSocket] Get entity failed: HTTP {response.status}")
            return {"success": False, "error": f"HTTP {response.status}: {error_text}"}

    except Exception as e:
      logger.error(f"[HA-WebSocket] Delete port error: {e}")
      return {"success": False, "error": str(e)}

  async def subscribe_to_port(self, entity_id: str, handler: Callable):
    """Подписка на изменения конкретного порта"""
    try:
      # Добавляем порт и обработчик в подписки
      self.port_subscriptions[entity_id] = handler
      logger.info(f"[HA-WebSocket] Subscribed to port: {entity_id}")

    except Exception as e:
      logger.error(f"[HA-WebSocket] Subscribe to port error: {e}")

  async def unsubscribe_from_port(self, entity_id: str):
    """Отписка от изменений конкретного порта"""
    try:
      if entity_id in self.port_subscriptions:
        del self.port_subscriptions[entity_id]
        logger.info(f"[HA-WebSocket] Unsubscribed from port: {entity_id}")

    except Exception as e:
      logger.error(f"[HA-WebSocket] Unsubscribe from port error: {e}")

  async def ping(self) -> bool:
    """Проверка соединения"""
    try:
      return self.connected and self.authenticated
    except Exception as e:
      logger.error(f"[HA-WebSocket] Ping error: {e}")
      return False


# Глобальный экземпляр для совместимости
ha_websocket = HomeAssistantWebSocket()
