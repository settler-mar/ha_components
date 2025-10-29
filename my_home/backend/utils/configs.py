import yaml
from typing import Any, Dict
from utils.logger import config_logger as logger

from fastapi import FastAPI
import random
import string
import os
import json

default_config = {
  'db': {
    'url': 'sqlite:///../data/sql_app.db',
    'echo': False,
    'echo_pool': False,
    'check_same_thread': True
  },
  'gsheet': '',
  'local_networks': "192.168.0.1/24",
  'scan_timeout': 2,
  'is_fast_scan': True,
  'homeassistant': {
    'url': 'homeassistant.local:8123',
    'token': '',
    'timeout': 30,
    'retry_attempts': 3,
    'log_requests': True,
    'log_responses': False,
    'auto_sync': True,
    'published_ports': {},
    'port_entities': {},
    'entity_ports': {}
  }
}


class AppConfig:
  _config: dict = {}
  _need_save: bool = False

  def __init__(self, config_path: str = None):
    config_dir = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data'))
    if not os.path.exists(config_dir):
      os.makedirs(config_dir)
    if config_path is None:
      config_path = os.path.join(config_dir, 'config.yaml')
    self._config_path = config_path
    self._config = self._load_yaml()
    self._config.update(self._load_json())
    self._test_config()
    if self._need_save:
      self.save_yaml()

  def _load_yaml(self) -> dict:
    try:
      with open(self._config_path, 'r') as file:
        return yaml.safe_load(file) or {}
    except FileNotFoundError:
      return {}

  def _load_json(self) -> dict:
    try:
      import json
      json_path = self._config_path.replace('.yaml', '.json')
      with open(json_path, 'r') as file:
        return json.load(file) or {}
    except (FileNotFoundError, json.JSONDecodeError):
      return {}

  def _test_config(self, root_config: dict = None, root_default: dict = None, visited: set = None) -> None:
    root_config = root_config or self._config
    root_default = root_default or default_config
    visited = visited or set()
    
    # Проверяем, не обрабатывали ли мы уже этот объект
    config_id = id(root_config)
    if config_id in visited:
      return
    visited.add(config_id)
    
    for key, value in root_default.items():
      if key not in root_config:
        root_config[key] = value
        self._need_save = True
      elif isinstance(value, dict) and isinstance(root_config[key], dict):
        self._test_config(root_config[key], value, visited)

  def save_yaml(self) -> None:
    with open(self._config_path, 'w') as file:
      yaml.safe_dump(self._config, file)

  def __getitem__(self, key: str) -> Any:
    return self._config.get(key, None)

  def __setitem__(self, key: str, value: Any) -> None:
    raise AttributeError("Direct assignment is not allowed. Use set_value instead.")

  def set_value(self, path: list, value: Any, _config: dict) -> None:
    key = path[0]
    path = path[1:]
    if not path:
      _config[key] = value
    else:
      if key not in _config:
        _config[key] = {}
      if not isinstance(_config[key], dict):
        raise AttributeError(f"Path {key} is not a dictionary")
      self.set_value(path, value, _config[key])

  def __repr__(self) -> str:
    return f"AppConfig({self._config})"

  def create_routes(self, app: FastAPI):
    @app.get(f"/api/config", tags=["config"], response_model=dict)
    def get_config():
      return self._config

    @app.put(f"/api/config", tags=["config"])
    def set_config(path: str, value: Any):
      """
      Set config parameter.
      :param path: - path to parameter in config. Example: 'auth/algorithm'
      :param value:
      :return:
      """
      self.set_value([p for p in path.split('/') if p], value, self._config)
      self.save_yaml()
      return {'status': 'ok'}

  # HA Port Manager методы
  async def initialize_ha_ports(self):
    """Инициализация опубликованных портов HA из базы данных"""
    try:
      from db_models.ports import Ports
      from utils.db_utils import db_session

      with db_session() as db:
        # Загружаем все опубликованные порты из базы данных
        published_ports = db.query(Ports).filter(
          Ports.params['ha_published'].astext == 'true'
        ).all()

        # Извлекаем данные из объектов SQLAlchemy внутри контекста сессии
        port_data = []
        for port in published_ports:
          device_id = port.device_id
          port_code = port.code
          entity_id = port.params.get('entity_id', '') if port.params else ''
          port_data.append((device_id, port_code, entity_id))

        # Очищаем текущие данные
        self._config['homeassistant']['published_ports'] = {}
        self._config['homeassistant']['port_entities'] = {}
        self._config['homeassistant']['entity_ports'] = {}

        # Обрабатываем данные вне контекста сессии
        for device_id, port_code, entity_id in port_data:
          if entity_id:
            # Добавляем в published_ports
            if str(device_id) not in self._config['homeassistant']['published_ports']:
              self._config['homeassistant']['published_ports'][str(device_id)] = []
            self._config['homeassistant']['published_ports'][str(device_id)].append(port_code)

            # Добавляем в индексы
            port_key = f"{device_id}:{port_code}"
            self._config['homeassistant']['port_entities'][port_key] = entity_id
            self._config['homeassistant']['entity_ports'][entity_id] = port_key

        self.save_yaml()
        print(f"[AppConfig-HA] Initialized with {len(port_data)} published ports")

    except Exception as e:
      print(f"[AppConfig-HA] Error initializing HA ports: {e}")

  async def add_published_port(self, device_id: int, port_code: str, entity_id: str) -> bool:
    """Добавляет порт в список опубликованных"""
    try:
      device_key = str(device_id)
      port_key = f"{device_id}:{port_code}"

      # Добавляем в published_ports
      if device_key not in self._config['homeassistant']['published_ports']:
        self._config['homeassistant']['published_ports'][device_key] = []

      if port_code not in self._config['homeassistant']['published_ports'][device_key]:
        self._config['homeassistant']['published_ports'][device_key].append(port_code)

      # Добавляем в индексы
      self._config['homeassistant']['port_entities'][port_key] = entity_id
      self._config['homeassistant']['entity_ports'][entity_id] = port_key

      self.save_yaml()
      print(f"[AppConfig-HA] Added published port: {device_id}:{port_code} -> {entity_id}")
      return True

    except Exception as e:
      print(f"[AppConfig-HA] Error adding published port: {e}")
      return False

  async def remove_published_port(self, device_id: int, port_code: str) -> bool:
    """Удаляет порт из списка опубликованных"""
    try:
      device_key = str(device_id)
      port_key = f"{device_id}:{port_code}"

      # Удаляем из published_ports
      if device_key in self._config['homeassistant']['published_ports']:
        if port_code in self._config['homeassistant']['published_ports'][device_key]:
          self._config['homeassistant']['published_ports'][device_key].remove(port_code)

        # Если список пустой, удаляем устройство
        if not self._config['homeassistant']['published_ports'][device_key]:
          del self._config['homeassistant']['published_ports'][device_key]

      # Удаляем из индексов
      entity_id = self._config['homeassistant']['port_entities'].pop(port_key, None)
      if entity_id:
        self._config['homeassistant']['entity_ports'].pop(entity_id, None)

      self.save_yaml()
      print(f"[AppConfig-HA] Removed published port: {device_id}:{port_code}")
      return True

    except Exception as e:
      print(f"[AppConfig-HA] Error removing published port: {e}")
      return False

  async def is_port_published(self, device_id: int, port_code: str) -> bool:
    """Проверяет, опубликован ли порт в HA"""
    device_key = str(device_id)
    return (device_key in self._config['homeassistant']['published_ports'] and
            port_code in self._config['homeassistant']['published_ports'][device_key])

  async def get_published_ports(self, device_id: int) -> list:
    """Получает список опубликованных портов для устройства"""
    device_key = str(device_id)
    return self._config['homeassistant']['published_ports'].get(device_key, [])

  async def get_entity_id(self, device_id: int, port_code: str) -> str:
    """Получает entity_id для порта"""
    port_key = f"{device_id}:{port_code}"
    return self._config['homeassistant']['port_entities'].get(port_key, '')

  async def get_port_from_entity(self, entity_id: str) -> tuple:
    """Получает device_id и port_code по entity_id"""
    logger.debug(f"Looking for entity_id: {entity_id}")
    logger.debug(f"entity_ports keys: {list(self._config['homeassistant']['entity_ports'].keys())}")
    
    port_key = self._config['homeassistant']['entity_ports'].get(entity_id, '')
    logger.debug(f"Found port_key: {port_key}")
    
    if port_key and ':' in port_key:
      device_id, port_code = port_key.split(':', 1)
      logger.debug(f"Parsed device_id: {device_id}, port_code: {port_code}")
      return int(device_id), port_code
    
    logger.warning(f"No port_key found for entity_id: {entity_id}")
    return None, None

  async def handle_ha_state_change(self, entity_id: str, new_state: str) -> bool:
    """Обрабатывает изменение состояния в HA"""
    try:
      device_id, port_code = await self.get_port_from_entity(entity_id)
      if not device_id or not port_code:
        print(f"[AppConfig-HA] Unknown entity: {entity_id}")
        return False

      # Проверяем, что порт опубликован
      if not await self.is_port_published(device_id, port_code):
        print(f"[AppConfig-HA] Port {device_id}:{port_code} not published")
        return False

      # Отправляем команду на устройство
      await self._send_device_command(device_id, port_code, new_state)

      # Уведомляем фронтенд об изменении
      await self._broadcast_port_update(device_id, port_code, new_state)

      print(f"[AppConfig-HA] Handled state change: {entity_id} -> {new_state}")
      return True

    except Exception as e:
      print(f"[AppConfig-HA] Error handling state change: {e}")
      return False

  async def _send_device_command(self, device_id: int, port_code: str, state: str):
    """Отправляет команду на устройство"""
    try:
      from models.my_home import MyHomeClass

      my_home = MyHomeClass()
      client = my_home.get_client(device_id)

      if not client:
        print(f"[AppConfig-HA] Device {device_id} client not found")
        return

      if not hasattr(client, '_current_ws') or not client._current_ws:
        print(f"[AppConfig-HA] Device {device_id} WebSocket not connected")
        return

      # Определяем значение для отправки на устройство
      if state in ['on', 'ON', '1', 'true', 'True']:
        value = '1'
      elif state in ['off', 'OFF', '0', 'false', 'False']:
        value = '0'
      else:
        value = str(state)

      # Формируем команду в формате ESP: "code#value"
      command = f"{port_code}#{value}"

      # Отправляем команду через WebSocket устройства
      await client._current_ws.send_str(command)

      print(f"[AppConfig-HA] Sent command to device {device_id}: {command}")

    except Exception as e:
      print(f"[AppConfig-HA] Error sending device command: {e}")

  async def _broadcast_port_update(self, device_id: int, port_code: str, value: str):
    """Отправляет обновление порта через WebSocket для фронтенда"""
    try:
      from utils.socket_utils import connection_manager

      connection_manager.broadcast_log(
        text=f"Port {port_code} updated to {value}",
        level="info",
        device_id=device_id,
        pin_name=port_code,
        value=value,
        direction="in",
        action="port_update",
        class_name="AppConfig"
      )

    except Exception as e:
      print(f"[AppConfig-HA] Error broadcasting port update: {e}")

  async def sync_with_database(self, device_id: int) -> int:
    """Синхронизирует состояние с базой данных"""
    try:
      from db_models.ports import Ports
      from utils.db_utils import db_session

      with db_session() as db:
        # Получаем все опубликованные порты для устройства из БД
        db_ports = db.query(Ports).filter(
          Ports.device_id == device_id,
          Ports.params['ha_published'].astext == 'true'
        ).all()

        synced_count = 0

        # Извлекаем данные из объектов SQLAlchemy внутри контекста сессии
        port_data = []
        for port in db_ports:
          port_code = port.code
          entity_id = port.params.get('entity_id', '') if port.params else ''
          port_data.append((port_code, entity_id))

        # Обрабатываем данные вне контекста сессии
        for port_code, entity_id in port_data:
          if entity_id:
            # Добавляем в конфигурацию
            await self.add_published_port(device_id, port_code, entity_id)
            synced_count += 1

        print(f"[AppConfig-HA] Synced {synced_count} ports for device {device_id}")
        return synced_count

    except Exception as e:
      print(f"[AppConfig-HA] Error syncing with database: {e}")
      return 0

  def get_ha_status(self) -> dict:
    """Получает статус HA интеграции"""
    return {
      "published_devices": len(self._config['homeassistant']['published_ports']),
      "total_published_ports": sum(len(ports) for ports in self._config['homeassistant']['published_ports'].values()),
      "total_entities": len(self._config['homeassistant']['entity_ports']),
      "devices": self._config['homeassistant']['published_ports']
    }

  # HA конфигурационные методы
  def apply_default_ha_config(self):
    """Применяет дефолтную конфигурацию HA"""
    default_config = {
      'url': 'http://192.168.0.78:8123',  # Дефолтный URL из вашего примера
      'token': '',  # Пустой токен - пользователь может настроить позже
      'timeout': 30,
      'retry_attempts': 3,
      'log_requests': True,
      'log_responses': False,
      'auto_sync': True,
      'published_ports': {},
      'port_entities': {},
      'entity_ports': {}
    }
    
    # Обновляем только пустые значения
    for key, value in default_config.items():
      if not self._config['homeassistant'].get(key):
        self._config['homeassistant'][key] = value
    
    self.save_yaml()
    logger.info("Applied default Home Assistant configuration")

  def is_ha_configured(self) -> bool:
    """Проверяет, настроена ли конфигурация HA"""
    # Проверяем наличие URL (обязательно) и токена (опционально)
    url = self._config['homeassistant'].get('url', '')
    return bool(url.strip())

  def get_ha_url(self) -> str:
    """Получает URL Home Assistant"""
    url = self._config['homeassistant'].get('url', 'homeassistant.local:8123')
    if not url.startswith('http'):
      url = f"http://{url}"
    return url

  def get_ha_token(self) -> str:
    """Получает токен Home Assistant"""
    return self._config['homeassistant'].get('token', '')

  def get_ha_timeout(self) -> int:
    """Получает таймаут запросов"""
    return self._config['homeassistant'].get('timeout', 5)

  def get_ha_retry_attempts(self) -> int:
    """Получает количество попыток при ошибках"""
    return self._config['homeassistant'].get('retry_attempts', 3)

  def should_log_ha_requests(self) -> bool:
    """Проверяет, нужно ли логировать запросы"""
    return self._config['homeassistant'].get('log_requests', True)

  def should_log_ha_responses(self) -> bool:
    """Проверяет, нужно ли логировать ответы"""
    return self._config['homeassistant'].get('log_responses', False)

  def is_auto_sync_enabled(self) -> bool:
    """Проверяет, включена ли автосинхронизация"""
    return self._config['homeassistant'].get('auto_sync', True)

  def set_auto_sync(self, enabled: bool):
    """Включает/выключает автосинхронизацию"""
    self._config['homeassistant']['auto_sync'] = enabled
    self._need_save = True


config = AppConfig()
