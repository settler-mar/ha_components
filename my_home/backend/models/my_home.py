from fastapi import Depends, APIRouter, Query
from sqlalchemy.util import await_fallback
import paho.mqtt.client as mqtt
import json
from pprint import pprint
from typing import Optional, Union
from utils.db_utils import db_session
from db_models.devices import Devices as DbDevices
from db_models.ports import Ports as DbPorts
from models.device import get_ports_from_db
import threading
from datetime import datetime, timedelta
from utils.socket_utils import connection_manager
from utils.logs import log_print
from utils.logger import myhome_logger as logger
from ssdpy import SSDPClient
import asyncio
import aiohttp
import inspect
import time
import os
import requests
import hashlib
from utils.google_connector import GoogleConnector
from ipaddress import ip_address, AddressValueError
from fastapi.responses import JSONResponse
from utils.configs import config

import socket
import ipaddress

from models.device import MyHomeDeviceClient
from models.singelton import SingletonClass


async def fetch_info(session, ip, semaphore):
  url = f"http://{ip}/info"
  async with semaphore:
    try:
      async with session.get(url, timeout=5) as response:
        text = await response.text()
        if response.status == 200:
          data = json.loads(text)
        else:
          data = {"error": f"JSON decode error", "raw_response": text}
        data['ip'] = ip
        return ip, data
    except Exception as e:
      return ip, {"error": str(e)}


