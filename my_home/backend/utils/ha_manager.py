"""
Менеджер Home Assistant с централизованной логикой
- Автоматическое подключение и переподключение
- Синхронизация портов с базой данных
- Двухсторонняя обработка портов
"""
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from db_models.devices import Devices
from db_models.ports import Ports
from utils.db_utils import db_session
from utils.configs import config
from utils.home_assistant import HomeAssistantWebSocket, PortConfig, PortType, ControlType
from utils.value_mapper import value_mapper

# Импортируем глобальный логгер
from utils.logger import ha_logger as logger


class HomeAssistantManager:
  """Менеджер Home Assistant с централизованной логикой"""

  def __init__(self):
    self.ha_client = HomeAssistantWebSocket()
    self.initialized = False
    self.auto_sync_enabled = True
    self.sync_in_progress = False
    self.device_clients = {}  # Удаляем, будем использовать my_home
    self.my_home = None  # Добавляем ссылку на my_home

    # Кэш опубликованных портов
    self._published_ports_cache = []
    self._ports_cache_timestamp = None

    # Настройка колбэков
    self.ha_client.set_callbacks(
      on_port_state_changed=self._on_port_state_changed,
      on_port_created=self._on_port_created,
      on_port_deleted=self._on_port_deleted,
      on_service_called=self._on_service_called,
      on_connection_status_changed=self._on_connection_status_changed
    )

  async def initialize(self) -> bool:
    """Инициализация менеджера HA"""
    try:
      logger.info("Initializing Home Assistant manager...")

      # Проверяем конфигурацию HA
      if not config.is_ha_configured():
        logger.warning("Home Assistant not configured, applying default configuration")
        config.apply_default_ha_config()
        logger.info(
          f"Applied default HA config: URL={config.get_ha_url()}, Token={'***' if config.get_ha_token() else 'None'}")

      # Проверяем токен
      token = config.get_ha_token()
      if not token or token.strip() == "":
        logger.warning("Home Assistant token is not configured or empty")
        logger.warning("To get a Home Assistant token:")
        logger.warning("1. Open Home Assistant web interface")
        logger.warning("2. Go to Profile (click on your user icon)")
        logger.warning("3. Scroll down to 'Long-lived access tokens'")
        logger.warning("4. Click 'Create token'")
        logger.warning("5. Give it a name (e.g., 'MyHome Integration')")
        logger.warning("6. Copy the generated token")
        logger.warning("7. Add it to your config.yaml file:")
        logger.warning("   homeassistant:")
        logger.warning("     token: 'your_token_here'")
        logger.warning("Continuing with limited functionality...")

      # Подключаемся к HA
      logger.info(f"Connecting to Home Assistant at {config.get_ha_url()}")
      connected = await self.ha_client.connect()
      if not connected:
        logger.error("Failed to connect to Home Assistant")
        return False

      logger.success("Successfully connected to Home Assistant")

      # Проверяем статус подключения после подключения
      logger.info(
        f"Connection status: connected={self.ha_client.connected}, authenticated={self.ha_client.authenticated}")

      # Если подключение не удалось, прерываем инициализацию
      if not self.ha_client.connected:
        logger.error("HA WebSocket connection failed during initialization")
        return False

      # Получаем настройки автосинхронизации
      self.auto_sync_enabled = config.is_auto_sync_enabled()
      logger.info(f"Auto-sync enabled: {self.auto_sync_enabled}")

      # Загружаем кэш опубликованных портов
      logger.info("Loading published ports cache from database...")
      await self._refresh_ports_cache(force_log=True)
      logger.info(f"Cache loaded: {len(self._published_ports_cache)} published ports")

      # Проверяем статус подключения перед синхронизацией
      logger.info(
        f"Pre-sync connection status: connected={self.ha_client.connected}, authenticated={self.ha_client.authenticated}")

      # Выполняем синхронизацию если включена
      if self.auto_sync_enabled:
        logger.info("Auto-sync enabled, performing initial synchronization...")
        await self.sync_ports_with_ha()
      else:
        logger.info("Auto-sync disabled, skipping initial synchronization")

      self.initialized = True
      logger.success("Home Assistant manager initialized successfully")
      return True

    except Exception as e:
      logger.error(f"Initialization failed: {e}")
      return False

  async def shutdown(self):
    """Завершение работы менеджера"""
    try:
      logger.info("Shutting down Home Assistant manager...")

      if self.ha_client:
        await self.ha_client.disconnect()

      self.initialized = False
      logger.success("Home Assistant manager shutdown complete")

    except Exception as e:
      logger.error(f"Shutdown error: {e}")

  async def sync_ports_with_ha(self) -> Dict[str, Any]:
    """Синхронизация портов с Home Assistant"""
    if self.sync_in_progress:
      logger.warning("Sync already in progress, skipping")
      return {"success": False, "error": "Sync already in progress"}

    try:
      self.sync_in_progress = True
      logger.info("Starting ports synchronization with Home Assistant...")

      # Получаем все порты из кэша (все порты из БД)
      all_ports = await self._get_ports_from_database()
      logger.debug(f"Loaded {len(all_ports)} total ports from cache")

      # Фильтруем только те порты, которые должны быть опубликованы в HA
      ports_to_sync = await self._filter_published_ports(all_ports)
      logger.info(f"Filtered {len(ports_to_sync)} ports to sync from {len(all_ports)} total ports")

      # Получаем все сущности из HA
      logger.info("Requesting states from Home Assistant...")

      # Проверяем статус подключения перед запросом
      if not self.ha_client.connected:
        logger.error("HA WebSocket is not connected")
        return {"success": False, "error": "HA WebSocket is not connected"}

      if not self.ha_client.authenticated:
        logger.warning("HA WebSocket is connected but not authenticated")
        # Продолжаем попытку, так как некоторые команды могут работать без аутентификации

      ha_states = await self.ha_client.get_states()

      if not ha_states.get('success'):
        error_msg = ha_states.get('error', 'Unknown error')
        logger.error(f"Failed to get HA states: {error_msg}")
        logger.error(f"Full HA states response: {ha_states}")
        return {"success": False, "error": f"Failed to get HA states: {error_msg}"}

      ha_entities = ha_states.get('result', [])
      ha_our_entities = [entity for entity in ha_entities
                         if entity.get('entity_id', '').startswith('switch.myhome') or
                         entity.get('entity_id', '').startswith('sensor.myhome') or
                         entity.get('entity_id', '').startswith('binary_sensor.myhome')]

      logger.info(f"Found {len(ha_our_entities)} MyHome entities in HA")
      logger.info(f"Ports to sync: {len(ports_to_sync)} from {len(all_ports)} total ports")

      # Анализируем различия
      sync_result = await self._analyze_and_sync(ports_to_sync, ha_our_entities)

      logger.success(f"Sync completed: {sync_result}")
      return sync_result

    except Exception as e:
      logger.error(f"Sync error: {e}")
      return {"success": False, "error": str(e)}
    finally:
      self.sync_in_progress = False

  async def _get_ports_from_database(self) -> List[Dict[str, Any]]:
    """Получение портов из кэша (больше не обращается к БД напрямую)"""
    if not self._published_ports_cache:
      logger.warning("Ports cache is empty, refreshing...")
      await self._refresh_ports_cache()
    else:
      logger.debug(f"Returning cached ports: {len(self._published_ports_cache)} ports")

    return self._published_ports_cache

  async def _refresh_ports_cache(self, force_log: bool = False):
    """Обновление кэша всех портов из базы данных"""
    try:
      logger.debug("Refreshing ports cache from database...")

      # Загружаем все порты из БД (без фильтрации)
      all_ports = await self._load_ports_from_database()

      # Обновляем кэш всеми портами
      self._published_ports_cache = all_ports
      self._ports_cache_timestamp = datetime.now()

      if force_log:
        logger.info(f"Cache refreshed: {len(all_ports)} total ports loaded")
      else:
        logger.debug(f"Cache refreshed: {len(all_ports)} total ports loaded")

    except Exception as e:
      logger.error(f"Error refreshing ports cache: {e}")
      self._published_ports_cache = []
      self._ports_cache_timestamp = None

  async def _load_ports_from_database(self) -> List[Dict[str, Any]]:
    """Загрузка всех портов из базы данных (без проверки публикации в HA)"""
    ports = []

    try:
      logger.debug("Loading all ports from database...")
      with db_session() as db:
        # Получаем все устройства
        devices = db.query(Devices).all()
        logger.debug(f"Found {len(devices)} devices in database")

        # Извлекаем данные из объектов SQLAlchemy внутри контекста сессии
        device_data = []
        total_ports = 0

        for device in devices:
          device_ports = db.query(Ports).filter(Ports.device_id == device.id).all()
          total_ports += len(device_ports)

          for port in device_ports:
            # Загружаем все порты без проверки публикации
            port_data = {
              'device_id': device.id,
              'port_code': port.code,
              'port_type': port.type,
              'params': port.params or {},
              'device_name': device.name,
              'port_name': port.name
            }
            device_data.append(port_data)

            # Логируем информацию о порте
            params = port.params or {}
            ha_published = params.get('ha_published', False)
            entity_id = params.get('entity_id', 'N/A')
            logger.debug(
              f"Loaded port: {port.code} ({device.name} - {port.name}) - Published: {ha_published}, Entity: {entity_id}")

        # Обрабатываем данные вне контекста сессии
        ports = device_data
        logger.debug(f"Loaded {total_ports} total ports from {len(devices)} devices")

    except Exception as e:
      logger.error(f"Error loading ports from database: {e}")

    return ports

  async def _filter_published_ports(self, all_ports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Фильтрация портов, опубликованных в HA"""
    published_ports = []

    try:
      logger.debug("Filtering published ports...")

      for port in all_ports:
        device_id = port['device_id']
        port_code = port['port_code']
        params = port.get('params', {})

        # Проверяем, опубликован ли порт в HA (из данных БД)
        is_published = params.get('ha_published', False)

        if is_published:
          # Получаем entity_id из params или генерируем
          entity_id = params.get('entity_id')
          if not entity_id:
            entity_id = await config.get_entity_id(device_id, port_code)

          # Добавляем entity_id к данным порта
          port_data = port.copy()
          port_data['entity_id'] = entity_id
          published_ports.append(port_data)

          logger.debug(f"Port published: {entity_id} ({port['device_name']} - {port['port_name']})")
        else:
          logger.debug(f"Port not published: {port_code} ({port['device_name']} - {port['port_name']})")

      logger.debug(f"Filtered {len(published_ports)} published ports from {len(all_ports)} total ports")

    except Exception as e:
      logger.error(f"Error filtering published ports: {e}")

    return published_ports

  async def get_all_ports_from_database(self) -> List[Dict[str, Any]]:
    """Получение всех портов из базы данных (без фильтрации по публикации)"""
    try:
      return await self._load_ports_from_database()
    except Exception as e:
      logger.error(f"Error getting all ports from database: {e}")
      return []

  async def _analyze_and_sync(self, db_ports: List[Dict[str, Any]], ha_entities: List[Dict[str, Any]]) -> Dict[
    str, Any]:
    """Анализ и синхронизация портов"""
    try:
      logger.info(f"Starting sync analysis: {len(db_ports)} ports in DB, {len(ha_entities)} entities in HA")

      # Создаем словари для быстрого поиска
      db_entities = {port['entity_id']: port for port in db_ports}
      ha_entities_dict = {entity['entity_id']: entity for entity in ha_entities}

      # Находим различия
      to_create = []  # Порты из БД, которых нет в HA
      to_delete = []  # Порты в HA, которых нет в БД
      to_update = []  # Порты с разными конфигурациями

      # Проверяем порты из БД
      for entity_id, port_data in db_entities.items():
        if entity_id not in ha_entities_dict:
          to_create.append(port_data)
          logger.debug(
            f"Port to create: {entity_id} ({port_data.get('device_name', 'Unknown')} - {port_data.get('port_name', 'Unknown')})")
        else:
          # Проверяем, нужно ли обновить конфигурацию
          ha_entity = ha_entities_dict[entity_id]
          if self._needs_update(port_data, ha_entity):
            to_update.append(port_data)
            logger.debug(
              f"Port to update: {entity_id} ({port_data.get('device_name', 'Unknown')} - {port_data.get('port_name', 'Unknown')})")

      # Проверяем порты в HA
      for entity_id, ha_entity in ha_entities_dict.items():
        if entity_id not in db_entities:
          to_delete.append(ha_entity)
          logger.debug(f"Entity to delete: {entity_id}")

      logger.info(f"Sync plan: {len(to_create)} to create, {len(to_delete)} to delete, {len(to_update)} to update")

      # Выполняем синхронизацию
      results = {
        'created': 0,
        'deleted': 0,
        'updated': 0,
        'errors': []
      }

      # Создаем недостающие порты
      for port_data in to_create:
        try:
          logger.info(
            f"Creating port: {port_data['entity_id']} ({port_data.get('device_name', 'Unknown')} - {port_data.get('port_name', 'Unknown')})")
          await self._create_port_in_ha(port_data)

          # Добавляем порт в конфигурацию
          await config.add_published_port(port_data['device_id'], port_data['port_code'], port_data['entity_id'])

          # Сохраняем entity_id в базе данных
          await self._save_entity_id_to_db(port_data)

          # Обновляем кэш
          await self._refresh_ports_cache()

          results['created'] += 1
          logger.success(f"Successfully created: {port_data['entity_id']}")
        except Exception as e:
          error_msg = f"Failed to create {port_data['entity_id']}: {e}"
          results['errors'].append(error_msg)
          logger.error(error_msg)
          logger.error(f"{error_msg}")

      # Удаляем лишние порты
      for ha_entity in to_delete:
        try:
          logger.info(f"Deleting entity: {ha_entity['entity_id']}")
          await self._delete_port_from_ha(ha_entity['entity_id'])
          results['deleted'] += 1
          logger.success(f"Successfully deleted: {ha_entity['entity_id']}")
        except Exception as e:
          error_msg = f"Failed to delete {ha_entity['entity_id']}: {e}"
          results['errors'].append(error_msg)
          logger.error(error_msg)

      # Обновляем измененные порты
      for port_data in to_update:
        try:
          logger.info(
            f"Updating port: {port_data['entity_id']} ({port_data.get('device_name', 'Unknown')} - {port_data.get('port_name', 'Unknown')})")
          await self._update_port_in_ha(port_data)
          results['updated'] += 1
          logger.success(f"Successfully updated: {port_data['entity_id']}")
        except Exception as e:
          error_msg = f"Failed to update {port_data['entity_id']}: {e}"
          results['errors'].append(error_msg)
          logger.error(error_msg)

      # Финальное сообщение с детальной статистикой
      total_operations = results['created'] + results['deleted'] + results['updated']
      error_count = len(results['errors'])
      total_published_ports = len(db_ports)  # Общее количество опубликованных портов

      if error_count > 0:
        logger.warning(
          f"Sync completed with {error_count} errors: {results['created']} created, {results['deleted']} deleted, {results['updated']} updated")
        logger.info(f"Total published ports: {total_published_ports}")
        for error in results['errors']:
          logger.error(f"  - {error}")
      else:
        logger.success(
          f"Sync completed successfully: {results['created']} created, {results['deleted']} deleted, {results['updated']} updated")
        logger.info(f"Total published ports: {total_published_ports}")

      return {
        'success': True,
        'message': f"Sync completed: {results['created']} created, {results['deleted']} deleted, {results['updated']} updated. Total published ports: {total_published_ports}",
        'details': results,
        'total_published_ports': total_published_ports
      }

    except Exception as e:
      logger.error(f"Analyze and sync error: {e}")
      return {"success": False, "error": str(e)}

  async def _save_entity_id_to_db(self, port_data: Dict[str, Any]):
    """Сохранение entity_id в базе данных"""
    try:
      device_id = port_data['device_id']
      port_code = port_data['port_code']
      entity_id = port_data['entity_id']

      logger.debug(f"Saving entity_id to DB: {entity_id} for device {device_id}, port {port_code}")

      with db_session() as db:
        # Находим порт в базе данных
        port = db.query(Ports).filter(
          Ports.device_id == device_id,
          Ports.code == port_code
        ).first()

        if port:
          # Обновляем params с entity_id
          if not port.params:
            port.params = {}

          port.params['entity_id'] = entity_id
          db.commit()
          logger.debug(f"Entity ID saved to DB: {entity_id}")
        else:
          logger.warning(f"Port not found in DB: device {device_id}, port {port_code}")

    except Exception as e:
      logger.error(f"Error saving entity_id to DB: {e}")

  def _needs_update(self, port_data: Dict[str, Any], ha_entity: Dict[str, Any]) -> bool:
    """Проверка, нужно ли обновить конфигурацию порта"""
    try:
      # Сравниваем основные атрибуты
      ha_attrs = ha_entity.get('attributes', {})

      # Проверяем friendly_name
      expected_name = port_data.get('port_name', '')
      actual_name = ha_attrs.get('friendly_name', '')
      if expected_name != actual_name:
        return True

      # Проверяем device_class
      expected_device_class = port_data.get('params', {}).get('device_class', '')
      actual_device_class = ha_attrs.get('device_class', '')
      if expected_device_class != actual_device_class:
        return True

      # Проверяем unit_of_measurement
      expected_unit = port_data.get('params', {}).get('unit_of_measurement', '')
      actual_unit = ha_attrs.get('unit_of_measurement', '')
      if expected_unit != actual_unit:
        return True

      return False

    except Exception as e:
      logger.error(f"Error checking if update needed: {e}")
      return False

  async def _create_port_in_ha(self, port_data: Dict[str, Any]):
    """Создание порта в Home Assistant"""
    try:
      # Определяем тип порта
      port_type = port_data.get('port_type', 'switch')
      entity_type = 'switch' if port_type == 'switch' else 'sensor'

      # Создаем конфигурацию порта
      port_config = PortConfig(
        entity_id=port_data['entity_id'],
        name=port_data.get('port_name', port_data['port_code']),
        port_type=PortType.SWITCH if port_type == 'switch' else PortType.SENSOR,
        device_class=port_data.get('params', {}).get('device_class'),
        unit_of_measurement=port_data.get('params', {}).get('unit_of_measurement'),
        icon=port_data.get('params', {}).get('icon'),
        state_class=port_data.get('params', {}).get('state_class'),
        entity_category=port_data.get('params', {}).get('entity_category'),
        enabled_by_default=port_data.get('params', {}).get('enabled_by_default', True),
        force_update=port_data.get('params', {}).get('force_update', False),
        suggested_display_precision=port_data.get('params', {}).get('suggested_display_precision'),
        attributes=port_data.get('params', {}).get('attributes', {})
      )

      # Создаем порт
      result = await self.ha_client.create_port(port_config)
      if result.get('success'):
        logger.success(f"Created port in HA: {port_data['entity_id']}")
      else:
        raise Exception(result.get('error', 'Unknown error'))

    except Exception as e:
      logger.error(f"Error creating port in HA: {e}")
      raise

  async def _delete_port_from_ha(self, entity_id: str):
    """Удаление порта из Home Assistant"""
    try:
      result = await self.ha_client.delete_port(entity_id)
      if result.get('success'):
        logger.success(f"Deleted port from HA: {entity_id}")
      else:
        raise Exception(result.get('error', 'Unknown error'))

    except Exception as e:
      logger.error(f"Error deleting port from HA: {e}")
      raise

  async def _update_port_in_ha(self, port_data: Dict[str, Any]):
    """Обновление порта в Home Assistant"""
    try:
      # Получаем текущее состояние
      current_state = await self.ha_client.get_state(port_data['entity_id'])
      if not current_state.get('success'):
        raise Exception("Failed to get current state")

      # Обновляем атрибуты
      attributes = current_state['data'].get('attributes', {})

      # Обновляем основные атрибуты
      if 'port_name' in port_data:
        attributes['friendly_name'] = port_data['port_name']
      elif 'name' in port_data:
        attributes['friendly_name'] = port_data['name']

      params = port_data.get('params', {})
      if 'device_class' in params:
        attributes['device_class'] = params['device_class']
      if 'unit_of_measurement' in params:
        attributes['unit_of_measurement'] = params['unit_of_measurement']
      if 'icon' in params:
        attributes['icon'] = params['icon']
      if 'state_class' in params:
        attributes['state_class'] = params['state_class']
      if 'entity_category' in params:
        attributes['entity_category'] = params['entity_category']

      # Обновляем состояние
      current_state_value = current_state['data'].get('state', 'unknown')
      result = await self.ha_client.set_state(
        port_data['entity_id'],
        current_state_value,
        ControlType.UI,
        attributes
      )

      if result.get('success'):
        logger.success(f"Updated port in HA: {port_data['entity_id']}")
      else:
        raise Exception(result.get('error', 'Unknown error'))

    except Exception as e:
      logger.error(f"Error updating port in HA: {e}")
      raise

  async def handle_device_port_change(self, device_id: int, port_code: str, new_value: Any) -> bool:
    """Обработка изменения порта на устройстве (отправка в HA)"""
    try:
      # Проверяем, опубликован ли порт
      if not config.is_port_published(device_id, port_code):
        return False

      entity_id = config.get_entity_id(device_id, port_code)

      # Определяем новое состояние
      if isinstance(new_value, bool):
        state = 'on' if new_value else 'off'
      elif isinstance(new_value, (int, float)):
        state = str(new_value)
      else:
        state = str(new_value)

      # Отправляем в HA
      result = await self.ha_client.set_state(entity_id, state, ControlType.UI)

      if result.get('success'):
        logger.success(f"Port change sent to HA: {entity_id} = {state}")
        return True
      else:
        logger.error(f" Failed to send port change to HA: {result.get('error')}")
        return False

    except Exception as e:
      logger.error(f" Error handling device port change: {e}")
      return False

  async def _on_port_state_changed(self, entity_id: str, new_state: Dict[str, Any], old_state: Dict[str, Any]):
    """Обработка изменения состояния порта в HA (отправка на устройство)"""
    try:
      # Получаем информацию о порте из конфигурации
      device_id, port_code = await config.get_port_from_entity(entity_id)
      if not device_id or not port_code:
        logger.warning(f"Port info not found for entity: {entity_id}")
        return

      # Получаем новое значение
      new_value = new_state.get('state')
      if new_value is None:
        return

      # Преобразуем значение
      if new_value in ['on', 'off']:
        value = new_value == 'on'
      elif new_value.isdigit():
        value = int(new_value)
      elif new_value.replace('.', '').isdigit():
        value = float(new_value)
      else:
        value = new_value

      # Отправляем команду на устройство
      await self._send_command_to_device(device_id, port_code, value)

    except Exception as e:
      logger.error(f" Error handling port state change: {e}")

  async def _send_command_to_device(self, device_id: int, port_code: str, value: Any):
    """Отправка команды на устройство"""
    try:
      # Получаем клиент устройства через my_home
      device_client = self.get_device_client(device_id)
      if not device_client:
        logger.warning(f"Device client not found for device {device_id}")
        return

      # Проверяем, что устройство онлайн
      if not device_client._online:
        logger.warning(f"Device {device_id} is offline, cannot send command")
        return

      # Преобразуем значение из HA в формат устройства
      port_info = self._get_port_info_from_cache(port_code, device_id)
      mapped_value = value_mapper.map_ha_to_device(port_code, value, port_info)
      logger.debug(f"Mapped HA value {value} to device value {mapped_value} for port {port_code}")

      # Отправляем команду через метод send_command (формат ESP: "code#value")
      success = await device_client.send_command(port_code, mapped_value)

      if success:
        logger.info(f"Command sent successfully to device {device_id}, port {port_code}: {value} -> {mapped_value}")
      else:
        logger.error(f"Failed to send command to device {device_id}, port {port_code}: {value} -> {mapped_value}")

    except Exception as e:
      logger.error(f"Error sending command to device: {e}")
      import traceback
      logger.error(f"Traceback: {traceback.format_exc()}")

  async def _on_port_created(self, entity_id: str):
    """Обработка создания порта"""
    logger.info(f" Port created: {entity_id}")

  async def _on_port_deleted(self, entity_id: str):
    """Обработка удаления порта"""
    logger.info(f" Port deleted: {entity_id}")

  async def _on_service_called(self, entity_id: str, domain: str, service: str, service_data: Dict[str, Any]):
    """Обработка вызова сервиса"""
    try:
      logger.info(f"Service called: {domain}.{service} for {entity_id} with data: {service_data}")

      # Получаем информацию о порте из конфигурации
      device_id, port_code = await config.get_port_from_entity(entity_id)
      if not device_id or not port_code:
        logger.warning(f"Port info not found for entity: {entity_id}")
        return

      # Обрабатываем различные типы сервисов
      if domain == 'switch':
        if service == 'turn_on':
          await self._send_command_to_device(device_id, port_code, True)
        elif service == 'turn_off':
          await self._send_command_to_device(device_id, port_code, False)
        elif service == 'toggle':
          # Получаем текущее состояние и инвертируем его
          current_state = await self.ha_client.get_state(entity_id)
          if current_state and current_state.get('state') == 'on':
            await self._send_command_to_device(device_id, port_code, False)
          else:
            await self._send_command_to_device(device_id, port_code, True)

      elif domain == 'input_number':
        if service == 'set_value':
          value = service_data.get('value')
          if value is not None:
            await self._send_command_to_device(device_id, port_code, value)

      elif domain == 'input_boolean':
        if service == 'turn_on':
          await self._send_command_to_device(device_id, port_code, True)
        elif service == 'turn_off':
          await self._send_command_to_device(device_id, port_code, False)

      elif domain == 'input_select':
        if service == 'select_option':
          option = service_data.get('option')
          if option is not None:
            await self._send_command_to_device(device_id, port_code, option)

      else:
        logger.info(f"Unhandled service: {domain}.{service} for {entity_id}")

    except Exception as e:
      logger.error(f"Error handling service call: {e}")
      import traceback
      logger.error(f"Traceback: {traceback.format_exc()}")

  async def _on_connection_status_changed(self, connected: bool):
    """Обработка изменения статуса подключения"""
    logger.info(f" Connection status changed: {'connected' if connected else 'disconnected'}")

    if connected and self.auto_sync_enabled:
      # При переподключении выполняем синхронизацию
      await self.sync_ports_with_ha()

  def set_my_home(self, my_home):
    """Установка ссылки на my_home"""
    self.my_home = my_home
    logger.info(f"MyHome reference set, devices count: {len(my_home._devices) if my_home else 0}")

  def get_device_client(self, device_id: int):
    """Получение клиента устройства через my_home"""
    if not self.my_home:
      logger.warning(f"MyHome not set, cannot get device client for {device_id}")
      return None
    return self.my_home.get_client(device_id)

  async def send_device_state_to_ha(self, device_id: int, port_code: str, value: Any):
    """Отправка состояния устройства в Home Assistant"""
    try:
      logger.debug(f"Sending device state to HA: device_id={device_id}, port_code={port_code}, value={value}")
      
      # Получаем entity_id для порта
      entity_id = await config.get_entity_id(device_id, port_code)
      if not entity_id:
        logger.debug(f"No entity_id found for device {device_id}, port {port_code}")
        return

      logger.debug(f"Entity ID: {entity_id}")

      # Проверяем, что порт опубликован в HA
      if not await config.is_port_published(device_id, port_code):
        logger.debug(f"Port {device_id}:{port_code} is not published to HA")
        return

      # Преобразуем значение в формат HA
      port_info = self._get_port_info_from_cache(port_code, device_id)
      logger.debug(f"Port info for mapping: {port_info}")
      
      ha_value = value_mapper.map_device_to_ha(port_code, value, port_info)
      ha_state = str(ha_value) if not isinstance(ha_value, str) else ha_value
      
      logger.debug(f"Mapped value: {value} -> {ha_value} -> {ha_state}")

      # Отправляем состояние в HA с сохранением friendly_name
      if self.ha_client and self.ha_client.connected:
        # Получаем friendly_name из порта
        friendly_name = None
        if port_info:
          friendly_name = port_info.get('name') or port_info.get('port_name')
        
        # Формируем атрибуты для сохранения friendly_name
        attributes = {}
        if friendly_name:
          attributes['friendly_name'] = friendly_name
        
        await self.ha_client.set_state(entity_id, ha_state, ControlType.UI, attributes)
        logger.debug(f"State sent to HA: {entity_id} = {ha_state} (friendly_name: {friendly_name})")
      else:
        logger.warning(f"HA client not connected, cannot send state for {entity_id}")

    except Exception as e:
      logger.error(f"Error sending device state to HA: {e}")
      import traceback
      logger.error(f"Traceback: {traceback.format_exc()}")

  def _get_port_info_from_cache(self, port_code: str, device_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Получает информацию о порте из кэша или базы данных"""
    try:
      logger.debug(f"Looking for port info: port_code={port_code}, device_id={device_id}")
      logger.debug(f"Cache contains {len(self._published_ports_cache)} ports")
      
      # Сначала ищем в кэше опубликованных портов
      for port in self._published_ports_cache:
        if port.get('port_code') == port_code:
          # Если указан device_id, проверяем соответствие
          if device_id is None or port.get('device_id') == device_id:
            logger.debug(f"Found port in cache: {port}")
            # Нормализуем данные порта для маппера
            normalized_port = self._normalize_port_data(port)
            return normalized_port
      
      logger.debug(f"Port {port_code} not found in cache")
      
      # Если не найден в кэше, ищем в базе данных
      if device_id is not None:
        logger.debug(f"Port {port_code} not found in cache, searching in database for device {device_id}")
        return self._get_port_info_from_db(device_id, port_code)
      
      return None
    except Exception as e:
      logger.error(f"Error getting port info from cache: {e}")
      return None

  def _normalize_port_data(self, port_data: Dict[str, Any]) -> Dict[str, Any]:
    """Нормализует данные порта для маппера"""
    normalized = port_data.copy()
    
    # Если есть port_type, но нет kind, используем port_type как kind
    if 'port_type' in normalized and 'kind' not in normalized:
      normalized['kind'] = normalized['port_type']
    
    # Если есть port_type и kind, приоритет у kind
    elif 'port_type' in normalized and 'kind' in normalized:
      # kind уже есть, оставляем как есть
      pass
    
    # Если нет ни port_type, ни kind, устанавливаем unknown
    elif 'kind' not in normalized:
      normalized['kind'] = 'unknown'
    
    logger.debug(f"Normalized port data: {normalized}")
    return normalized

  def _get_port_info_from_db(self, device_id: int, port_code: str) -> Optional[Dict[str, Any]]:
    """Получает информацию о порте из базы данных"""
    try:
      logger.debug(f"Searching in DB: device_id={device_id}, port_code={port_code}")
      
      with db_session() as db:
        port = db.query(Ports).filter(
          Ports.device_id == device_id,
          Ports.code == port_code
        ).first()
        
        if port:
          # Преобразуем SQLAlchemy объект в словарь
          port_data = {
            'device_id': port.device_id,
            'port_code': port.code,
            'kind': port.kind,
            'direction': port.direction,
            'name': port.name,
            'params': port.params or {}
          }
          logger.debug(f"Found port in DB: {port_code} (type: {port.kind}, direction: {port.direction})")
          logger.debug(f"Port data: {port_data}")
          return port_data
        else:
          logger.warning(f"Port not found in DB: device {device_id}, port {port_code}")
          
          # Давайте посмотрим, какие порты есть для этого устройства
          all_ports = db.query(Ports).filter(Ports.device_id == device_id).all()
          logger.debug(f"All ports for device {device_id}: {[(p.code, p.kind) for p in all_ports]}")
          
          return None
          
    except Exception as e:
      logger.error(f"Error getting port info from DB: {e}")
      return None

  def get_status(self) -> Dict[str, Any]:
    """Получение статуса менеджера"""
    return {
      'initialized': self.initialized,
      'auto_sync_enabled': self.auto_sync_enabled,
      'sync_in_progress': self.sync_in_progress,
      'ha_client_status': self.ha_client.get_connection_status() if self.ha_client else None,
      'device_clients_count': len(self.device_clients),
      'cache_status': self.get_cache_status()
    }

  async def get_published_ports_count(self) -> int:
    """Получение количества опубликованных портов"""
    try:
      # Получаем все порты из кэша
      all_ports = await self._get_ports_from_database()

      # Фильтруем только опубликованные порты
      published_ports = await self._filter_published_ports(all_ports)

      return len(published_ports)
    except Exception as e:
      logger.error(f"Error getting published ports count: {e}")
      return 0

  async def get_published_ports_summary(self) -> Dict[str, Any]:
    """Получение сводки по опубликованным портам"""
    try:
      # Получаем все порты из кэша
      all_ports = await self._get_ports_from_database()

      # Фильтруем только опубликованные порты
      published_ports = await self._filter_published_ports(all_ports)

      # Группируем по устройствам
      devices_summary = {}
      for port in published_ports:
        device_id = port['device_id']
        device_name = port['device_name']

        if device_id not in devices_summary:
          devices_summary[device_id] = {
            'device_name': device_name,
            'ports_count': 0,
            'ports': []
          }

        devices_summary[device_id]['ports_count'] += 1
        devices_summary[device_id]['ports'].append({
          'entity_id': port['entity_id'],
          'port_name': port['port_name'],
          'port_type': port['port_type']
        })

      return {
        'total_published_ports': len(published_ports),
        'total_ports': len(all_ports),
        'devices_count': len(devices_summary),
        'devices_summary': devices_summary,
        'cache_timestamp': self._ports_cache_timestamp.isoformat() if self._ports_cache_timestamp else None
      }

    except Exception as e:
      logger.error(f"Error getting published ports summary: {e}")
      return {
        'total_published_ports': 0,
        'total_ports': 0,
        'devices_count': 0,
        'devices_summary': {},
        'cache_timestamp': None
      }

  async def add_port_to_cache(self, device_id: int, port_code: str, port_data: Dict[str, Any]):
    """Добавление порта в кэш (работает только с буфером)"""
    try:
      # Проверяем, опубликован ли порт
      if await config.is_port_published(device_id, port_code):
        entity_id = await config.get_entity_id(device_id, port_code)

        # Ищем существующий порт в кэше
        existing_port = None
        for i, cached_port in enumerate(self._published_ports_cache):
          if cached_port['device_id'] == device_id and cached_port['port_code'] == port_code:
            existing_port = i
            break

        port_entry = {
          'device_id': device_id,
          'port_code': port_code,
          'entity_id': entity_id,
          'port_type': port_data.get('type', 'switch'),
          'params': port_data.get('params', {}),
          'device_name': port_data.get('device_name', 'Unknown'),
          'port_name': port_data.get('name', port_code)
        }

        if existing_port is not None:
          # Обновляем существующий порт
          self._published_ports_cache[existing_port] = port_entry
          logger.debug(f"Updated port in cache: {entity_id}")
        else:
          # Добавляем новый порт
          self._published_ports_cache.append(port_entry)
          logger.debug(f"Added port to cache: {entity_id}")

        self._ports_cache_timestamp = datetime.now()
        logger.info(f"Port added/updated in cache: {entity_id}")

    except Exception as e:
      logger.error(f"Error adding port to cache: {e}")

  async def remove_port_from_cache(self, device_id: int, port_code: str):
    """Удаление порта из кэша (работает только с буфером)"""
    try:
      # Ищем порт в кэше
      for i, cached_port in enumerate(self._published_ports_cache):
        if cached_port['device_id'] == device_id and cached_port['port_code'] == port_code:
          removed_port = self._published_ports_cache.pop(i)
          logger.info(f"Removed port from cache: {removed_port['entity_id']}")
          self._ports_cache_timestamp = datetime.now()
          break

    except Exception as e:
      logger.error(f"Error removing port from cache: {e}")

  async def update_port_in_cache(self, device_id: int, port_code: str, port_data: Dict[str, Any]):
    """Обновление порта в кэше (работает только с буфером)"""
    try:
      # Ищем порт в кэше
      for i, cached_port in enumerate(self._published_ports_cache):
        if cached_port['device_id'] == device_id and cached_port['port_code'] == port_code:
          # Обновляем данные порта
          if await config.is_port_published(device_id, port_code):
            entity_id = await config.get_entity_id(device_id, port_code)
            self._published_ports_cache[i].update({
              'entity_id': entity_id,
              'port_type': port_data.get('type', cached_port['port_type']),
              'params': port_data.get('params', cached_port['params']),
              'device_name': port_data.get('device_name', cached_port['device_name']),
              'port_name': port_data.get('name', cached_port['port_name'])
            })
            logger.info(f"Updated port in cache: {entity_id}")
          else:
            # Порт больше не опубликован, удаляем из кэша
            removed_port = self._published_ports_cache.pop(i)
            logger.info(f"Port no longer published, removed from cache: {removed_port['entity_id']}")

          self._ports_cache_timestamp = datetime.now()
          break

    except Exception as e:
      logger.error(f"Error updating port in cache: {e}")

  def get_cache_status(self) -> Dict[str, Any]:
    """Получение статуса кэша портов"""
    return {
      'cache_size': len(self._published_ports_cache),
      'cache_timestamp': self._ports_cache_timestamp.isoformat() if self._ports_cache_timestamp else None,
      'cache_age_seconds': (
          datetime.now() - self._ports_cache_timestamp).total_seconds() if self._ports_cache_timestamp else None,
      'is_cache_empty': len(self._published_ports_cache) == 0
    }

  async def enable_auto_sync(self, enabled: bool):
    """Включение/выключение автосинхронизации"""
    self.auto_sync_enabled = enabled
    config.set_auto_sync(enabled)
    logger.info(f" Auto sync {'enabled' if enabled else 'disabled'}")

  async def force_sync(self) -> Dict[str, Any]:
    """Принудительная синхронизация"""
    return await self.sync_ports_with_ha()


# Глобальный экземпляр менеджера
ha_manager = HomeAssistantManager()
