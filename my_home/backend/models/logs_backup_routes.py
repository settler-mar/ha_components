"""
API routes для управления логами и бэкапами
"""
import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from db_models.devices import Devices
from utils.db_utils import db_session
from models.enhanced_logs import EnhancedLogsManager, LogsTable
from models.my_home import MyHomeClass, ConfigVersionManager
from utils.google_connector import GoogleConnector


def add_logs_backup_routes(app: APIRouter):
    """
    Добавляет маршруты для управления логами и бэкапами
    """
    
    @app.post("/api/devices/{device_id}/backup/trigger", tags=["backup"])
    async def trigger_manual_backup(device_id: int):
        """Запуск ручного бэкапа устройства"""
        try:
            from models.my_home import MyHomeClass
            my_home = MyHomeClass()
            
            # Получаем клиент устройства
            client = my_home.get_client(device_id)
            if not client:
                return {"success": False, "error": "Device not found"}
            
            # Получаем IP устройства
            device_ip = client.ip
            if not device_ip:
                return {"success": False, "error": "Device IP not configured"}
            
            # Запускаем бэкап
            from models.my_home import ConfigVersionManager
            config_manager = ConfigVersionManager(f"http://{device_ip}", device_id)
            result = config_manager.run_backup_if_changed()
            
            return {
                "success": True, 
                "message": "Backup triggered successfully",
                "changed_files": result.get("changed_files", 0),
                "has_changes": result.get("has_changes", False)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @app.post("/api/devices/{device_id}/backup/force", tags=["backup"])
    async def trigger_forced_backup(device_id: int):
        """Запуск форсированного бэкапа устройства (всех файлов)"""
        try:
            from models.my_home import MyHomeClass
            my_home = MyHomeClass()
            
            # Получаем клиент устройства
            client = my_home.get_client(device_id)
            if not client:
                return {"success": False, "error": "Device not found"}
            
            # Получаем IP устройства
            device_ip = client.ip
            if not device_ip:
                return {"success": False, "error": "Device IP not configured"}
            
            # Запускаем форсированный бэкап
            from models.my_home import ConfigVersionManager
            config_manager = ConfigVersionManager(f"http://{device_ip}", device_id)
            result = config_manager.run_forced_backup()
            
            return {
                "success": True, 
                "message": "Forced backup triggered successfully",
                "changed_files": result.get("changed_files", 0),
                "has_changes": True  # Форсированный бэкап всегда создает файлы
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @app.get("/api/devices/{device_id}/backup/history", tags=["backup"])
    async def get_backup_history(device_id: int):
        """Получение истории бэкапов устройства"""
        try:
            from models.my_home import ConfigVersionManager
            import os
            
            backup_root = f"../data/backup/{device_id}"
            log_file = os.path.join(backup_root, 'backup.log')
            
            if not os.path.exists(log_file):
                return {"success": True, "history": []}
            
            config_manager = ConfigVersionManager("", device_id)  # IP не нужен для чтения
            history = config_manager.load_history()
            
            return {"success": True, "history": history}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @app.post("/api/devices/{device_id}/logs/export", tags=["logs"])
    async def trigger_manual_logs_export(device_id: int):
        """Запуск ручного экспорта логов устройства"""
        try:
            from models.my_home import MyHomeClass
            my_home = MyHomeClass()
            
            # Получаем клиент устройства
            client = my_home.get_client(device_id)
            if not client:
                return {"success": False, "error": "Device not found"}
            
            # Получаем IP устройства
            device_ip = client.ip
            if not device_ip:
                return {"success": False, "error": "Device IP not configured"}
            
            # Запускаем экспорт логов для этого устройства
            my_home._save_logs_for_device(device_id, device_ip)
            
            return {"success": True, "message": "Logs export triggered successfully"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @app.get("/api/devices/{device_id}/logs/files", tags=["logs"])
    async def get_log_files(device_id: int):
        """Получение списка физических файлов логов"""
        try:
            import os
            
            logs_root = f"../store/backup/logs/{device_id}"
            if not os.path.exists(logs_root):
                return {"success": True, "files": []}
            
            files = []
            for filename in os.listdir(logs_root):
                if filename.endswith('.txt'):
                    filepath = os.path.join(logs_root, filename)
                    if os.path.isfile(filepath):
                        size = os.path.getsize(filepath)
                        modified = os.path.getmtime(filepath)
                        files.append({
                            "name": filename,
                            "size": size,
                            "modified": modified
                        })
            
            # Сортируем по времени изменения (новые первыми)
            files.sort(key=lambda x: x['modified'], reverse=True)
            
            return {"success": True, "files": files}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @app.get("/api/devices/{device_id}/logs/download/{filename}", tags=["logs"])
    async def download_log_file(device_id: int, filename: str):
        """Скачивание файла логов"""
        try:
            import os
            from fastapi.responses import FileResponse
            
            logs_root = f"../store/backup/logs/{device_id}"
            filepath = os.path.join(logs_root, filename)
            
            if not os.path.exists(filepath) or not filename.endswith('.txt'):
                raise HTTPException(status_code=404, detail="File not found")
            
            return FileResponse(
                filepath,
                media_type='text/plain',
                filename=filename
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/devices/{device_id}/logs/content/{filename}", tags=["logs"])
    async def get_log_file_content(device_id: int, filename: str):
        """Получение содержимого файла логов"""
        try:
            import os
            
            logs_root = f"../store/backup/logs/{device_id}"
            filepath = os.path.join(logs_root, filename)
            
            if not os.path.exists(filepath) or not filename.endswith('.txt'):
                raise HTTPException(status_code=404, detail="File not found")
            
            # Читаем файл с ограничением размера (для больших файлов)
            max_size = 1024 * 1024  # 1MB
            file_size = os.path.getsize(filepath)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                if file_size > max_size:
                    # Читаем только последние строки для больших файлов
                    f.seek(max(0, file_size - max_size))
                    content = f.read()
                    content = "...(файл обрезан)...\n" + content
                else:
                    content = f.read()
            
            return {"success": True, "content": content}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @app.get("/api/devices/{device_id}/backup/download", tags=["backup"])
    async def download_backup_log(device_id: int):
        """Скачивание файла backup.log"""
        try:
            import os
            from fastapi.responses import FileResponse
            
            backup_root = f"../data/backup/{device_id}"
            filepath = os.path.join(backup_root, 'backup.log')
            
            if not os.path.exists(filepath):
                raise HTTPException(status_code=404, detail="Backup log file not found")
            
            return FileResponse(
                filepath,
                media_type='text/plain',
                filename='backup.log'
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/devices/{device_id}/backup/content", tags=["backup"])
    async def get_backup_log_content(device_id: int):
        """Получение содержимого файла backup.log"""
        try:
            import os
            
            backup_root = f"../data/backup/{device_id}"
            filepath = os.path.join(backup_root, 'backup.log')
            
            if not os.path.exists(filepath):
                return {"success": True, "content": "Файл backup.log не найден"}
            
            # Читаем файл
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                content = "Файл backup.log пуст"
            
            return {"success": True, "content": content}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @app.get("/api/devices/{device_id}/config/files", tags=["config"])
    async def get_config_files(device_id: int):
        """Получение списка конфигурационных файлов с количеством версий"""
        try:
            import os
            
            backup_root = f"../data/backup/{device_id}"
            if not os.path.exists(backup_root):
                return {"success": True, "files": []}
            
            files_info = {}
            
            # Проходим по всем папкам бэкапов
            for backup_dir in os.listdir(backup_root):
                backup_path = os.path.join(backup_root, backup_dir)
                if not os.path.isdir(backup_path) or backup_dir in ['backup.log']:
                    continue
                
                # Проходим по файлам в папке бэкапа
                for filename in os.listdir(backup_path):
                    filepath = os.path.join(backup_path, filename)
                    if os.path.isfile(filepath):
                        if filename not in files_info:
                            files_info[filename] = {
                                "name": filename,
                                "versions": 0,
                                "latest_backup": backup_dir
                            }
                        files_info[filename]["versions"] += 1
                        
                        # Обновляем последний бэкап (по имени папки - дата)
                        if backup_dir > files_info[filename]["latest_backup"]:
                            files_info[filename]["latest_backup"] = backup_dir
            
            files_list = list(files_info.values())
            files_list.sort(key=lambda x: x["name"])
            
            return {"success": True, "files": files_list}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @app.get("/api/devices/{device_id}/config/history/{filename}", tags=["config"])
    async def get_config_file_history(device_id: int, filename: str):
        """Получение истории версий конфигурационного файла"""
        try:
            import os
            
            backup_root = f"../data/backup/{device_id}"
            if not os.path.exists(backup_root):
                return {"success": True, "versions": []}
            
            versions = []
            
            # Проходим по всем папкам бэкапов
            for backup_dir in os.listdir(backup_root):
                backup_path = os.path.join(backup_root, backup_dir)
                if not os.path.isdir(backup_path):
                    continue
                
                filepath = os.path.join(backup_path, filename)
                if os.path.exists(filepath):
                    size = os.path.getsize(filepath)
                    versions.append({
                        "timestamp": backup_dir,
                        "size": size,
                        "path": filepath
                    })
            
            # Сортируем по времени (новые первыми)
            versions.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return {"success": True, "versions": versions}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @app.get("/api/devices/{device_id}/config/content/{filename}", tags=["config"])
    async def get_config_file_content(device_id: int, filename: str):
        """Получение содержимого последней версии файла"""
        try:
            import os
            
            backup_root = f"../data/backup/{device_id}"
            if not os.path.exists(backup_root):
                return {"success": False, "error": "Backup directory not found"}
            
            # Находим последнюю версию файла
            latest_version = None
            latest_timestamp = ""
            
            for backup_dir in os.listdir(backup_root):
                backup_path = os.path.join(backup_root, backup_dir)
                if not os.path.isdir(backup_path):
                    continue
                
                filepath = os.path.join(backup_path, filename)
                if os.path.exists(filepath) and backup_dir > latest_timestamp:
                    latest_timestamp = backup_dir
                    latest_version = filepath
            
            if not latest_version:
                return {"success": False, "error": "File not found"}
            
            with open(latest_version, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {"success": True, "content": content}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @app.get("/api/devices/{device_id}/config/version/{filename}/{timestamp}", tags=["config"])
    async def get_config_file_version(device_id: int, filename: str, timestamp: str):
        """Получение содержимого конкретной версии файла"""
        try:
            import os
            
            backup_root = f"../data/backup/{device_id}"
            filepath = os.path.join(backup_root, timestamp, filename)
            
            if not os.path.exists(filepath):
                return {"success": False, "error": "File version not found"}
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {"success": True, "content": content}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @app.get("/api/devices/{device_id}/config/download/{filename}", tags=["config"])
    async def download_latest_config_file(device_id: int, filename: str):
        """Скачивание последней версии конфигурационного файла"""
        try:
            import os
            from fastapi.responses import FileResponse
            
            backup_root = f"../data/backup/{device_id}"
            if not os.path.exists(backup_root):
                raise HTTPException(status_code=404, detail="Backup directory not found")
            
            # Находим последнюю версию файла
            latest_version = None
            latest_timestamp = ""
            
            for backup_dir in os.listdir(backup_root):
                backup_path = os.path.join(backup_root, backup_dir)
                if not os.path.isdir(backup_path):
                    continue
                
                filepath = os.path.join(backup_path, filename)
                if os.path.exists(filepath) and backup_dir > latest_timestamp:
                    latest_timestamp = backup_dir
                    latest_version = filepath
            
            if not latest_version:
                raise HTTPException(status_code=404, detail="File not found")
            
            return FileResponse(
                latest_version,
                media_type='text/plain',
                filename=filename
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/devices/{device_id}/config/download/{filename}/{timestamp}", tags=["config"])
    async def download_config_file_version(device_id: int, filename: str, timestamp: str):
        """Скачивание конкретной версии конфигурационного файла"""
        try:
            import os
            from fastapi.responses import FileResponse
            
            backup_root = f"../data/backup/{device_id}"
            filepath = os.path.join(backup_root, timestamp, filename)
            
            if not os.path.exists(filepath):
                raise HTTPException(status_code=404, detail="File version not found")
            
            return FileResponse(
                filepath,
                media_type='text/plain',
                filename=f"{filename}_{timestamp.replace(':', '_')}"
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/devices/{device_id}/logs/status", tags=["logs"])
    async def get_logs_status(device_id: int):
        """Получение статуса логов устройства"""
        try:
            with db_session() as db:
                device = db.query(Devices).filter(Devices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                # Информация о последней выгрузке логов
                last_export_info = None
                
                # Проверяем настройки Google Sheets
                params = device.params or {}
                gsheet_config = params.get('gsheet_logs', {})
                gsheet_enabled = gsheet_config.get('enabled', False)
                
                # Проверяем доступность GoogleConnector
                google_available = False
                try:
                    google_connector = GoogleConnector(False)
                    google_available = google_connector and google_connector.enabled
                except Exception:
                    pass
                
                # Получаем информацию о логах из таблицы БД
                logs_table = LogsTable(db)
                log_names = logs_table.get_log_names(device_id)
                total_logs = len(log_names)
                
                # Получаем последний лог из таблицы
                if total_logs > 0:
                    latest_logs = logs_table.get_logs(device_id, limit=1)
                    if latest_logs:
                        last_log_time = latest_logs[0]['timestamp']
                        if isinstance(last_log_time, str):
                            last_log_time = datetime.fromisoformat(last_log_time.replace('Z', '+00:00'))
                        last_export_info = {
                            'timestamp': last_log_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'logs_count': total_logs,
                            'log_names': log_names
                        }
                
                # Получаем информацию о локальных файлах логов
                logs_root = f"../store/backup/logs"
                local_logs_info = None
                if os.path.exists(logs_root):
                    try:
                        log_files = [f for f in os.listdir(logs_root) if f.endswith('.txt')]
                        if log_files:
                            log_files.sort(key=lambda x: os.path.getmtime(os.path.join(logs_root, x)), reverse=True)
                            last_file_time = datetime.fromtimestamp(
                                os.path.getmtime(os.path.join(logs_root, log_files[0]))
                            )
                            local_logs_info = {
                                'timestamp': last_file_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'files_count': len(log_files),
                                'latest_file': log_files[0]
                            }
                    except Exception:
                        pass
                
                return {
                    "success": True,
                    "device_id": device_id,
                    "device_name": device.name,
                    "last_export": last_export_info,
                    "local_logs": local_logs_info,
                    "gsheet_config": {
                        "enabled": gsheet_enabled,
                        "sheet_id": gsheet_config.get('sheet_id'),
                        "worksheet_name": gsheet_config.get('worksheet_name', 'Logs')
                    },
                    "google_available": google_available,
                    "total_logs_in_db": total_logs,
                    "log_names": log_names
                }
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting logs status: {str(e)}")
    
    @app.post("/api/devices/{device_id}/logs/export", tags=["logs"])
    async def manual_logs_export(device_id: int, background_tasks: BackgroundTasks):
        """Ручной запуск экспорта логов"""
        try:
            with db_session() as db:
                device = db.query(Devices).filter(Devices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                params = device.params or {}
                ip = params.get('ip')
                if not ip:
                    raise HTTPException(status_code=400, detail="Device IP not found")
            
            # Запускаем экспорт логов в фоне
            background_tasks.add_task(export_device_logs, device_id, ip)
            
            return {
                "success": True,
                "message": "Экспорт логов запущен",
                "device_id": device_id
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error starting logs export: {str(e)}")
    
    @app.get("/api/devices/{device_id}/logs/history", tags=["logs"])
    async def get_logs_history(device_id: int, limit: int = 50, log_name: str = None):
        """Получение истории логов из БД"""
        try:
            with db_session() as db:
                device = db.query(Devices).filter(Devices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                logs_table = LogsTable(db)
                logs = logs_table.get_logs(device_id, log_name, limit)
                
                return {
                    "success": True,
                    "device_id": device_id,
                    "device_name": device.name,
                    "logs": logs,
                    "total_count": len(logs),
                    "filter_log_name": log_name
                }
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting logs history: {str(e)}")
    
    @app.get("/api/system/backup/status", tags=["backup"])
    async def get_system_backup_status():
        """Получение статуса системных бэкапов (Home Assistant делает бэкап всего проекта)"""
        try:
            # В Home Assistant бэкапы делаются на уровне всего addon'а, не отдельных устройств
            # Здесь мы показываем информацию о конфигурационных бэкапах устройств
            
            device_backups = []
            backup_base = "../data/backup"
            
            if os.path.exists(backup_base):
                try:
                    for device_dir in os.listdir(backup_base):
                        device_path = os.path.join(backup_base, device_dir)
                        if not os.path.isdir(device_path):
                            continue
                        
                        try:
                            device_id = int(device_dir)
                        except ValueError:
                            continue
                        
                        # Получаем информацию об устройстве
                        with db_session() as db:
                            device = db.query(Devices).filter(Devices.id == device_id).first()
                            device_name = device.name if device else f"Device {device_id}"
                        
                        # Получаем список бэкапов устройства
                        backup_dirs = [d for d in os.listdir(device_path) 
                                     if os.path.isdir(os.path.join(device_path, d)) and d != 'log.json']
                        backup_dirs.sort(reverse=True)
                        
                        if backup_dirs:
                            latest_backup = backup_dirs[0]
                            latest_backup_path = os.path.join(device_path, latest_backup)
                            backup_time = datetime.fromtimestamp(os.path.getctime(latest_backup_path))
                            
                            # Подсчитываем размер бэкапа
                            total_size = 0
                            files_count = 0
                            for root, dirs, files in os.walk(latest_backup_path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    total_size += os.path.getsize(file_path)
                                    files_count += 1
                            
                            device_backups.append({
                                'device_id': device_id,
                                'device_name': device_name,
                                'latest_backup': latest_backup,
                                'backup_time': backup_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'total_backups': len(backup_dirs),
                                'files_count': files_count,
                                'total_size': total_size
                            })
                
                except Exception as e:
                    print(f"Error reading backup directories: {e}")
            
            return {
                "success": True,
                "backup_type": "Home Assistant Addon Backup",
                "description": "В Home Assistant бэкапы создаются для всего addon'а через интерфейс HA",
                "device_config_backups": device_backups,
                "backup_base_path": backup_base,
                "ha_backup_info": {
                    "note": "Системные бэкапы addon'а создаются через Home Assistant",
                    "location": "Настройки > Система > Бэкапы > Создать бэкап",
                    "includes": ["Код приложения", "Конфигурация", "Данные устройств", "Логи"]
                }
            }
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting system backup status: {str(e)}")
    
    @app.get("/api/devices/{device_id}/config-backup/status", tags=["backup"])
    async def get_device_config_backup_status(device_id: int):
        """Получение статуса бэкапов конфигурации конкретного устройства"""
        try:
            with db_session() as db:
                device = db.query(Devices).filter(Devices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                # Получаем информацию о бэкапах конфигурации устройства
                backup_root = f"../data/backup/{device_id}"
                backups_info = []
                
                if os.path.exists(backup_root):
                    try:
                        # Получаем список папок бэкапов
                        backup_dirs = [d for d in os.listdir(backup_root) 
                                     if os.path.isdir(os.path.join(backup_root, d)) and d != 'log.json']
                        backup_dirs.sort(reverse=True)  # Сортируем по убыванию (новые сначала)
                        
                        for backup_dir in backup_dirs:
                            backup_path = os.path.join(backup_root, backup_dir)
                            
                            # Получаем информацию о содержимом бэкапа
                            files = []
                            total_size = 0
                            
                            for root, dirs, filenames in os.walk(backup_path):
                                for filename in filenames:
                                    file_path = os.path.join(root, filename)
                                    rel_path = os.path.relpath(file_path, backup_path)
                                    file_size = os.path.getsize(file_path)
                                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                    
                                    files.append({
                                        'name': rel_path,
                                        'size': file_size,
                                        'modified': file_time.strftime('%Y-%m-%d %H:%M:%S')
                                    })
                                    total_size += file_size
                            
                            # Время создания бэкапа
                            backup_time = datetime.fromtimestamp(os.path.getctime(backup_path))
                            
                            backups_info.append({
                                'name': backup_dir,
                                'timestamp': backup_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'files_count': len(files),
                                'total_size': total_size,
                                'files': files
                            })
                            
                    except Exception as e:
                        print(f"Error reading backup directory: {e}")
                
                # Читаем лог изменений
                log_file = os.path.join(backup_root, 'log.json')
                changes_history = []
                if os.path.exists(log_file):
                    try:
                        with open(log_file, 'r') as f:
                            changes_history = json.load(f)
                    except Exception as e:
                        print(f"Error reading log file: {e}")
                
                return {
                    "success": True,
                    "device_id": device_id,
                    "device_name": device.name,
                    "backup_type": "Device Configuration Backup",
                    "description": "Бэкап конфигурационных файлов устройства",
                    "backups": backups_info,
                    "changes_history": changes_history,
                    "backup_root": backup_root
                }
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting device config backup status: {str(e)}")
    
    @app.post("/api/devices/{device_id}/config-backup/create", tags=["backup"])
    async def manual_device_config_backup_create(device_id: int, background_tasks: BackgroundTasks):
        """Ручное создание бэкапа конфигурации устройства"""
        try:
            with db_session() as db:
                device = db.query(Devices).filter(Devices.id == device_id).first()
                if not device:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                params = device.params or {}
                ip = params.get('ip')
                if not ip:
                    raise HTTPException(status_code=400, detail="Device IP not found")
                
                backup_enabled = params.get('backup_config', False)
                if not backup_enabled:
                    raise HTTPException(status_code=400, detail="Config backup not enabled for this device")
            
            # Запускаем создание бэкапа конфигурации в фоне
            background_tasks.add_task(create_device_config_backup, device_id, ip)
            
            return {
                "success": True,
                "message": "Создание бэкапа конфигурации устройства запущено",
                "device_id": device_id,
                "backup_type": "Device Configuration"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error starting config backup creation: {str(e)}")


async def export_device_logs(device_id: int, ip: str):
    """Фоновая задача для экспорта логов устройства"""
    try:
        # Получаем экземпляр MyHomeClass
        my_home = MyHomeClass()
        
        # Запускаем сохранение логов для конкретного устройства
        await asyncio.get_event_loop().run_in_executor(
            None, 
            my_home.save_logs_for_device, 
            device_id, 
            ip
        )
        
        print(f"[LogsExport] Manual export completed for device {device_id}")
        
    except Exception as e:
        print(f"[LogsExport] Error exporting logs for device {device_id}: {e}")


async def create_device_config_backup(device_id: int, ip: str):
    """Фоновая задача для создания бэкапа конфигурации устройства"""
    try:
        # Создаем ConfigVersionManager для устройства
        base_url = f"http://{ip}"
        config_manager = ConfigVersionManager(base_url, device_id)
        
        # Запускаем создание бэкапа конфигурации
        await asyncio.get_event_loop().run_in_executor(
            None,
            config_manager.run_backup_if_changed
        )
        
        print(f"[ConfigBackup] Manual config backup completed for device {device_id}")
        
        # Уведомляем через WebSocket о завершении
        try:
            from utils.socket_utils import connection_manager
            connection_manager.broadcast_log(
                text=f"Бэкап конфигурации устройства {device_id} создан",
                level="info",
                device_id=device_id,
                class_name="ConfigBackup",
                action="backup_completed"
            )
        except Exception:
            pass
        
    except Exception as e:
        print(f"[ConfigBackup] Error creating config backup for device {device_id}: {e}")
        
        # Уведомляем об ошибке через WebSocket
        try:
            from utils.socket_utils import connection_manager
            connection_manager.broadcast_log(
                text=f"Ошибка создания бэкапа конфигурации устройства {device_id}: {str(e)}",
                level="error",
                device_id=device_id,
                class_name="ConfigBackup",
                action="backup_error",
                value=str(e)
            )
        except Exception:
            pass
