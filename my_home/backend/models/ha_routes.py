"""
API маршруты для интеграции с Home Assistant
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from pydantic import BaseModel
from db_models.devices import Devices
from db_models.ports import Ports
from utils.db_utils import db_session
from utils.configs import config
from utils.home_assistant import ha_websocket
from utils.ha_manager import ha_manager
import os
import json
import aiohttp
from datetime import datetime


class PortParameters(BaseModel):
    entity_id: str = ""
    name: str = ""
    friendly_name: str = ""
    device_class: str = ""
    unit_of_measurement: str = ""
    icon: str = ""
    state_class: str = ""
    entity_category: str = ""
    enabled_by_default: str = "true"
    force_update: str = "false"
    suggested_display_precision: str = ""
    attributes: Dict[str, Any] = {}


class PortChange(BaseModel):
    deviceId: int
    portCode: str
    action: str  # 'add' or 'remove'
    parameters: PortParameters


class SaveChangesRequest(BaseModel):
    changes: List[PortChange]
    selectedPorts: List[str]


def add_ha_routes(app: APIRouter):
  """Добавление маршрутов для интеграции с Home Assistant"""

  @app.get("/api/ha/test-connection", tags=["home-assistant"])
  async def test_ha_connection():
    """Тестирование подключения к Home Assistant"""
    try:
      # Проверяем подключение через HA Manager
      status = ha_manager.get_status()
      connected = status.get('ha_client_status', {}).get('connected', False)
      return {
        "connected": connected,
        "message": "Connected to Home Assistant" if connected else "Failed to connect to Home Assistant",
        "status": status
      }
    except Exception as e:
      return {
        "connected": False,
        "error": str(e)
      }

  @app.get("/api/ha/status", tags=["home-assistant"])
  async def get_ha_status():
    """Получение статуса HA Manager"""
    try:
      status = ha_manager.get_status()
      return {
        "success": True,
        "status": status
      }
    except Exception as e:
      return {
        "success": False,
        "error": str(e)
      }

  @app.post("/api/ha/sync", tags=["home-assistant"])
  async def sync_ha_ports():
    """Принудительная синхронизация портов с HA"""
    try:
      result = await ha_manager.force_sync()
      return result
    except Exception as e:
      return {
        "success": False,
        "error": str(e)
      }

  @app.post("/api/ha/auto-sync", tags=["home-assistant"])
  async def toggle_auto_sync(enabled: bool):
    """Включение/выключение автосинхронизации"""
    try:
      await ha_manager.enable_auto_sync(enabled)
      return {
        "success": True,
        "auto_sync_enabled": enabled,
        "message": f"Auto sync {'enabled' if enabled else 'disabled'}"
      }
    except Exception as e:
      return {
        "success": False,
        "error": str(e)
      }

  @app.get("/api/ha/cache-status", tags=["home-assistant"])
  async def get_cache_status():
    """Получение статуса кэша опубликованных портов"""
    try:
      status = ha_manager.get_cache_status()
      return {
        "success": True,
        "cache_status": status
      }
    except Exception as e:
      return {
        "success": False,
        "error": str(e)
      }

  @app.post("/api/ha/refresh-cache", tags=["home-assistant"])
  async def refresh_ports_cache():
    """Принудительное обновление кэша опубликованных портов"""
    try:
      await ha_manager._refresh_ports_cache(force_log=True)
      count = len(ha_manager._published_ports_cache)
      return {
        "success": True,
        "message": f"Cache refreshed successfully",
        "total_published_ports": count,
        "cache_timestamp": ha_manager._ports_cache_timestamp.isoformat() if ha_manager._ports_cache_timestamp else None
      }
    except Exception as e:
      return {
        "success": False,
        "error": str(e)
      }

  @app.get("/api/ha/all-ports", tags=["home-assistant"])
  async def get_all_ports():
    """Получение всех портов из базы данных (без фильтрации по публикации)"""
    try:
      all_ports = await ha_manager.get_all_ports_from_database()
      return {
        "success": True,
        "total_ports": len(all_ports),
        "ports": all_ports
      }
    except Exception as e:
      return {
        "success": False,
        "error": str(e)
      }

  @app.get("/api/ha/published-ports-count", tags=["home-assistant"])
  async def get_published_ports_count():
    """Получение количества опубликованных портов"""
    try:
      count = await ha_manager.get_published_ports_count()
      return {
        "success": True,
        "total_published_ports": count
      }
    except Exception as e:
      return {
        "success": False,
        "error": str(e)
      }

  @app.get("/api/ha/published-ports-summary", tags=["home-assistant"])
  async def get_published_ports_summary():
    """Получение сводки по опубликованным портам"""
    try:
      summary = await ha_manager.get_published_ports_summary()
      return {
        "success": True,
        "summary": summary
      }
    except Exception as e:
      return {
        "success": False,
        "error": str(e)
      }

  @app.get("/api/devices/{device_id}/ha-settings", tags=["home-assistant"])
  async def get_ha_settings(device_id: int):
    """Получение настроек интеграции с Home Assistant для устройства"""
    try:
      with db_session() as db:
        device = db.query(Devices).filter(Devices.id == device_id).first()
        if not device:
          raise HTTPException(status_code=404, detail="Device not found")

        # Получаем настройки из параметров устройства
        params = device.params if isinstance(device.params, dict) else {}
        ha_settings = params.get('ha_integration', {})

        return {
          "success": True,
          "enabled": ha_settings.get('enabled', False),
          "settings": {
            "entityPrefix": ha_settings.get('entityPrefix', device.name or 'device'),
            "publishDeviceOnline": ha_settings.get('publishDeviceOnline', True),
            "publishedPorts": ha_settings.get('publishedPorts', []),
            "publishedGroups": ha_settings.get('publishedGroups', [])
          }
        }
    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/devices/{device_id}/ha-settings", tags=["home-assistant"])
    async def save_ha_settings(device_id: int, settings_data: Dict[str, Any]):
        """Сохранение настроек интеграции с Home Assistant для устройства"""
        try:
            print(f"[HA-Settings] Received request for device {device_id}")
            print(f"[HA-Settings] Settings data: {settings_data}")
            
            with db_session() as db:
                device = db.query(Devices).filter(Devices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                print(f"[HA-Settings] Device found: {device.name}")
                
                # Получаем параметры устройства
                params = device.params if isinstance(device.params, dict) else {}
                
                # Получаем текущие настройки HA (сохраняем существующие данные)
                ha_settings = params.get('ha_integration', {})
                
                # Извлекаем данные из запроса
                incoming_settings = settings_data.get('settings', {})
                
                # Обновляем только те поля, которые пришли в запросе
                # Остальные поля сохраняем из существующих настроек
                if 'entityPrefix' in incoming_settings:
                    ha_settings['entityPrefix'] = incoming_settings['entityPrefix']
                elif 'entityPrefix' not in ha_settings:
                    # Устанавливаем значение по умолчанию только если его нет
                    ha_settings['entityPrefix'] = device.name or 'device'
                
                if 'publishDeviceOnline' in incoming_settings:
                    ha_settings['publishDeviceOnline'] = incoming_settings['publishDeviceOnline']
                elif 'publishDeviceOnline' not in ha_settings:
                    ha_settings['publishDeviceOnline'] = True
                
                # Эти поля всегда обновляем (даже если пустые массивы)
                ha_settings['publishedPorts'] = incoming_settings.get('publishedPorts', [])
                ha_settings['publishedGroups'] = incoming_settings.get('publishedGroups', [])
                
                # Сохраняем обновленные настройки
                params['ha_integration'] = ha_settings
                device.params = params
                
                print(f"[HA-Settings] Saving to DB:")
                print(f"  - publishedPorts: {ha_settings['publishedPorts']}")
                print(f"  - publishedGroups: {ha_settings['publishedGroups']}")
                print(f"  - entityPrefix: {ha_settings.get('entityPrefix')}")
                
                db.commit()
                db.refresh(device)
                
                print(f"[HA-Settings] Settings saved successfully")
                
                return {
                    "success": True,
                    "message": "Settings saved successfully",
                    "saved_settings": {
                        "publishedPorts": ha_settings['publishedPorts'],
                        "publishedGroups": ha_settings['publishedGroups'],
                        "entityPrefix": ha_settings.get('entityPrefix'),
                        "publishDeviceOnline": ha_settings.get('publishDeviceOnline')
                    }
                }
        except Exception as e:
            import traceback
            print(f"[HA-Settings] Error: {e}")
            print(f"[HA-Settings] Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))



  @app.get("/api/devices/{device_id}/backup-info", tags=["backup"])
  async def get_backup_info(device_id: int):
    """Получение информации о последних бэкапах и логах устройства"""
    try:
      with db_session() as db:
        device = db.query(Devices).filter(Devices.id == device_id).first()
        if not device:
          raise HTTPException(status_code=404, detail="Device not found")

        # Получаем информацию о последнем бэкапе
        backup_root = f"../data/backup/{device_id}"
        last_backup = None
        if os.path.exists(backup_root):
          try:
            backup_dirs = [d for d in os.listdir(backup_root)
                           if os.path.isdir(os.path.join(backup_root, d)) and d != 'log.json']
            if backup_dirs:
              backup_dirs.sort(reverse=True)
              last_backup = backup_dirs[0]
          except Exception:
            pass

        # Получаем информацию о последних логах
        logs_root = f"../store/backup/logs/{device_id}"
        last_logs = None
        if os.path.exists(logs_root):
          try:
            log_files = [f for f in os.listdir(logs_root) if f.endswith('.txt')]
            if log_files:
              log_files.sort(key=lambda x: os.path.getmtime(os.path.join(logs_root, x)), reverse=True)
              last_logs = datetime.fromtimestamp(
                os.path.getmtime(os.path.join(logs_root, log_files[0]))
              ).strftime('%Y-%m-%d %H:%M:%S')
          except Exception:
            pass

        params = device.params if isinstance(device.params, dict) else {}
        return {
          "success": True,
          "lastBackup": last_backup,
          "lastLogs": last_logs,
          "backupEnabled": params.get('backup_config', False),
          "logsEnabled": params.get('save_logs', False)
        }
    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

  @app.post("/api/devices/{device_id}/set-value", tags=["device-control"])
  async def set_device_value(device_id: int, value_data: Dict[str, Any]):
    """Установка значения порта устройства"""
    try:
      from models.my_home import MyHomeClass

      with db_session() as db:
        device = db.query(Devices).filter(Devices.id == device_id).first()
        if not device:
          raise HTTPException(status_code=404, detail="Device not found")

        code = value_data.get('code')
        value = value_data.get('value')

        if not code:
          raise HTTPException(status_code=400, detail="Port code is required")

        # Получаем клиент устройства
        my_home = MyHomeClass()
        client = my_home.get_client(device_id)

        if not client:
          raise HTTPException(status_code=404, detail="Device client not found")

        # Отправляем команду на устройство в формате ESP: "code#value"
        success = await send_command_to_device(client, code, value)

        if success:
          return {
            "success": True,
            "message": f"Value {value} set for port {code}",
            "code": code,
            "value": value
          }
        else:
          raise HTTPException(status_code=500, detail="Failed to send command to device")

    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

  @app.post("/api/ha/save-changes", tags=["home-assistant"])
  async def save_ha_changes(request_data: SaveChangesRequest):
    """Сохранение изменений портов в Home Assistant через hass-node-red интеграцию"""
    try:
      changes = request_data.changes
      selected_ports = request_data.selectedPorts
      
      if not changes:
        return {"success": False, "error": "No changes to save"}
      
      print(f"[HA-Save-Changes] Received {len(changes)} changes")
      print(f"[HA-Save-Changes] Selected ports: {selected_ports}")
      
      saved_count = 0
      errors = []
      
      for change in changes:
        try:
          device_id = change.deviceId
          port_code = change.portCode
          action = change.action  # 'add' or 'remove'
          parameters = change.parameters
          
          print(f"[HA-Save-Changes] Processing {action} for device {device_id}, port {port_code}")
          
          if action == 'add':
            # Создаем сущность в Home Assistant
            result = await create_ha_entity(device_id, port_code, parameters.dict())
            if result.get('success'):
              saved_count += 1
              print(f"[HA-Save-Changes] Successfully created entity for {port_code}")
            else:
              errors.append(f"Failed to create entity for {port_code}: {result.get('error')}")
              
          elif action == 'remove':
            # Удаляем сущность из Home Assistant
            result = await remove_ha_entity(device_id, port_code)
            if result.get('success'):
              saved_count += 1
              print(f"[HA-Save-Changes] Successfully removed entity for {port_code}")
            else:
              errors.append(f"Failed to remove entity for {port_code}: {result.get('error')}")
              
        except Exception as e:
          error_msg = f"Error processing {change.portCode}: {str(e)}"
          errors.append(error_msg)
          print(f"[HA-Save-Changes] {error_msg}")
      
      return {
        "success": True,
        "savedCount": saved_count,
        "totalChanges": len(changes),
        "errors": errors if errors else None
      }
      
    except Exception as e:
      print(f"[HA-Save-Changes] Error: {e}")
      raise HTTPException(status_code=500, detail=str(e))

  @app.post("/api/ha/update-state", tags=["home-assistant"])
  async def update_ha_state(device_id: int, port_code: str, state: str, attributes: Dict[str, Any] = None):
    """Обновление состояния сущности в Home Assistant"""
    try:
      result = await update_ha_entity_state(device_id, port_code, state, attributes)
      return result
    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

  @app.get("/api/ha/get-state", tags=["home-assistant"])
  async def get_ha_state(device_id: int, port_code: str):
    """Получение состояния сущности из Home Assistant"""
    try:
      result = await get_ha_entity_state(device_id, port_code)
      return result
    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

  @app.get("/api/ha/get-all-states", tags=["home-assistant"])
  async def get_all_ha_states_endpoint():
    """Получение всех состояний из Home Assistant"""
    try:
      result = await get_all_ha_states()
      return result
    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

  @app.post("/api/ha/sync-states", tags=["home-assistant"])
  async def sync_ha_states(device_id: int):
    """Синхронизация состояний Home Assistant с портами устройства"""
    try:
      from utils.configs import config
      
      # Синхронизируем с базой данных
      synced_count = await config.sync_with_database(device_id)
      
      return {
        "success": True,
        "synced_count": synced_count,
        "message": f"Synced {synced_count} ports from database"
      }
        
    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

  @app.get("/api/ha/config", tags=["home-assistant"])
  async def get_ha_config():
    """Получение конфигурации Home Assistant"""
    try:
      return {
        "url": config.get_ha_url(),
        "configured": config.is_ha_configured(),
        "timeout": config.get_ha_timeout(),
        "retry_attempts": config.get_ha_retry_attempts(),
        "log_requests": config.should_log_ha_requests(),
        "log_responses": config.should_log_ha_responses()
      }
    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

  @app.post("/api/ha/config", tags=["home-assistant"])
  async def update_ha_config(config_data: Dict[str, Any]):
    """Обновление конфигурации Home Assistant"""
    try:
      # Обновляем только разрешенные параметры
      allowed_keys = ['url', 'token', 'timeout', 'retry_attempts', 'log_requests', 'log_responses']
      
      for key, value in config_data.items():
        if key in allowed_keys:
          if key == 'url':
            config._config['homeassistant']['url'] = value
          elif key == 'token':
            config._config['homeassistant']['token'] = value
          elif key == 'timeout':
            config._config['homeassistant']['timeout'] = value
          elif key == 'retry_attempts':
            config._config['homeassistant']['retry_attempts'] = value
          elif key == 'log_requests':
            config._config['homeassistant']['log_requests'] = value
          elif key == 'log_responses':
            config._config['homeassistant']['log_responses'] = value
      
      # Сохраняем изменения
      config.save_yaml()
      
      # Переподключаемся к WebSocket если изменился URL или токен
      if 'url' in config_data or 'token' in config_data:
        await ha_websocket.disconnect()
        await ha_websocket.connect()
      
      return {"success": True, "message": "Configuration updated"}
    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

  @app.get("/api/ha/websocket-status", tags=["home-assistant"])
  async def get_websocket_status():
    """Получение статуса WebSocket подключения"""
    try:
      return {
        "connected": ha_websocket.connected,
        "authenticated": ha_websocket.authenticated,
        "reconnect_attempts": ha_websocket.reconnect_attempts
      }
    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

  @app.post("/api/ha/websocket-reconnect", tags=["home-assistant"])
  async def reconnect_websocket():
    """Принудительное переподключение WebSocket"""
    try:
      await ha_websocket.disconnect()
      success = await ha_websocket.connect()
      return {"success": success, "message": "WebSocket reconnected" if success else "Failed to reconnect"}
    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

  @app.post("/api/ha/ping", tags=["home-assistant"])
  async def ping_ha():
    """Проверка соединения с Home Assistant"""
    try:
      if not await ensure_websocket_connection():
        return {"success": False, "error": "Failed to connect to Home Assistant"}
      
      success = await ha_websocket.ping()
      return {"success": success, "message": "Ping successful" if success else "Ping failed"}
    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

  @app.post("/api/ha/toggle-config", tags=["home-assistant"])
  async def toggle_ha_config(enabled: bool):
    """Переключение режима настройки HA"""
    try:
      # Этот endpoint используется для переключения режима настройки HA
      # В реальности это может быть глобальная настройка или настройка соединения
      return {"success": True, "enabled": enabled}
    except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))


async def send_command_to_device(client, code: str, value) -> bool:
  """
  Отправляет команду на устройство в формате ESP: "code#value"
  """
  try:
    # Проверяем что клиент онлайн
    if not hasattr(client, '_ws') or not client._ws:
      print(f"[DeviceControl] Device {client.device_id} WebSocket not connected")
      return False

    # Формируем команду в формате ESP
    command = f"{code}#{value}"

    # Отправляем через WebSocket клиента устройства
    await client._ws.send_str(command)

    print(f"[DeviceControl] Command sent to device {client.device_id}: {command}")
    return True

  except Exception as e:
    print(f"[DeviceControl] Error sending command to device {client.device_id}: {e}")
    return False


async def create_ha_entity(device_id: int, port_code: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
  """
  Создает сущность в Home Assistant через hass-node-red интеграцию
  """
  try:
    # Получаем информацию об устройстве
    with db_session() as db:
      device = db.query(Devices).filter(Devices.id == device_id).first()
      if not device:
        return {"success": False, "error": f"Device {device_id} not found"}
      
      # Получаем настройки HA интеграции
      params = device.params if isinstance(device.params, dict) else {}
      ha_settings = params.get('ha_integration', {})
      entity_prefix = ha_settings.get('entityPrefix', device.name or 'device')
      
      # Определяем тип сущности на основе параметров
      device_class = parameters.get('device_class', '')
      unit_of_measurement = parameters.get('unit_of_measurement', '')
      
      # Определяем тип сущности для формирования правильного entity_id
      entity_type = determine_entity_type(device_class, unit_of_measurement, port_code)
      
      # Формируем entity_id в правильном формате: domain.entity_id
      if parameters.get('entity_id'):
        # Если entity_id указан явно, используем его с доменом
        entity_id_raw = parameters.get('entity_id')
        # Убираем домен если он уже есть
        if '.' in entity_id_raw:
          entity_id_raw = entity_id_raw.split('.', 1)[1]
        # Формируем полный entity_id с доменом
        entity_id = f"{entity_type}.{entity_prefix}_{entity_id_raw}"
      else:
        # Формируем entity_id автоматически
        clean_port_code = port_code.replace('.', '_').replace('-', '_').replace(':', '_')
        entity_id = f"{entity_type}.{entity_prefix}_{clean_port_code}"
      
      # Формируем конфигурацию сущности
      entity_config = {
        "entity_id": entity_id,
        "name": parameters.get('name', port_code),
        "device_class": device_class if device_class else None,
        "unit_of_measurement": unit_of_measurement if unit_of_measurement else None,
        "icon": parameters.get('icon') or None,
        "state_class": parameters.get('state_class') or None,
        "entity_category": parameters.get('entity_category') or None,
        "enabled_by_default": parameters.get('enabled_by_default', 'true') == 'true',
        "force_update": parameters.get('force_update', 'false') == 'true',
        "suggested_display_precision": parameters.get('suggested_display_precision') or None,
        "attributes": parameters.get('attributes', {})
      }
      
      # Убираем None значения
      entity_config = {k: v for k, v in entity_config.items() if v is not None}
      
      print(f"[HA-Create-Entity] Creating {entity_type} entity: {entity_id}")
      print(f"[HA-Create-Entity] Config: {json.dumps(entity_config, indent=2)}")
      
      # Формируем конфигурацию сущности для Home Assistant REST API
      # Важно: entity_id передается в URL, а не в теле запроса
      # friendly_name имеет приоритет над name
      friendly_name = parameters.get('friendly_name') or parameters.get('name') or port_code
      entity_state = {
        "state": "unknown",  # Начальное состояние
        "attributes": {
          "friendly_name": friendly_name
        }
      }

      # Добавляем опциональные атрибуты только если они заданы
      if device_class:
        entity_state["attributes"]["device_class"] = device_class
      if unit_of_measurement:
        entity_state["attributes"]["unit_of_measurement"] = unit_of_measurement
      if parameters.get('icon'):
        entity_state["attributes"]["icon"] = parameters.get('icon')
      if parameters.get('state_class'):
        entity_state["attributes"]["state_class"] = parameters.get('state_class')
      if parameters.get('entity_category'):
        entity_state["attributes"]["entity_category"] = parameters.get('entity_category')
      
      # Добавляем boolean атрибуты
      if parameters.get('enabled_by_default', 'true') == 'true':
        entity_state["attributes"]["enabled_by_default"] = True
      if parameters.get('force_update', 'false') == 'true':
        entity_state["attributes"]["force_update"] = True
      if parameters.get('suggested_display_precision'):
        entity_state["attributes"]["suggested_display_precision"] = int(parameters.get('suggested_display_precision'))

      # Добавляем дополнительные атрибуты
      if parameters.get('attributes'):
        entity_state["attributes"].update(parameters.get('attributes', {}))

    # Сохраняем данные порта в базу данных
    await save_port_data_to_db(device_id, port_code, parameters, entity_id)
    
    # Добавляем порт в AppConfig
    from utils.configs import config
    await config.add_published_port(device_id, port_code, entity_id)
    
    # Создаем сущность через REST API
    result = await create_entity_via_rest(entity_id, entity_state)
    
    if result.get('success'):
      # Обновляем настройки устройства - добавляем порт в publishedPorts
      published_ports = ha_settings.get('publishedPorts', [])
      if port_code not in published_ports:
        published_ports.append(port_code)
        ha_settings['publishedPorts'] = published_ports
        params['ha_integration'] = ha_settings
        device.params = params
        db.commit()
        print(f"[HA-Create-Entity] Added {port_code} to publishedPorts")
    
    return result
      
  except Exception as e:
    print(f"[HA-Create-Entity] Error creating entity for {port_code}: {e}")
    return {"success": False, "error": str(e)}


async def remove_ha_entity(device_id: int, port_code: str) -> Dict[str, Any]:
  """
  Удаляет сущность из Home Assistant через hass-node-red интеграцию
  """
  try:
    # Получаем информацию об устройстве
    with db_session() as db:
      device = db.query(Devices).filter(Devices.id == device_id).first()
      if not device:
        return {"success": False, "error": f"Device {device_id} not found"}
      
      # Получаем настройки HA интеграции
      params = device.params if isinstance(device.params, dict) else {}
      ha_settings = params.get('ha_integration', {})
      entity_prefix = ha_settings.get('entityPrefix', device.name or 'device')
      
      # Формируем entity_id в правильном формате: domain.entity_id
      clean_port_code = port_code.replace('.', '_').replace('-', '_').replace(':', '_')
      # Определяем тип сущности (по умолчанию switch для удаления)
      entity_type = "switch"  # Можно улучшить, получая из настроек
      entity_id = f"{entity_type}.{entity_prefix}_{clean_port_code}"
      
      print(f"[HA-Remove-Entity] Removing entity: {entity_id}")
      
      # Удаляем сущность через REST API
      result = await remove_entity_via_rest(entity_id)
      
      if result.get('success'):
        # Обновляем настройки устройства - удаляем порт из publishedPorts
        published_ports = ha_settings.get('publishedPorts', [])
        if port_code in published_ports:
          published_ports.remove(port_code)
          ha_settings['publishedPorts'] = published_ports
          params['ha_integration'] = ha_settings
          device.params = params
        
        # Обновляем порт в БД - устанавливаем ha_published в False
        port = db.query(Ports).filter(Ports.device_id == device_id, Ports.code == port_code).first()
        if port:
          if port.params is None:
            port.params = {}
          port.params['ha_published'] = False
          port.params['ha_unpublished_at'] = datetime.now().isoformat()
          print(f"[HA-Remove-Entity] Updated port {port_code} in database: ha_published=False")
        
        db.commit()
        
        # Удаляем порт из AppConfig
        from utils.configs import config
        await config.remove_published_port(device_id, port_code)
      
      return result
      
  except Exception as e:
    print(f"[HA-Remove-Entity] Error removing entity for {port_code}: {e}")
    return {"success": False, "error": str(e)}


def determine_entity_type(device_class: str, unit_of_measurement: str, port_code: str) -> str:
  """
  Определяет тип сущности Home Assistant на основе параметров
  """
  # Сенсоры (sensors)
  if device_class in ['temperature', 'humidity', 'pressure', 'illuminance', 'power', 'energy', 'voltage', 'current']:
    return 'sensor'
  
  # Бинарные сенсоры
  if device_class in ['battery', 'connectivity', 'door', 'garage_door', 'window', 'lock', 'motion', 'occupancy', 'opening', 'presence', 'safety', 'smoke', 'sound', 'vibration']:
    return 'binary_sensor'
  
  # Переключатели
  if device_class in ['switch', 'outlet'] or 'switch' in port_code.lower():
    return 'switch'
  
  # Кнопки
  if device_class == 'button' or 'button' in port_code.lower():
    return 'button'
  
  # Числовые значения
  if device_class in ['number'] or unit_of_measurement in ['°C', '°F', '%', 'W', 'V', 'A', 'Hz', 'Pa', 'bar', 'psi', 'lux', 'dB']:
    return 'number'
  
  # Текстовые поля
  if device_class in ['text'] or 'text' in port_code.lower():
    return 'text'
  
  # Выбор
  if device_class in ['select'] or 'select' in port_code.lower():
    return 'select'
  
  # По умолчанию - сенсор
  return 'sensor'


async def ensure_websocket_connection() -> bool:
  """
  Обеспечивает подключение к Home Assistant WebSocket
  """
  try:
    if not ha_websocket.connected:
      print("[HA-WebSocket] Connecting to Home Assistant...")
      return await ha_websocket.connect()
    return True
  except Exception as e:
    print(f"[HA-WebSocket] Connection failed: {e}")
    return False


async def create_entity_via_rest(entity_id: str, entity_state: Dict[str, Any]) -> Dict[str, Any]:
  """
  Создает сущность в Home Assistant через REST API
  """
  try:
    # Получаем URL и токен из конфигурации
    ha_url = config.get_ha_url()
    token = config.get_ha_token()
    
    if not ha_url or not token:
      return {"success": False, "error": "Home Assistant not configured"}
    
    # Формируем URL для создания сущности
    api_url = f"{ha_url}/api/states/{entity_id}"
    
    # Заголовки для аутентификации
    headers = {
      "Authorization": f"Bearer {token}",
      "Content-Type": "application/json"
    }
    
    print(f"[HA-Create-Entity] Creating entity via REST: {entity_id}")
    print(f"[HA-Create-Entity] URL: {api_url}")
    print(f"[HA-Create-Entity] State: {json.dumps(entity_state, indent=2)}")
    
    # Отправляем POST запрос для создания сущности
    async with aiohttp.ClientSession() as session:
      async with session.post(api_url, headers=headers, json=entity_state) as response:
        if response.status == 200:
          result_data = await response.json()
          print(f"[HA-Create-Entity] Success: {result_data}")
          return {"success": True, "data": result_data}
        else:
          error_text = await response.text()
          print(f"[HA-Create-Entity] Error {response.status}: {error_text}")
          return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
          
  except Exception as e:
    print(f"[HA-Create-Entity] Exception: {e}")
    return {"success": False, "error": str(e)}


async def remove_entity_via_rest(entity_id: str) -> Dict[str, Any]:
  """
  Удаляет сущность из Home Assistant через REST API
  """
  try:
    # Получаем URL и токен из конфигурации
    ha_url = config.get_ha_url()
    token = config.get_ha_token()
    
    if not ha_url or not token:
      return {"success": False, "error": "Home Assistant not configured"}
    
    # Формируем URL для удаления сущности
    api_url = f"{ha_url}/api/states/{entity_id}"
    
    # Заголовки для аутентификации
    headers = {
      "Authorization": f"Bearer {token}",
      "Content-Type": "application/json"
    }
    
    print(f"[HA-Remove-Entity] Removing entity via REST: {entity_id}")
    print(f"[HA-Remove-Entity] URL: {api_url}")
    
    # Отправляем DELETE запрос для удаления сущности
    async with aiohttp.ClientSession() as session:
      async with session.delete(api_url, headers=headers) as response:
        if response.status == 200:
          result_data = await response.json()
          print(f"[HA-Remove-Entity] Success: {result_data}")
          return {"success": True, "data": result_data}
        elif response.status == 404:
          # Сущность уже не существует
          print(f"[HA-Remove-Entity] Entity {entity_id} not found (already removed)")
          return {"success": True, "message": "Entity not found (already removed)"}
        else:
          error_text = await response.text()
          print(f"[HA-Remove-Entity] Error {response.status}: {error_text}")
          return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
          
  except Exception as e:
    print(f"[HA-Remove-Entity] Exception: {e}")
    return {"success": False, "error": str(e)}




async def update_ha_entity_state(device_id: int, port_code: str, state: str, attributes: Dict[str, Any] = None) -> Dict[str, Any]:
  """
  Обновляет состояние сущности в Home Assistant
  """
  try:
    with db_session() as db:
      device = db.query(Devices).filter(Devices.id == device_id).first()
      if not device:
        return {"success": False, "error": f"Device {device_id} not found"}

      params = device.params if isinstance(device.params, dict) else {}
      ha_settings = params.get('ha_integration', {})
      entity_prefix = ha_settings.get('entityPrefix', device.name or 'device')
      
      # Формируем entity_id в правильном формате: domain.entity_id
      clean_port_code = port_code.replace('.', '_').replace('-', '_').replace(':', '_')
      # Определяем тип сущности (по умолчанию switch для обновления состояния)
      entity_type = "switch"  # Можно улучшить, получая из настроек
      entity_id = f"{entity_type}.{entity_prefix}_{clean_port_code}"
      
      # Формируем данные для обновления состояния
      state_data = {
        "state": state,
        "attributes": attributes or {}
      }
      
      print(f"[HA-Update-State] Updating {entity_id} to state: {state}")
      
      # Убеждаемся, что WebSocket подключен
      if not await ensure_websocket_connection():
        return {"success": False, "error": "Failed to connect to Home Assistant"}
      
      # Отправляем запрос на обновление состояния через WebSocket
      result = await ha_websocket.set_state(entity_id, state, attributes)
      
      return result
      
  except Exception as e:
    print(f"[HA-Update-State] Error updating state for {port_code}: {e}")
    return {"success": False, "error": str(e)}


async def get_ha_entity_state(device_id: int, port_code: str) -> Dict[str, Any]:
  """
  Получает текущее состояние сущности из Home Assistant
  """
  try:
    with db_session() as db:
      device = db.query(Devices).filter(Devices.id == device_id).first()
      if not device:
        return {"success": False, "error": f"Device {device_id} not found"}

      params = device.params if isinstance(device.params, dict) else {}
      ha_settings = params.get('ha_integration', {})
      entity_prefix = ha_settings.get('entityPrefix', device.name or 'device')
      
      # Формируем entity_id в правильном формате: domain.entity_id
      clean_port_code = port_code.replace('.', '_').replace('-', '_').replace(':', '_')
      # Определяем тип сущности (по умолчанию switch для получения состояния)
      entity_type = "switch"  # Можно улучшить, получая из настроек
      entity_id = f"{entity_type}.{entity_prefix}_{clean_port_code}"
      
      print(f"[HA-Get-State] Getting state for {entity_id}")
      
      # Убеждаемся, что WebSocket подключен
      if not await ensure_websocket_connection():
        return {"success": False, "error": "Failed to connect to Home Assistant"}
      
      # Отправляем запрос на получение состояния через WebSocket
      state = await ha_websocket.get_state(entity_id)
      if state:
        return {"success": True, "data": state}
      else:
        return {"success": False, "error": f"Entity {entity_id} not found"}
      
  except Exception as e:
    print(f"[HA-Get-State] Error getting state for {port_code}: {e}")
    return {"success": False, "error": str(e)}


async def get_all_ha_states() -> Dict[str, Any]:
  """
  Получает все состояния из Home Assistant
  """
  try:
    print(f"[HA-Get-All-States] Getting all states")
    
    # Убеждаемся, что WebSocket подключен
    if not await ensure_websocket_connection():
      return {"success": False, "error": "Failed to connect to Home Assistant"}
    
    # Отправляем запрос на получение всех состояний через WebSocket
    states = await ha_websocket.get_states()
    
    return {"success": True, "data": states}
    
  except Exception as e:
    print(f"[HA-Get-All-States] Error getting all states: {e}")
    return {"success": False, "error": str(e)}


async def save_port_data_to_db(device_id: int, port_code: str, parameters: Dict[str, Any], entity_id: str) -> bool:
  """
  Сохраняет данные порта в базу данных
  """
  try:
    from db_models.ports import Ports
    from db_models.devices import Devices
    from datetime import datetime
    
    with db_session() as db:
      # Проверяем, существует ли порт
      existing_port = db.query(Ports).filter(
        Ports.device_id == device_id,
        Ports.code == port_code
      ).first()
      
      if existing_port:
        # Обновляем существующий порт
        existing_port.name = parameters.get('friendly_name') or parameters.get('name', port_code)
        existing_port.label = parameters.get('name', port_code)
        existing_port.description = f"HA Entity: {entity_id}"
        existing_port.type = parameters.get('device_class', 'switch')
        existing_port.unit = parameters.get('unit_of_measurement', '')
        
        # Сохраняем дополнительные параметры HA
        ha_params = {
          'entity_id': entity_id,
          'device_class': parameters.get('device_class', ''),
          'unit_of_measurement': parameters.get('unit_of_measurement', ''),
          'icon': parameters.get('icon', ''),
          'state_class': parameters.get('state_class', ''),
          'entity_category': parameters.get('entity_category', ''),
          'enabled_by_default': parameters.get('enabled_by_default', 'true'),
          'force_update': parameters.get('force_update', 'false'),
          'suggested_display_precision': parameters.get('suggested_display_precision', ''),
          'attributes': parameters.get('attributes', {}),
          'ha_published': True,
          'ha_published_at': datetime.now().isoformat()
        }
        
        # Обновляем параметры порта
        if not existing_port.params:
          existing_port.params = {}
        existing_port.params.update(ha_params)
        
        db.commit()
        print(f"[HA-Save-Port] Updated port {port_code} in database")
        
      else:
        # Создаем новый порт
        new_port = Ports(
          device_id=device_id,
          code=port_code,
          name=parameters.get('friendly_name') or parameters.get('name', port_code),
          label=parameters.get('name', port_code),
          description=f"HA Entity: {entity_id}",
          type=parameters.get('device_class', 'switch'),
          unit=parameters.get('unit_of_measurement', ''),
          params={
            'entity_id': entity_id,
            'device_class': parameters.get('device_class', ''),
            'unit_of_measurement': parameters.get('unit_of_measurement', ''),
            'icon': parameters.get('icon', ''),
            'state_class': parameters.get('state_class', ''),
            'entity_category': parameters.get('entity_category', ''),
            'enabled_by_default': parameters.get('enabled_by_default', 'true'),
            'force_update': parameters.get('force_update', 'false'),
            'suggested_display_precision': parameters.get('suggested_display_precision', ''),
            'attributes': parameters.get('attributes', {}),
            'ha_published': True,
            'ha_published_at': datetime.now().isoformat()
          }
        )
        
        db.add(new_port)
        db.commit()
        print(f"[HA-Save-Port] Created new port {port_code} in database")
      
      return True
      
  except Exception as e:
    print(f"[HA-Save-Port] Error saving port {port_code} to database: {e}")
    return False


async def update_port_state_from_ha(device_id: int, port_code: str, ha_state: str) -> bool:
  """
  Обновляет состояние порта в нашей системе на основе состояния из HA
  """
  try:
    from models.my_home import MyHomeClass
    
    my_home = MyHomeClass()
    client = my_home.get_client(device_id)
    
    if not client:
      print(f"[HA-Sync] Device {device_id} client not found")
      return False
    
    # Определяем значение для порта на основе состояния HA
    if ha_state in ['on', 'ON', '1', 'true', 'True']:
      port_value = '1'
    elif ha_state in ['off', 'OFF', '0', 'false', 'False']:
      port_value = '0'
    else:
      port_value = str(ha_state)
    
    # Обновляем значение порта в клиенте устройства
    if hasattr(client, '_ports_index') and port_code in client._ports_index:
      client._ports_index[port_code]['val'] = port_value
      client._ports_index[port_code]['last_update'] = datetime.now().isoformat()
      
      # Обновляем в списке портов
      for port in client._ports:
        if port.get('code') == port_code:
          port['val'] = port_value
          port['last_update'] = datetime.now().isoformat()
          break
      
      print(f"[HA-Sync] Updated port {port_code} to value {port_value} from HA state {ha_state}")
      return True
    else:
      print(f"[HA-Sync] Port {port_code} not found in device {device_id}")
      return False
      
  except Exception as e:
    print(f"[HA-Sync] Error updating port {port_code} from HA state {ha_state}: {e}")
    return False
