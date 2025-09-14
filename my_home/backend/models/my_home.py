from fastapi import Depends, APIRouter, Query
from sqlalchemy.util import await_fallback
import paho.mqtt.client as mqtt
import json
from pprint import pprint
from typing import Optional, Union
from utils.db_utils import db_session
from db_models.devices import Devices as DbDevices
from db_models.ports import Ports as DbPorts
import threading
from datetime import datetime, timedelta
from utils.socket_utils import connection_manager
from utils.logs import log_print
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
  def __init__(self, base_url, device_id, config_dir='/config', backup_root='../data/backup'):
    self.base_url = base_url.rstrip('/')
    self.device_id = device_id
    self.config_dir = config_dir
    self.backup_root = os.path.realpath(os.path.join(backup_root, str(device_id)))
    print(self.backup_root)
    self.log_file = os.path.join(self.backup_root, 'log.json')

    os.makedirs(self.backup_root, exist_ok=True)
    if not os.path.exists(self.log_file):
      with open(self.log_file, 'w') as f:
        json.dump([], f)

  def fetch_file_list(self):
    url = f"{self.base_url}/list?dir={self.config_dir}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()  # Ожидается список путей

  def download_file(self, path):
    print('download file', path)
    url = self.base_url + os.path.join(self.config_dir, path.lstrip('/'))
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.content

  def get_latest_backup_dir(self):
    backups = sorted(
      [d for d in os.listdir(self.backup_root)
       if os.path.isdir(os.path.join(self.backup_root, d)) and d != 'log.json'],
      reverse=True
    )
    if backups:
      return os.path.join(self.backup_root, backups[0])
    return None

  def file_hash(self, content):
    return hashlib.md5(content).hexdigest()

  def load_history(self):
    with open(self.log_file, 'r') as f:
      return json.load(f)

  def save_history_entry(self, timestamp, changed_files):
    history = self.load_history()
    history.append({
      'timestamp': timestamp,
      'changed_files': changed_files
    })
    with open(self.log_file, 'w') as f:
      json.dump(history, f, indent=2)

  def run_backup_if_changed(self):
    file_list = self.fetch_file_list()
    latest_backup_dir = self.get_latest_backup_dir()
    changes_detected = False
    current_files = {}
    changed_files = []

    for file_path in file_list:
      file_path = file_path.get('name')
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
      print(f"[ConfigVersionManager] ({self.device_id}) Изменения сохранены: {timestamp}")
    else:
      print(f"[ConfigVersionManager] ({self.device_id}) Изменений не обнаружено.")


