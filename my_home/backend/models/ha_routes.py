"""
API маршруты для интеграции с Home Assistant
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import json
from db_models.devices import Devices
from db_models.ports import Ports
from utils.db_utils import db_session
from models.home_assistant_integration import data_publisher
import os
from datetime import datetime


def add_ha_routes(app: APIRouter):
    """Добавление маршрутов для интеграции с Home Assistant"""
    
    @app.get("/api/ha/test-connection", tags=["home-assistant"])
    async def test_ha_connection():
        """Тестирование подключения к Home Assistant"""
        try:
            connected = await data_publisher.initialize()
            return {
                "connected": connected,
                "message": "Connected to Home Assistant" if connected else "Failed to connect to Home Assistant"
            }
        except Exception as e:
            return {
                "connected": False,
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
                params = device.params or {}
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
    async def save_ha_settings(device_id: int, request: Request):
        """Сохранение настроек интеграции с Home Assistant для устройства"""
        try:
            # Парсим JSON из тела запроса
            body = await request.body()
            settings_data = json.loads(body.decode('utf-8'))
            
            with db_session() as db:
                device = db.query(Devices).filter(Devices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                # Обновляем параметры устройства
                params = device.params or {}
                ha_settings = params.get('ha_integration', {})
                
                # Новая структура данных
                ha_settings.update({
                    'entityPrefix': settings_data.get('settings', {}).get('entityPrefix', device.name or 'device'),
                    'publishDeviceOnline': settings_data.get('settings', {}).get('publishDeviceOnline', True),
                    'publishedPorts': settings_data.get('settings', {}).get('publishedPorts', []),
                    'publishedGroups': settings_data.get('settings', {}).get('publishedGroups', [])
                })
                
                params['ha_integration'] = ha_settings
                device.params = params
                db.commit()
                
                return {"success": True, "message": "Settings saved successfully"}
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/devices/{device_id}/publish-to-ha", tags=["home-assistant"])
    async def publish_device_to_ha(device_id: int):
        """Публикация данных устройства в Home Assistant"""
        try:
            with db_session() as db:
                device = db.query(Devices).filter(Devices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                # Получаем настройки интеграции
                params = device.params or {}
                ha_settings = params.get('ha_integration', {})
                
                if not ha_settings.get('enabled', False):
                    return {"success": False, "error": "Home Assistant integration is disabled"}
                
                # Получаем данные устройства (здесь нужно получить актуальные данные)
                # Пока используем заглушку
                device_values = []  # TODO: Получить реальные данные устройства
                
                result = await data_publisher.publish_device_data(
                    device_id=device_id,
                    values=device_values,
                    publish_level=ha_settings.get('publishLevel', 'all'),
                    selected_ports=ha_settings.get('selectedPorts', []),
                    selected_groups=ha_settings.get('selectedGroups', []),
                    prefix=ha_settings.get('entityPrefix', 'my_home')
                )
                
                return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/devices/{device_id}/ha-entities", tags=["home-assistant"])
    async def get_ha_entities(device_id: int):
        """Получение списка сущностей устройства в Home Assistant"""
        try:
            with db_session() as db:
                device = db.query(Devices).filter(Devices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                # Получаем настройки интеграции
                params = device.params or {}
                ha_settings = params.get('ha_integration', {})
                prefix = ha_settings.get('entityPrefix', 'my_home')
                
                entities = await data_publisher.get_published_entities(device_id, prefix)
                
                return {
                    "success": True,
                    "entities": entities,
                    "total": len(entities)
                }
        except Exception as e:
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
                
                return {
                    "success": True,
                    "lastBackup": last_backup,
                    "lastLogs": last_logs,
                    "backupEnabled": device.params.get('backup_config', False) if device.params else False,
                    "logsEnabled": device.params.get('save_logs', False) if device.params else False
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