class ConfigVersionManager:
  def __init__(self, base_url, device_id, config_dir='/config', backup_root=None):
    from utils.configs import get_data_dir
    
    self.base_url = base_url.rstrip('/')
    self.device_id = device_id
    self.config_dir = config_dir
    
    # Используем универсальную функцию для определения пути к data
    if backup_root is None:
      data_dir = get_data_dir()
      backup_root = os.path.join(data_dir, 'backup')
    
    self.backup_root = os.path.realpath(os.path.join(backup_root, str(device_id)))
    logger.debug(f"Backup root: {self.backup_root}")
    self.log_file = os.path.join(self.backup_root, 'backup.log')
    self.old_log_file = os.path.join(self.backup_root, 'log.json')

    os.makedirs(self.backup_root, exist_ok=True)

    # Миграция старого log.json в backup.log
    self._migrate_old_log_file()

    if not os.path.exists(self.log_file):
      with open(self.log_file, 'w', encoding='utf-8') as f:
        f.write("")  # Создаем пустой текстовый файл

  def fetch_file_list(self):
    url = f"{self.base_url}/list?dir={self.config_dir}"
    resp = requests.get(url)
    resp.raise_for_status()
    file_list = resp.json()  # Ожидается список путей
    logger.debug(f"ConfigVersionManager ({self.device_id}) Fetched {len(file_list)} files from {url}")
    return file_list

  def download_file(self, path):
    logger.debug(f"Downloading file: {path}")
    url = self.base_url + os.path.join(self.config_dir, path.lstrip('/'))
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.content

  def get_latest_backup_dir(self):
    backups = sorted(
      [d for d in os.listdir(self.backup_root)
       if os.path.isdir(os.path.join(self.backup_root, d)) and d not in ['log.json', 'backup.log']],
      reverse=True
    )
    if backups:
      return os.path.join(self.backup_root, backups[0])
    return None

  def file_hash(self, content):
    return hashlib.md5(content).hexdigest()

  def _migrate_old_log_file(self):
    """
    Миграция старого log.json в новый формат backup.log
    """
    if not os.path.exists(self.old_log_file):
      return  # Нет старого файла для миграции

    if os.path.exists(self.log_file):
      # Если новый файл уже существует, удаляем старый
      try:
        os.remove(self.old_log_file)
        logger.debug(f"ConfigVersionManager removed old log.json for device {self.device_id}")
      except Exception as e:
        logger.error(f"ConfigVersionManager error removing old log.json for device {self.device_id}: {e}")
      return

    try:
      # Читаем старый JSON файл
      with open(self.old_log_file, 'r', encoding='utf-8') as f:
        old_data = json.load(f)

      # Конвертируем в новый текстовый формат
      with open(self.log_file, 'w', encoding='utf-8') as f:
        for entry in old_data:
          timestamp = entry.get('timestamp', '')
          changed_files = entry.get('changed_files', [])
          files_str = ', '.join(changed_files) if changed_files else 'No changes'
          f.write(f"{timestamp}: {files_str}\n")

      # Удаляем старый файл после успешной миграции
      os.remove(self.old_log_file)

      logger.info(
        f"ConfigVersionManager migrated log.json to backup.log for device {self.device_id} ({len(old_data)} entries)")

    except Exception as e:
      logger.error(f"ConfigVersionManager error migrating log.json for device {self.device_id}: {e}")
      # В случае ошибки создаем пустой новый файл
      try:
        with open(self.log_file, 'w', encoding='utf-8') as f:
          f.write("")
      except Exception:
        pass

  def load_history(self):
    """Загружаем историю из текстового файла"""
    if not os.path.exists(self.log_file):
      return []

    history = []
    with open(self.log_file, 'r', encoding='utf-8') as f:
      for line in f:
        line = line.strip()
        if line:
          try:
            # Парсим строку формата: "TIMESTAMP: changed_files"
            if ': ' in line:
              timestamp_str, files_str = line.split(': ', 1)
              history.append({
                'timestamp': timestamp_str,
                'changed_files': files_str.split(', ') if files_str else []
              })
          except Exception as e:
            logger.error(f"Error parsing log line: {line}, error: {e}")
    return history

  def save_history_entry(self, timestamp, changed_files):
    """Сохраняем запись в текстовом формате"""
    files_str = ', '.join(changed_files) if changed_files else 'No changes'
    log_line = f"{timestamp}: {files_str}\n"

    with open(self.log_file, 'a', encoding='utf-8') as f:
      f.write(log_line)

    # Обновляем время бэкапа в параметрах устройства
    self._update_device_backup_time(timestamp, changed_files)

  def _update_device_backup_time(self, timestamp, changed_files):
    """Обновляет время последнего бэкапа в параметрах устройства"""
    try:
      from utils.db_utils import db_session
      from db_models.devices import Devices as DbDevices

      with db_session() as db:
        device = db.query(DbDevices).filter(DbDevices.id == self.device_id).first()
        if device:
          params = device.params if isinstance(device.params, dict) else {}
          params['last_backup_time'] = timestamp
          params['last_backup_check'] = timestamp

          # Добавляем файлы в список загруженных (уникальные значения)
          uploaded_files = params.get('uploaded_files', [])
          for file in changed_files:
            if file not in uploaded_files:
              uploaded_files.append(file)
          params['uploaded_files'] = uploaded_files

          device.params = params
          db.commit()

          # Обновляем объект из БД
          db.refresh(device)

          # Извлекаем данные устройства внутри контекста сессии
          device_data = device.to_dict()

          # Отправляем WebSocket уведомление об обновлении устройства
          self._broadcast_device_update(self.device_id, device_data)
    except Exception as e:
      logger.error(f"Error updating device backup time: {e}")

  def _update_device_backup_time(self, device_id: int, has_changes: bool = False, changed_files_count: int = 0):
    """
    Обновляет время последнего бэкапа в device.params
    """
    try:
      with db_session() as db:
        device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
        if device:
          params = device.params if isinstance(device.params, dict) else {}

          current_time = datetime.now().isoformat()
          params['last_backup_time'] = current_time
          params['last_backup_check'] = current_time

          if has_changes:
            params['last_backup_files_count'] = changed_files_count

          device.params = params
          db.commit()
          db.refresh(device)

          # Извлекаем данные устройства внутри контекста сессии
          device_data = device.to_dict()

          # Отправляем WebSocket уведомление об обновлении
          self._broadcast_device_update(device_id, device_data)

          logger.info(f"[ConfigVersionManager] Updated backup time for device {device_id}")

    except Exception as e:
      logger.error(f"[ConfigVersionManager] Error updating backup time for device {device_id}: {e}")

  def _broadcast_device_update(self, device_id: int, device_data: dict):
    """
    Отправляет WebSocket уведомление об обновлении устройства
    """
    try:
      from utils.socket_utils import connection_manager
      import asyncio

      ws_data = {
        "type": "device",
        "action": "update",
        "data": {
          "device_id": device_id,
          "device": device_data,
          "ts": datetime.now().timestamp()
        }
      }

      # Запускаем broadcast в event loop
      try:
        loop = asyncio.get_running_loop()
        if loop and loop.is_running():
          asyncio.create_task(connection_manager.broadcast(ws_data))
        else:
          loop.run_until_complete(connection_manager.broadcast(ws_data))
      except RuntimeError:
        # Если нет активного loop, запускаем в новом потоке
        def broadcast_update():
          asyncio.run(connection_manager.broadcast(ws_data))

        threading.Thread(target=broadcast_update, daemon=True).start()

    except Exception as e:
      logger.error(f"Error broadcasting device update: {e}")

  def run_backup_if_changed(self):
    file_list = self.fetch_file_list()
    latest_backup_dir = self.get_latest_backup_dir()
    changes_detected = False
    current_files = {}
    changed_files = []

    for item in file_list:
      # Обрабатываем как строку или как объект с полем name
      if isinstance(item, str):
        file_path = item
      elif isinstance(item, dict) and 'name' in item:
        file_path = item['name']
      else:
        logger.warning(f"[ConfigVersionManager] ({self.device_id}) Skipping invalid file item: {item}")
        continue

      # Убираем ведущий слеш если есть
      if isinstance(file_path, str) and file_path.startswith('/'):
        file_path = file_path[1:]

      content = self.download_file(file_path)
      current_files[file_path] = content

      filename = os.path.basename(file_path)
      if latest_backup_dir:
        old_file_path = os.path.join(latest_backup_dir, filename)
        if os.path.exists(old_file_path):
          with open(old_file_path, 'rb') as f:
            old_content = f.read()
          if self.file_hash(content) != self.file_hash(old_content):
            changes_detected = True
            changed_files.append(filename)
        else:
          changes_detected = True
          changed_files.append(filename)
      else:
        changes_detected = True
        changed_files.append(filename)

    if changes_detected:
      timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
      new_backup_dir = os.path.join(self.backup_root, timestamp)
      os.makedirs(new_backup_dir, exist_ok=True)

      for path, content in current_files.items():
        filename = os.path.basename(path)
        with open(os.path.join(new_backup_dir, filename), 'wb') as f:
          f.write(content)

      self.save_history_entry(timestamp, changed_files)
      logger.info(f"[ConfigVersionManager] ({self.device_id}) Изменения сохранены: {timestamp}")

      # Обновляем время бэкапа в базе данных
      self._update_device_backup_time(self.device_id, has_changes=True, changed_files_count=len(changed_files))

      return {"has_changes": True, "changed_files": len(changed_files), "files": changed_files}
    else:
      logger.info(f"[ConfigVersionManager] ({self.device_id}) Изменений не обнаружено.")

      # Обновляем время проверки бэкапа (даже если изменений нет)
      self._update_device_backup_time(self.device_id, has_changes=False, changed_files_count=0)

      return {"has_changes": False, "changed_files": 0, "files": []}

  def run_forced_backup(self):
    """
    Форсированный бэкап всех файлов (независимо от изменений)
    """
    file_list = self.fetch_file_list()
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_dir = os.path.join(self.backup_root, timestamp)
    os.makedirs(backup_dir, exist_ok=True)

    backed_up_files = []

    for item in file_list:
      # Обрабатываем как строку или как объект с полем name
      if isinstance(item, str):
        path = item
      elif isinstance(item, dict) and 'name' in item:
        path = item['name']
      else:
        logger.warning(f"[ConfigVersionManager] ({self.device_id}) Skipping invalid file item: {item}")
        continue

      # Убираем ведущий слеш если есть
      if isinstance(path, str) and path.startswith('/'):
        path = path[1:]

      try:
        content = self.download_file(path)
        file_path = os.path.join(backup_dir, path.replace('/', '_'))

        with open(file_path, 'wb') as f:
          f.write(content)

        backed_up_files.append(path)
        logger.info(f"[ConfigVersionManager] ({self.device_id}) Forced backup: {path}")

      except Exception as e:
        logger.error(f"[ConfigVersionManager] ({self.device_id}) Error backing up {path}: {e}")

    if backed_up_files:
      self.save_history_entry(timestamp, backed_up_files)
      logger.info(f"[ConfigVersionManager] ({self.device_id}) Forced backup completed: {len(backed_up_files)} files")

      # Обновляем время бэкапа в базе данных
      self._update_device_backup_time(self.device_id, has_changes=True, changed_files_count=len(backed_up_files))

      return {"has_changes": True, "changed_files": len(backed_up_files), "files": backed_up_files}
    else:
      logger.warning(f"[ConfigVersionManager] ({self.device_id}) Forced backup failed: no files backed up")

      # Обновляем время проверки бэкапа (даже если бэкап не удался)
      self._update_device_backup_time(self.device_id, has_changes=False, changed_files_count=0)

      return {"has_changes": False, "changed_files": 0, "files": []}