class MyHomeClass(SingletonClass):
  type = 'myhome'
  connectors_list = {}
  _status: str = None
  _devices: dict[int, MyHomeDeviceClient] = {}  # device_id → клиент

  _save_config_hour = 1
  _save_logs_period = 2
  _save_logs_hour = 1
  _save_logs_minute = 1

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

    self.load_devices()

  def _save_logs_local(self, name, content, device_id, ip):
    logs_root = "../store/backup/logs"
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
      GoogleConnector().gsheet_add_row(self.sheet, '.'.join(name.split('.')[:-1]), data)
      return True
    except Exception as e:
      print(f"[Logs] Ошибка при сохранении в gsheet: {e}")
      return False

  def _save_logs(self):
    for device_id, device in self._devices.items():
      # print(device.__dict__)
      params = device.params

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
      print(f"[Logs] [local_save] Обработка логов с {device_id} ({ip})")

      try:
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

          file_path = f"/logs/{name}"
          file_url = f"{base_url}{file_path}"

          # Скачиваем лог
          log_resp = requests.get(file_url, timeout=5)
          log_resp.raise_for_status()
          content = log_resp.text

          if not method(name, content, device_id, ip):
            print('[Logs] Не удалось сохранить лог', name, device_id)
            return

            # Удаляем лог с устройства, если разрешено
          if params.get("remove_logs", True):
            delete_resp = requests.delete(
              f"{base_url}/edit", params={"path": file_path}, timeout=5
            )
            if delete_resp.status_code == 200:
              print(f"[Logs] {name} удалён с {device_id}")
            else:
              print(f"[Logs] Не удалось удалить {name} с {device_id}: {delete_resp.status_code}")

      except Exception as e:
        print(f"[Logs] Ошибка при обработке {device_id}: {e}")

  def _save_config(self):
    self.save_config_process = True
    for device_id, device in self._devices.items():
      params = device.params or {}
      if not params.get("backup_config"):
        continue

      base_url = f"http://{params.get('ip')}"
      print(f"[Configs] Обрабатываю device {device_id} по адресу {base_url}")

      try:
        ConfigVersionManager(
          base_url=base_url,
          device_id=device_id
        ).run_backup_if_changed()
      except Exception as e:
        print(f"[Configs] Ошибка при обработке {device_id}: {e}")
    self.save_config_process = False

  def _run_all(self):
    self._save_logs()
    self._save_config()

  def _run(self):
    if self.is_run:
      print("[my home] already running")
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

      print(f"[my home] Жду до {next_run.strftime('%Y-%m-%d %H:%M:%S')} ({int(wait_seconds)} сек)", action)
      if wait_seconds > 0:
        time.sleep(wait_seconds)

      if not self.stop_event.is_set():
        print(f"[my home] Выполняю задачу в {datetime.now().strftime('%H:%M:%S')}")
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
    print('MyHomeClass __del__')
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
      print('Сканирование уже выполняется')
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
    with db_session() as db:
      devices = db.query(DbDevices).all()
      for device in devices:
        self.add_device(device)
      print('[my home] Загружено устройств:', len(self._devices.keys()))

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
      print('[my home] add device', device['id'], device['name'])
      device_id = device['id']
    else:
      print('[my home] add device', device.id, device.name)
      device_id = device.id

    # Остановим старый клиент, если он есть
    old_client = self._devices.get(device_id)
    if old_client:
      try:
        asyncio.create_task(old_client.stop())
      except Exception:
        pass

    # Создаём клиента из ORM-объекта
    client = MyHomeDeviceClient.from_db_device(
      device,
      on_initial_ports=self._on_initial_ports,
      on_value=self._on_value,
      on_connect=lambda dev_id: log_print(f"[my home][{dev_id}] WS connected"),
      # on_disconnect=lambda dev_id: log_print(f"[my home][{dev_id}] WS disconnected"),
    )
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

  # === callbacks ===
  def _on_initial_ports(self, device_id: int, ports: list[dict]):
    """
    Регистрируем/обновляем порты в БД под устройством и синхронизируем runtime-модель.
    """
    print(f"[my home] _on_initial_ports for device {device_id}: {len(ports)} ports")
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
    # print(f"[my home] _on_value for device {device_id}: {event}")
    pass
    # code = event.get("code")
    # if not code:
    #   return
    # with db_session() as db:
    #   db_port = (
    #     db.query(DbPorts)
    #     .filter(DbPorts.device_id == device_id, DbPorts.code == code)
    #     .first()
    #   )
    #   if db_port:
    #     db_port.last_value = event.get("val")
    #     db.commit()
    #
    # # пуш в ваш WebSocket/UI
    # try:
    #   connection_manager.broadcast_json({
    #     "topic": "port_update",
    #     "device_id": device_id,
    #     "code": code,
    #     "val": event.get("val"),
    #     "direction": event.get("direction"),
    #     "kind": event.get("kind"),
    #   })
    # except Exception:
    #   pass


def add_routes(app: APIRouter, my_home: MyHomeClass):
  log_print('Adding MYHOME routes')

  @app.get("/api/live/scan",
           tags=["live"])
  async def scan_myhome():
    return await MyHomeClass().scan()

  @app.get("/api/live/{ip}/get_value",
           tags=["live"])
  async def get_myhome_value(ip: str):
    """
    Получить значение устройства по IP
    """
    async with aiohttp.ClientSession() as session:
      url = f"http://{ip}/values"
      async with session.get(url) as response:
        if response.status == 200:
          data = await response.text()
          try:
            data = json.loads(data)
          except json.JSONDecodeError as e:
            data = {"error": f"JSON decode error: {str(e)}", "raw_response": data}
        else:
          data = {"error": f"Error: {response.status}"}
        return data

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
      db_device.params.update({
        'ip': ip,
        'mac': info.get('mac'),
        'ssid': info.get('ssid'),
        'flash_date': info.get('flash_date'),
        'version': info.get('version'),
        'save_logs': any(el for el in values if el.get('title') == "LOGS")
      })
      db_device.type = info.get('flash_chip_revision')
      db.commit()
      db.refresh(db_device)
      db_device.on_create()

      my_home.add_device(db_device)

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

  @app.get("/api/live/devices", tags=["live"])
  async def get_devices():
    """
    Получить все устройства
    """
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
        print(e)
        continue

    return result

  @app.get("/api/live/ports", tags=["live"])
  async def get_ports():
    """
    Получить все порты всех устройств
    """
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
        continue

    return {"ports": result}