class MyHomeClass(SingletonClass):
  type = 'myhome'
  connectors_list = {}
  _status: str = None
  _devices: dict[int, MyHomeDeviceClient] = {}  # device_id → клиент

  _save_config_hour = 1
  _save_logs_period = 2
  _save_logs_hour = 1
  _save_logs_minute = 1
  _devices_loaded = False  # Флаг для отслеживания загрузки устройств

  NETWORK = "192.168.1.0/24"
  PORT = 80
  SCAN_TIMEOUT = 2

  # Храним активные хосты
  active_hosts = []
  scanning = False
  save_config_process = False

  is_run = False

  params = {
    'save_config_hour': {
      'type': 'int',
      'default': 1,
      'description': 'Час сохранения конфигурации',
      'min': 0,
      'max': 23,
    },
    'save_logs_period': {
      'type': 'int',
      'default': 2,
      'description': 'Период сохранения логов (часы)',
      'min': 1,
      'max': 24,
    },
    '_save_logs_hour': {
      'type': 'int',
      'default': 1,
      'description': 'Час сохранения логов',
      'min': 0,
      'max': 23,
    },
    'save_logs_minute': {
      'type': 'int',
      'default': 2,
      'description': 'Минута сохранения логов',
      'min': 0,
      'max': 59,
    },
    'gsheet': {
      'type': 'str',
      'default': None,
      'description': 'ID Google Sheet для сохранения логов',
    }
  }

  devices_params = {
    'code': {
      'readonly': True,
    },
    'model': {
      'readonly': True,
    },
    'vendor': {
      'readonly': True,
    },
    'type': {
      'readonly': True,
    },
    'params.backup_config': {
      'type': 'bool',
      'default': True,
      'description': 'Сохранять конфигурацию',
    },
    'params.save_logs': {
      'type': 'bool',
      'default': True,
      'description': 'Сохранять логи',
    },
    'params.remove_logs': {
      'type': 'bool',
      'default': True,
      'description': 'Удалять логи после сохранения',
    },
    'params.log_save_method': {
      'type': 'list',
      'default': 'gsheet',
      'description': 'Метод сохранения логов',
      'options': {
        'local_save': 'На сервере',
        'gsheet': 'Google Sheets',
      },
    },
    'params.ip': {
      'type': 'str',
      'default': None,
      'description': 'IP адрес устройства',
      'readonly': True,
    },
    'params.mac': {
      'type': 'str',
      'default': None,
      'description': 'MAC адрес устройства',
      'readonly': True,
    },
    'params.ssid': {
      'type': 'str',
      'default': None,
      'description': 'SSID устройства',
      'readonly': True,
    },
    'params.flash_date': {
      'type': 'str',
      'default': None,
      'description': 'Дата прошивки устройства',
      'readonly': True,
    },
    'params.version': {
      'type': 'str',
      'default': None,
      'description': 'Версия прошивки устройства',
      'readonly': True,
    },
  }

  description = "Модули на основе проекта MyHome. Поддерживает Wi-Fi устройства на основе ESP8266 и ESP32."

  def __init__(self, **kwargs):
    self._id = kwargs.get('id', None)

    self.sheet = kwargs.get('params', {}).get('gsheet')

    self.thread = threading.Thread(target=self._run, daemon=True)
    self.stop_event = threading.Event()
    self.thread.start()

    self.NETWORK = config['local_networks'] or self.NETWORK
    self.SCAN_TIMEOUT = config['scan_timeout'] or self.SCAN_TIMEOUT
    self.is_fast_scan = config['is_fast_scan'] or True

    self._save_config_hour = int(config['save_config_hour'] or self._save_config_hour)
    self._save_logs_period = int(config['save_logs_period'] or self._save_logs_period)
    self._save_logs_hour = int(config['save_logs_hour'] or self._save_logs_hour)
    self._save_logs_minute = int(config['save_logs_minute'] or self._save_logs_minute)

    # Загружаем устройства только один раз
    if not self._devices_loaded:
      self.load_devices()
      self._devices_loaded = True

  def _save_logs_local(self, name, content, device_id, ip):
    from utils.configs import get_data_dir
    logs_root = os.path.join(get_data_dir(), "store", "backup", "logs")
    os.makedirs(logs_root, exist_ok=True)

    # Конкатенируем в файл по имени
    local_path = os.path.join(logs_root, name)
    with open(local_path, "a", encoding="utf-8") as f:
      f.write(content.strip())

    return True

  def _save_logs_gsheet(self, name, content, device_id, ip):
    data = [line.strip().split(',\t') for line in content.split('\n') if line.strip()]
    data = [[*line[:-1], line[-1].replace('.', ',')] for line in data]
    try:
      google_connector = GoogleConnector(False)  # Не строгий режим
      if google_connector and google_connector.enabled:
        google_connector.gsheet_add_row(self.sheet, '.'.join(name.split('.')[:-1]), data)
        return True
      else:
        logger.warning("[Logs] GoogleConnector недоступен, пропускаем сохранение в gsheet")
        return False
    except Exception as e:
      logger.error(f"[Logs] Ошибка при сохранении в gsheet: {e}")
      return False

  def _save_logs(self):
    # Логируем начало процесса сохранения логов
    connection_manager.broadcast_log(
      text="Начало сохранения логов с устройств",
      level="info",
      class_name="MyHomeClass",
      action="save_logs_start"
    )

    total_devices = 0
    processed_devices = 0
    total_logs = 0
    saved_logs = 0

    for device_id, device in self._devices.items():
      total_devices += 1
      params = device.params if isinstance(device.params, dict) else {}

      if not params.get("save_logs"):
        continue

      method = {
        'local_save': self._save_logs_local,
        'gsheet': self._save_logs_gsheet,
      }[params.get("log_save_method", "gsheet")]
      if method is None:
        continue  # неизвестный метод

      ip = params.get("ip")
      base_url = f"http://{ip}"
      device_name = device.name or f"Device {device_id}"

      # Логируем начало обработки устройства
      connection_manager.broadcast_log(
        text=f"Обработка логов с устройства {device_name} ({ip})",
        level="info",
        device_id=device_id,
        class_name="MyHomeClass",
        action="device_logs_start"
      )

      try:
        # Получаем список файлов из /logs
        response = requests.get(f"{base_url}/list?dir=/logs", timeout=5)
        response.raise_for_status()
        entries = response.json()

        device_logs_count = 0
        device_saved_count = 0

        for entry in entries:
          if entry.get("type") != "file":
            continue
          name = entry.get("name")
          if not name.endswith(".txt") or name in ['_.txt', 'clean.txt']:
            continue

          total_logs += 1
          device_logs_count += 1

          file_path = f"/logs/{name}"
          file_url = f"{base_url}{file_path}"

          # Скачиваем лог
          log_resp = requests.get(file_url, timeout=5)
          log_resp.raise_for_status()
          content = log_resp.text

          if method(name, content, device_id, ip):
            saved_logs += 1
            device_saved_count += 1

            # Логируем успешное сохранение лога
            connection_manager.broadcast_log(
              text=f"Лог {name} сохранен с устройства {device_name}",
              level="info",
              device_id=device_id,
              class_name="MyHomeClass",
              action="log_saved",
              value=name
            )
          else:
            # Логируем ошибку сохранения лога
            connection_manager.broadcast_log(
              text=f"Не удалось сохранить лог {name} с устройства {device_name}",
              level="error",
              device_id=device_id,
              class_name="MyHomeClass",
              action="log_save_failed",
              value=name
            )

          # Удаляем лог с устройства, если разрешено
          if params.get("remove_logs", True):
            delete_resp = requests.delete(
              f"{base_url}/edit", params={"path": file_path}, timeout=5
            )
            if delete_resp.status_code == 200:
              # Логируем удаление лога с устройства
              connection_manager.broadcast_log(
                text=f"Лог {name} удален с устройства {device_name}",
                level="info",
                device_id=device_id,
                class_name="MyHomeClass",
                action="log_deleted",
                value=name
              )
            else:
              # Логируем ошибку удаления лога
              connection_manager.broadcast_log(
                text=f"Не удалось удалить лог {name} с устройства {device_name}: {delete_resp.status_code}",
                level="warning",
                device_id=device_id,
                class_name="MyHomeClass",
                action="log_delete_failed",
                value=name
              )

        processed_devices += 1

        # Логируем завершение обработки устройства
        connection_manager.broadcast_log(
          text=f"Обработка логов устройства {device_name} завершена: {device_saved_count}/{device_logs_count} логов сохранено",
          level="info",
          device_id=device_id,
          class_name="MyHomeClass",
          action="device_logs_completed",
          value=f"{device_saved_count}/{device_logs_count}"
        )

      except Exception as e:
        # Логируем ошибку обработки устройства
        connection_manager.broadcast_log(
          text=f"Ошибка при обработке логов устройства {device_name}: {str(e)}",
          level="error",
          device_id=device_id,
          class_name="MyHomeClass",
          action="device_logs_error",
          value=str(e)
        )

    # Логируем завершение процесса сохранения логов
    connection_manager.broadcast_log(
      text=f"Сохранение логов завершено: {saved_logs}/{total_logs} логов сохранено с {processed_devices}/{total_devices} устройств",
      level="info",
      class_name="MyHomeClass",
      action="save_logs_completed",
      value=f"{saved_logs}/{total_logs} logs from {processed_devices}/{total_devices} devices"
    )

  def _save_config(self):
    self.save_config_process = True
    for device_id, device in self._devices.items():
      params = device.params if isinstance(device.params, dict) else {}
      if not params.get("backup_config"):
        continue

      base_url = f"http://{params.get('ip')}"
      logger.info(f"[Configs] Обрабатываю device {device_id} по адресу {base_url}")

      try:
        ConfigVersionManager(
          base_url=base_url,
          device_id=device_id
        ).run_backup_if_changed()
      except Exception as e:
        logger.error(f"[Configs] Ошибка при обработке {device_id}: {e}")
    self.save_config_process = False

  def _save_logs_for_device(self, device_id: int, device_ip: str):
    """
    Обертка для вызова сохранения логов конкретного устройства
    """
    return self.save_logs_for_device(device_id, device_ip)

  def save_logs_for_device(self, device_id: int, ip: str):
    """Сохранение логов для конкретного устройства (для ручного запуска)"""
    import requests
    from utils.socket_utils import connection_manager

    logger.info(f"[my home] Manual logs export for device {device_id} ({ip})")

    with db_session() as db:
      device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
      if not device:
        logger.error(f"[my home] Device {device_id} not found")
        return False

      device_name = device.name
      base_url = f"http://{ip}"

    # Используем локальное сохранение как основной метод
    method = self._save_logs_local
    saved_logs = 0
    total_logs = 0

    try:
      connection_manager.broadcast_log(
        text=f"Ручной экспорт логов с устройства {device_name} ({ip})",
        level="info",
        device_id=device_id,
        class_name="MyHomeClass",
        action="manual_logs_export_start"
      )

      # Получаем список файлов из /logs
      response = requests.get(f"{base_url}/list?dir=/logs", timeout=5)
      response.raise_for_status()
      entries = response.json()

      for entry in entries:
        if entry.get("type") != "file":
          continue
        name = entry.get("name")
        if not name.endswith(".txt") or name in ['_.txt', 'clean.txt']:
          continue

        total_logs += 1

        file_path = f"/logs/{name}"
        file_url = f"{base_url}{file_path}"

        # Скачиваем лог
        log_resp = requests.get(file_url, timeout=5)
        log_resp.raise_for_status()
        content = log_resp.text

        if method(name, content, device_id, ip):
          saved_logs += 1

          connection_manager.broadcast_log(
            text=f"Лог {name} сохранен с устройства {device_name}",
            level="info",
            device_id=device_id,
            class_name="MyHomeClass",
            action="log_saved",
            value=name
          )

      connection_manager.broadcast_log(
        text=f"Ручной экспорт завершен: {saved_logs} из {total_logs} логов сохранено с устройства {device_name}",
        level="info",
        device_id=device_id,
        class_name="MyHomeClass",
        action="manual_logs_export_complete",
        value=f"{saved_logs}/{total_logs}"
      )

      # Обновляем время экспорта логов в базе данных
      self._update_device_logs_export_time(device_id, exported_logs_count=saved_logs)

      return True

    except Exception as e:
      connection_manager.broadcast_log(
        text=f"Ошибка при ручном экспорте логов с устройства {device_name}: {str(e)}",
        level="error",
        device_id=device_id,
        class_name="MyHomeClass",
        action="manual_logs_export_error",
        value=str(e)
      )

      # Обновляем время попытки экспорта логов (даже при ошибке)
      self._update_device_logs_export_time(device_id, exported_logs_count=0)

      return False

  def _update_device_logs_export_time(self, device_id: int, exported_logs_count: int = 0):
    """
    Обновляет время последнего экспорта логов в device.params
    """
    try:
      with db_session() as db:
        device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
        if device:
          params = device.params if isinstance(device.params, dict) else {}

          current_time = datetime.now().isoformat()
          params['last_logs_export'] = current_time

          if exported_logs_count > 0:
            params['last_logs_export_count'] = exported_logs_count

          device.params = params
          db.commit()
          db.refresh(device)

          # Извлекаем данные устройства внутри контекста сессии
          device_data = device.to_dict()

          # Отправляем WebSocket уведомление об обновлении
          self._broadcast_device_update(device_id, device_data)

          logger.info(f"[MyHomeClass] Updated logs export time for device {device_id}")

    except Exception as e:
      logger.error(f"[MyHomeClass] Error updating logs export time for device {device_id}: {e}")

  def _run_all(self):
    self._save_logs()
    self._save_config()

  def _run(self):
    if self.is_run:
      logger.info("[my home] already running")
      return
    self.is_run = True
    while not self.stop_event.is_set():
      now = datetime.now()
      next_run_logs = self._get_next_run_time(now)
      next_run_config = now.replace(hour=self._save_config_hour,
                                    minute=0,
                                    second=0,
                                    microsecond=0)
      if next_run_config <= now:
        next_run_config += timedelta(days=1)

      action, next_run = [
        (self._save_logs, next_run_logs),
        (self._save_config, next_run_config),
      ][next_run_logs > next_run_config]
      if next_run_logs == next_run_config:
        action = self._run_all
      wait_seconds = (next_run - now).total_seconds()

      logger.debug(f"Waiting until {next_run.strftime('%Y-%m-%d %H:%M:%S')} ({int(wait_seconds)} sec) for {action}")
      if wait_seconds > 0:
        time.sleep(wait_seconds)

      if not self.stop_event.is_set():
        logger.info(f"Executing task at {datetime.now().strftime('%H:%M:%S')}")
        action()

    self.is_run = False

  def _get_next_run_time(self, current_time):
    base_time = current_time.replace(hour=self._save_logs_hour,
                                     minute=self._save_logs_minute,
                                     second=0,
                                     microsecond=0)
    while base_time <= current_time:
      base_time += timedelta(hours=self._save_logs_period)
    return base_time

  def __del__(self):
    logger.debug('MyHomeClass __del__')
    self.stop_event.set()
    if self.thread.is_alive():
      self.thread.join()

  def get_info(self):
    return {
      'status': self._status,
      'type': 'myhome',
      'device_count': len(self._devices),
    }

  def scan_host(self, ip: str):
    try:
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      sock.settimeout(self.SCAN_TIMEOUT)
      result = sock.connect_ex((str(ip), self.PORT))
      if result == 0:
        self.active_hosts.append(str(ip))
      sock.close()
    except:
      pass

  def fast_scan(self):
    if self.scanning:
      logger.warning('Scan already in progress')
      return False
    self.active_hosts = []
    self.scanning = True
    net = ipaddress.IPv4Network(self.NETWORK, strict=False)
    threads = []
    for ip in net.hosts():
      t = threading.Thread(target=self.scan_host, args=(ip,))
      threads.append(t)
      t.start()

    for t in threads:
      t.join()

    self.scanning = False
    return self.active_hosts

  async def scan(self):
    if self.is_fast_scan:
      ip_list = self.fast_scan()
    else:
      client = SSDPClient()
      devices = client.m_search("upnp:MHOME")
      ip_list = [driver['location'].split('/')[2].split(':')[0] for driver in devices]

    semaphore = asyncio.Semaphore(10)  # Максимум 5 одновременных запросов
    async with aiohttp.ClientSession() as session:
      tasks = [fetch_info(session, ip, semaphore) for ip in ip_list]
      results = await asyncio.gather(*tasks)
      return [value[1] for value in results if isinstance(value[1], dict) and 'error' not in value[1]]

  def load_devices(self):
    """
    Загрузка устройств из базы данных
    """
    # Сначала выполняем миграцию старых log.json файлов
    self._migrate_all_log_files()

    with db_session() as db:
      devices = db.query(DbDevices).all()

      # Фильтруем устройства с уникальными IP
      seen_ips = set()
      unique_devices = []

      for device in devices:
        device_ip = device.params.get('ip') if device.params else None
        if device_ip:
          if device_ip in seen_ips:
            logger.warning(f"Skipping device {device.id} with duplicate IP {device_ip}")
            continue
          seen_ips.add(device_ip)
        unique_devices.append(device)

      for device in unique_devices:
        self.add_device(device)
      logger.info(f"Loaded {len(self._devices.keys())} devices")

  def _migrate_all_log_files(self):
    """
    Миграция всех старых log.json файлов при старте системы
    """
    try:
      from utils.configs import get_data_dir
      backup_root = os.path.join(get_data_dir(), "backup")
      if not os.path.exists(backup_root):
        return

      migrated_count = 0

      # Проходим по всем папкам устройств
      for item in os.listdir(backup_root):
        device_path = os.path.join(backup_root, item)
        if not os.path.isdir(device_path):
          continue

        # Проверяем, что это папка с числовым ID устройства
        try:
          device_id = int(item)
        except ValueError:
          continue

        old_log_file = os.path.join(device_path, 'log.json')
        new_log_file = os.path.join(device_path, 'backup.log')

        # Если есть старый файл и нет нового
        if os.path.exists(old_log_file) and not os.path.exists(new_log_file):
          try:
            # Создаем ConfigVersionManager для миграции
            config_manager = ConfigVersionManager("", device_id)
            migrated_count += 1
          except Exception as e:
            logger.error(f"Error migrating log.json for device {device_id}: {e}")

      if migrated_count > 0:
        logger.info(f"Migrated {migrated_count} log.json files to backup.log format")

    except Exception as e:
      logger.error(f"[MyHome] Error during log files migration: {e}")

  def get_client(self, device_id: int) -> Optional[MyHomeDeviceClient]:
    """
    Возвращает MyHomeDeviceClient по ID устройства
    """
    return self._devices.get(device_id)

  def add_device(self, device):
    """
    device — это ORM-объект DbDevices
    """
    if isinstance(device, dict):
      logger.info(f"Adding device: {device['id']} - {device['name']}")
      device_id = device['id']
      device_ip = device.get('params', {}).get('ip') if device.get('params') else None
    else:
      logger.info(f"Adding device: {device.id} - {device.name}")
      device_id = device.id
      device_ip = device.params.get('ip') if device.params else None

    # Проверяем, не добавляем ли мы устройство повторно по ID
    if device_id in self._devices:
      existing_client = self._devices[device_id]
      # Проверяем, не запущен ли уже клиент
      if hasattr(existing_client, '_running') and existing_client._running:
        logger.warning(f"Device {device_id} already running, skipping duplicate add")
        return

    # Проверяем, не добавляем ли мы устройство повторно по IP
    if device_ip and MyHomeDeviceClient.is_ip_already_used(device_ip, self._devices):
      logger.warning(f"Device with IP {device_ip} already exists, skipping duplicate add for device {device_id}")
      return

    # Остановим старый клиент, если он есть
    old_client = self._devices.get(device_id)
    if old_client:
      try:
        # Проверяем, есть ли активный event loop
        try:
          loop = asyncio.get_running_loop()
          if loop and loop.is_running():
            asyncio.create_task(old_client.stop())
          else:
            # Если нет активного loop, запускаем в новом потоке
            def stop_client():
              asyncio.run(old_client.stop())

            threading.Thread(target=stop_client, daemon=True).start()
        except RuntimeError:
          # Если нет event loop, запускаем в новом потоке
          def stop_client():
            asyncio.run(old_client.stop())

          threading.Thread(target=stop_client, daemon=True).start()
      except Exception:
        pass

    # Создаём клиента из ORM-объекта
    client = MyHomeDeviceClient.from_db_device(
      device,
      on_initial_ports=self._on_initial_ports,
      on_value=self._on_value,
      on_connect=self._on_connect,
      on_disconnect=self._on_disconnect,
    )

    # Дополнительная проверка: если клиент с таким IP уже существует, не добавляем
    if device_ip and MyHomeDeviceClient.is_ip_already_used(device_ip, self._devices):
      logger.warning(f"Device with IP {device_ip} already exists, not adding device {device_id}")
      return

    self._devices[device_id] = client

    # Запускаем клиента
    try:
      loop = asyncio.get_running_loop()
    except RuntimeError:
      loop = None

    if loop and loop.is_running():
      client.start(loop)
    else:
      threading.Thread(target=self._run_client_in_thread, args=(client,), daemon=True).start()

  def _run_client_in_thread(self, client):
    """
    Запускает клиент в отдельном потоке с собственным event loop
    """
    try:
      asyncio.run(client.start())
    except Exception as e:
      logger.error(f"[MyHomeClass] Error running client in thread: {e}")

  # === callbacks ===
  def _on_connect(self, device_id: int):
    """
    Вызывается при подключении устройства
    """
    logger.success(f"Device {device_id} WebSocket connected")

    # Обновляем статус в БД
    try:
      with db_session() as db:
        device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
        if device:
          device.online = True
          device.last_seen = datetime.now()
          # Инициализируем поля в params для бэкапов и логов
          params = device.params if isinstance(device.params, dict) else {}
          if 'last_backup_time' not in params:
            params['last_backup_time'] = None
          if 'last_backup_check' not in params:
            params['last_backup_check'] = None
          if 'last_logs_export' not in params:
            params['last_logs_export'] = None
          if 'uploaded_files' not in params:
            params['uploaded_files'] = []
          device.params = params
          db.commit()

          # Обновляем объект из БД
          db.refresh(device)

          # Извлекаем данные устройства внутри контекста сессии
          device_data = device.to_dict()

          # Отправляем WebSocket уведомление об изменении статуса
          self._broadcast_device_status_update(device_id, device_data)
    except Exception as e:
      logger.error(f"[MyHome] Error updating online status for device {device_id}: {e}")

  def _on_disconnect(self, device_id: int):
    """
    Вызывается при отключении устройства
    """
    logger.warning(f"Device {device_id} WebSocket disconnected")

    # Обновляем статус в БД
    try:
      with db_session() as db:
        device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
        if device:
          device.online = False
          device.last_seen = datetime.now()
          db.commit()

          # Обновляем объект из БД
          db.refresh(device)

          # Извлекаем данные устройства внутри контекста сессии
          device_data = device.to_dict()

          # Отправляем WebSocket уведомление об изменении статуса
          self._broadcast_device_status_update(device_id, device_data)
    except Exception as e:
      logger.error(f"[MyHome] Error updating offline status for device {device_id}: {e}")

  def _broadcast_device_status_update(self, device_id: int, device_data: dict):
    """
    Отправляет WebSocket уведомление об изменении статуса устройства
    """
    try:
      from utils.socket_utils import connection_manager
      import asyncio

      ws_data = {
        "type": "device",
        "action": "status_update",
        "data": {
          "device_id": device_id,
          "device": device_data,
          "online": device_data.get('online', False),
          "last_seen": device_data.get('last_seen'),
          "ts": datetime.now().timestamp()
        }
      }

      # Запускаем broadcast в event loop
      try:
        loop = asyncio.get_running_loop()
        if loop and loop.is_running():
          asyncio.create_task(connection_manager.broadcast(ws_data))
        else:
          loop.run_until_complete(connection_manager.broadcast(ws_data))
      except RuntimeError:
        # Если нет активного loop, запускаем в новом потоке
        def broadcast_update():
          asyncio.run(connection_manager.broadcast(ws_data))

        threading.Thread(target=broadcast_update, daemon=True).start()

    except Exception as e:
      logger.error(f"Error broadcasting device status update: {e}")

  def _on_initial_ports(self, device_id: int, ports: list[dict]):
    """
    Регистрируем/обновляем порты в БД под устройством и синхронизируем runtime-модель.
    """
    logger.info(f"Initial ports for device {device_id}: {len(ports)} ports")
    # with db_session() as db:
    #   for p in ports:
    #     code = p["code"]
    #     direction = p["direction"]  # "in"/"out"
    #     kind = p["kind"]  # "analog"/"text"/"digital"/...
    #     val = p.get("val")
    #
    #     db_port = (
    #       db.query(DbPorts)
    #       .filter(DbPorts.device_id == device_id, DbPorts.code == code)
    #       .first()
    #     )
    #     if not db_port:
    #       db_port = DbPorts(
    #         device_id=device_id,
    #         code=code,
    #         name=code,
    #         direction=direction,
    #         kind=kind,
    #         last_value=val,
    #         params={"mqtt": p.get("mqtt")}
    #       )
    #       db.add(db_port)
    #     else:
    #       db_port.direction = direction
    #       db_port.kind = kind
    #       db_port.params = (db_port.params or {}) | {"mqtt": p.get("mqtt")}
    #       db_port.last_value = val
    #   db.commit()

    # оповестим runtime-слой/UI
    # Devices().reload_device(device_id)

  def _on_value(self, device_id: int, event: dict):
    """
    Пришло событие от WS по одному порту: обновим БД и нотифицируем UI/HA.
    event: {code, direction, kind, val, raw}
    """
    code = event.get("code")
    if not code:
      return

    # Обновляем БД
    pin_id = device_id  # По умолчанию используем device_id
    with db_session() as db:
      # Обновляем порт
      db_port = (
        db.query(DbPorts)
        .filter(DbPorts.device_id == device_id, DbPorts.code == code)
        .first()
      )
      if db_port:
        db_port.last_value = event.get("val")
        pin_id = db_port.id  # Используем ID порта если он найден

      # Обновляем статус устройства как онлайн при получении любых данных
      device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
      if device:
        device.online = True
        device.last_seen = datetime.now()

        # Инициализируем поля для отслеживания операций в params, если их нет
        params = device.params if isinstance(device.params, dict) else {}
        if 'last_backup_time' not in params:
          params['last_backup_time'] = None
        if 'last_backup_check' not in params:
          params['last_backup_check'] = None
        if 'last_logs_export' not in params:
          params['last_logs_export'] = None
        if 'uploaded_files' not in params:
          params['uploaded_files'] = []
        device.params = params

      db.commit()

    # Отправляем состояние в Home Assistant
    try:
      from utils.ha_manager import ha_manager
      import asyncio

      # Получаем значение из события
      value = event.get("val")
      if value is not None:
        # Отправляем состояние в HA асинхронно
        loop = asyncio.get_event_loop()
        if loop.is_running():
          asyncio.create_task(ha_manager.send_device_state_to_ha(device_id, code, value))
        else:
          loop.run_until_complete(ha_manager.send_device_state_to_ha(device_id, code, value))

    except Exception as e:
      logger.error(f"Error sending state to HA: {e}")

    # Пуш в WebSocket/UI
    try:
      from utils.socket_utils import connection_manager
      import asyncio

      ws_data = {
        "type": "port",
        "action": "in",
        "data": {
          "pin_id": pin_id,
          "device_id": device_id,
          "code": code,
          "value": event.get("val"),
          "value_raw": event.get("raw"),
          "direction": event.get("direction"),
          "kind": event.get("kind"),
          "ts": datetime.now().timestamp()
        }
      }

      # Запускаем broadcast в event loop
      loop = asyncio.get_event_loop()
      if loop.is_running():
        asyncio.create_task(connection_manager.broadcast(ws_data))
      else:
        loop.run_until_complete(connection_manager.broadcast(ws_data))

    except Exception as e:
      logger.error(f"Error broadcasting port update: {e}")


def add_routes(app: APIRouter, my_home: MyHomeClass):
  logger.info('Adding MYHOME routes')
  logger.debug(f"App type: {type(app)}")
  logger.debug(f"my_home type: {type(my_home)}")

  @app.get("/api/live/scan",
           tags=["live"])
  async def scan_myhome():
    return await MyHomeClass().scan()

  @app.get("/api/live/{ip}/get_value",
           tags=["live"])
  async def get_myhome_value(ip: str):
    """
    Получить значение устройства по IP с информацией о публикации в HA
    """
    try:
      # Получаем данные с устройства
      async with aiohttp.ClientSession() as session:
        url = f"http://{ip}/values"
        async with session.get(url) as response:
          if response.status == 200:
            data = await response.text()
            try:
              device_data = json.loads(data)
            except json.JSONDecodeError as e:
              return {"error": f"JSON decode error: {str(e)}", "raw_response": data}
          else:
            return {"error": f"Error: {response.status}"}

      # Находим устройство в базе данных по IP
      device_id = None
      with db_session() as db:
        devices = db.query(DbDevices).all()
        for device in devices:
          if device.params and device.params.get('ip') == ip:
            device_id = device.id
            break

      # Если устройство найдено, добавляем информацию о публикации в HA
      if device_id:
        from utils.configs import config

        # Получаем информацию о портах из базы данных
        ports_info = await get_ports_from_db(device_id)

        # Создаем словарь для быстрого поиска статуса публикации
        ha_status = {}
        for port_info in ports_info:
          ha_status[port_info['code']] = {
            code: value for code, value in port_info.items() if code not in ['code']
          }

        def add_ha_info_to_port(port):
          if isinstance(port, dict):
            if 'code' in port and port['code'] in ha_status:
              port['ha'] = ha_status[port['code']]
            if 'data' in port:
              port['data'] = add_ha_info_to_port(port['data'])
            return port
          elif isinstance(port, list):
            return [add_ha_info_to_port(p) for p in port]
          return port

      return add_ha_info_to_port(device_data)

    except Exception as e:
      logger.error(f"Error in get_myhome_value for {ip}: {e}")
      return {"error": f"Internal error: {str(e)}"}

  @app.get("/api/live/add/{ip}", tags=["live"])
  async def add_myhome_value(ip: str):
    """
    Добавить значение устройства по IP
    """
    # Валидация IP-адреса
    try:
      ip_address(ip)
    except Exception as e:
      return JSONResponse({'error': f'Invalid IP address "{ip}"'}, 422)

    timeout = aiohttp.ClientTimeout(sock_connect=5, total=10)

    async with aiohttp.ClientSession(timeout=timeout) as session:
      try:
        # Получение /values
        url_values = f"http://{ip}/values"
        async with session.get(url_values) as response:
          if response.status != 200:
            return JSONResponse({'error': f"Ошибка при запросе: {url_values}"}, 422)
          text = await response.text()
          try:
            values = json.loads(text)
          except json.JSONDecodeError as e:
            return JSONResponse({'error': f"Ошибка парсинга /values: {str(e)}"}, 422)

        # Получение /info
        url_info = f"http://{ip}/info"
        async with session.get(url_info) as response:
          if response.status != 200:
            return JSONResponse({'error': f"Ошибка при запросе: {url_info}"}, 422)
          text = await response.text()
          try:
            info = json.loads(text)
          except json.JSONDecodeError as e:
            return JSONResponse({'error': f"Ошибка парсинга /info: {str(e)}"}, 422)

      except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        return JSONResponse({'error': f"Ошибка при запросе: {str(e)}"}, 422)

    # Работа с БД
    with db_session() as db:
      db_device = db.query(DbDevices).filter(DbDevices.code == info['chip_id']).first()
      if db_device is None:
        db_device = DbDevices(
          code=info['chip_id'],
          name=info['name'],
          model=info['config_name'],
          vendor='my_home',
          params={'backup_config': True},
          description='',
        )
        db.add(db_device)
        db.commit()
        db.refresh(db_device)

      db_device.vendor = info.get('fr_name', 'my_home')
      params = db_device.params if isinstance(db_device.params, dict) else {}
      params.update({
        'ip': ip,
        'mac': info.get('mac'),
        'ssid': info.get('ssid'),
        'flash_date': info.get('flash_date'),
        'version': info.get('version'),
        'save_logs': any(el for el in values if el.get('title') == "LOGS")
      })
      db_device.params = params
      db_device.type = info.get('flash_chip_revision')
      db.commit()
      db.refresh(db_device)
      db_device.on_create()

      # Проверяем, не добавлено ли уже устройство по ID
      if db_device.id not in my_home._devices:
        # Дополнительная проверка по IP
        if MyHomeDeviceClient.is_ip_already_used(ip, my_home._devices):
          logger.warning(f"Device with IP {ip} already exists, skipping add for device {db_device.id}")
        else:
          my_home.add_device(db_device)
      else:
        logger.info(f"Device {db_device.id} already exists, skipping add")

    return {
      "status": "ok",
      "values": values,
      "info": info,
    }

  @app.get("/api/live/backup/", tags=["live"])
  async def backup_myhome():
    """
    Запустить бэкап конфигурации всех устройств
    """
    my_home._save_config()
    return {"status": "ok", "message": "Backup started"}

  @app.get("/api/live/save_logs/", tags=["live"])
  async def logs_myhome():
    """
    Запустить сохранение логов всех устройств
    """
    my_home._save_logs()
    return {"status": "ok", "message": "Logs saving started"}

  @app.get("/api/live/test", tags=["live"])
  async def test_live():
    """
    Тестовый эндпоинт для проверки работы live маршрутов
    """
    logger.info("=== GET /api/live/test called ===")
    return {"status": "ok", "message": "Live routes are working", "my_home_exists": my_home is not None}

  @app.get("/api/live/{ip}/info", tags=["live"])
  async def get_device_info(ip: str):
    """
    Получить информацию об устройстве с эндпоинта /info
    """
    try:
      url = f"http://{ip}/info"
      async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
          text = await response.text()
          if response.status == 200:
            try:
              data = json.loads(text)
              data['ip'] = ip
              return data
            except json.JSONDecodeError:
              return {"error": "JSON decode error", "raw_response": text, "ip": ip}
          else:
            return {"error": f"HTTP {response.status}", "raw_response": text, "ip": ip}
    except asyncio.TimeoutError:
      return {"error": "Timeout error", "ip": ip}
    except Exception as e:
      logger.error(f"Error fetching device info for {ip}: {e}")
      return {"error": str(e), "ip": ip}

  @app.get("/api/live/devices", tags=["live"])
  async def get_devices():
    """
    Получить все устройства
    """
    try:
      logger.info("=== GET /api/live/devices called ===")

      if my_home is None:
        logger.error("my_home is None in get_devices")
        return []

      logger.debug(f"Getting devices, my_home._devices count: {len(my_home._devices)}")
      logger.debug(f"my_home._devices keys: {list(my_home._devices.keys())}")

      result = []
      for device_id, client in my_home._devices.items():
        try:
          info = client.meta
          result.append({
            **info,
            'device_id': client.device_id,
            'online': client._online,
            'id': client.id,
            'code': client.code,
            'name': client.name,
            'model': client.model,
            'vendor': client.vendor,
            'type': client.type,
            'description': client.description,
            'params': client.params,
            'ip': client.ip,
          })

        except Exception as e:
          # Если клиент недоступен, пропускаем или можно добавить ошибку
          logger.error(f"Error processing device {device_id}: {e}")
          continue

      logger.info(f"Returning {len(result)} devices")
      return result

    except Exception as e:
      logger.error(f"Error in get_devices endpoint: {e}")
      import traceback
      logger.error(f"Traceback: {traceback.format_exc()}")
      return []

  @app.get("/api/live/ports", tags=["live"])
  async def get_ports():
    """
    Получить все порты всех устройств
    """
    logger.info("=== GET /api/live/ports called ===")

    if my_home is None:
      logger.error("my_home is None in get_ports")
      return {"ports": []}

    logger.debug(f"Getting ports, my_home._devices count: {len(my_home._devices)}")
    result = []
    for device_id, client in my_home._devices.items():
      try:
        ports = await client.get_ports_cached()
        for p in ports:
          # гарантируем наличие last_update
          if "last_update" not in p:
            p["last_update"] = datetime.now().isoformat()
          result.append({
            "device_id": client.device_id,
            "device_name": client.name,
            "code": p.get("code"),
            "val": p.get("val"),
            "last_update": p.get("last_update"),
            "direction": p.get("direction"),
            "kind": p.get("kind"),
            "unit": p.get("unit"),
            "title": p.get("title"),
            "group_title": p.get("group_title"),
            "raw": p.get("raw"),
          })
      except Exception as e:
        # Если клиент недоступен, пропускаем или можно добавить ошибку
        logger.error(f"Error processing ports for device {device_id}: {e}")
        continue

    logger.info(f"Returning {len(result)} ports")
    return {"ports": result}


logger.info("MYHOME routes added successfully")
logger.debug(f"Added /api/live/devices and /api/live/ports endpoints")
