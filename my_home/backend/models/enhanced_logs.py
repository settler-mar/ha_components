"""
Улучшенная система сохранения логов с поддержкой таблиц и истории из Google Docs
"""
import os
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from db_models.devices import Devices
from utils.db_utils import db_session
from utils.google_connector import GoogleConnector


class LogEntry:
    """Запись лога"""
    
    def __init__(self, device_id: int, log_name: str, content: str, timestamp: datetime = None):
        self.device_id = device_id
        self.log_name = log_name
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.size = len(content.encode('utf-8'))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'device_id': self.device_id,
            'log_name': self.log_name,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'size': self.size
        }


class LogsTable:
    """Таблица для хранения логов в базе данных"""
    
    def __init__(self, db: Session):
        self.db = db
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Создание таблицы логов если не существует"""
        # Создаем таблицу логов
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS device_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            log_name VARCHAR(100) NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            size INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices (id)
        )
        """
        self.db.execute(create_table_sql)
        self.db.commit()
    
    def save_log(self, log_entry: LogEntry) -> int:
        """Сохранение лога в таблицу"""
        from sqlalchemy import text
        
        insert_sql = text("""
        INSERT INTO device_logs (device_id, log_name, content, timestamp, size)
        VALUES (:device_id, :log_name, :content, :timestamp, :size)
        """)
        
        result = self.db.execute(insert_sql, {
            'device_id': log_entry.device_id,
            'log_name': log_entry.log_name,
            'content': log_entry.content,
            'timestamp': log_entry.timestamp,
            'size': log_entry.size
        })
        
        self.db.commit()
        return result.lastrowid
    
    def get_logs(self, device_id: int, log_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Получение логов из таблицы"""
        from sqlalchemy import text
        
        if log_name:
            query = text("""
            SELECT * FROM device_logs 
            WHERE device_id = :device_id AND log_name = :log_name
            ORDER BY timestamp DESC 
            LIMIT :limit
            """)
            result = self.db.execute(query, {
                'device_id': device_id,
                'log_name': log_name,
                'limit': limit
            })
        else:
            query = text("""
            SELECT * FROM device_logs 
            WHERE device_id = :device_id
            ORDER BY timestamp DESC 
            LIMIT :limit
            """)
            result = self.db.execute(query, {
                'device_id': device_id,
                'limit': limit
            })
        
        return [dict(row._mapping) for row in result]
    
    def get_log_names(self, device_id: int) -> List[str]:
        """Получение списка имен логов для устройства"""
        from sqlalchemy import text
        
        query = text("""
        SELECT DISTINCT log_name FROM device_logs 
        WHERE device_id = :device_id
        ORDER BY log_name
        """)
        
        result = self.db.execute(query, {'device_id': device_id})
        return [row[0] for row in result]


class EnhancedLogsManager:
    """Улучшенный менеджер логов с поддержкой таблиц и Google Docs"""
    
    def __init__(self):
        try:
            self.google_connector = GoogleConnector(False)  # Не строгий режим
        except Exception as e:
            print(f"[EnhancedLogsManager] GoogleConnector недоступен: {e}")
            self.google_connector = None
        self.logs_tables = {}
    
    def _get_logs_table(self, db: Session) -> LogsTable:
        """Получение таблицы логов для сессии БД"""
        if id(db) not in self.logs_tables:
            self.logs_tables[id(db)] = LogsTable(db)
        return self.logs_tables[id(db)]
    
    async def save_logs_local(self, device_id: int, log_name: str, content: str, 
                            device_ip: str) -> bool:
        """Сохранение логов локально (файл + таблица + Google файл)"""
        try:
            from utils.socket_utils import connection_manager
            
            # Создаем запись лога
            log_entry = LogEntry(device_id, log_name, content)
            
            # Сохраняем в таблицу
            with db_session() as db:
                logs_table = self._get_logs_table(db)
                log_id = logs_table.save_log(log_entry)
                print(f"[Logs] Saved log {log_name} to table with ID {log_id}")
                
                # Логируем сохранение в таблицу
                connection_manager.broadcast_log(
                    text=f"Лог {log_name} сохранен в таблицу БД (ID: {log_id})",
                    level="info",
                    device_id=device_id,
                    class_name="EnhancedLogsManager",
                    action="log_saved_to_table",
                    value=log_name
                )
            
            # Сохраняем в обычный файл
            logs_root = "../store/backup/logs"
            device_dir = os.path.join(logs_root, str(device_id))
            os.makedirs(device_dir, exist_ok=True)
            
            log_file = os.path.join(device_dir, f"{log_name}.txt")
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Сохраняем в файл для Google таблиц (построчно)
            google_log_file = os.path.join(device_dir, f"{log_name}_google.log")
            with open(google_log_file, 'w', encoding='utf-8') as f:
                for line in content.split('\n'):
                    if line.strip():  # Пропускаем пустые строки
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        f.write(f"{timestamp}: {line.strip()}\n")
            
            print(f"[Logs] Saved log {log_name} to files: {log_file}, {google_log_file}")
            
            # Обновляем время экспорта логов в параметрах устройства
            self._update_device_logs_export_time(device_id, log_name)
            
            # Логируем сохранение в файлы
            connection_manager.broadcast_log(
                text=f"Лог {log_name} сохранен в файлы",
                level="info",
                device_id=device_id,
                class_name="EnhancedLogsManager",
                action="log_saved_to_files",
                value=log_name
            )
            
            return True
            
        except Exception as e:
            print(f"[Logs] Failed to save log locally: {e}")
            
            # Логируем ошибку сохранения
            from utils.socket_utils import connection_manager
            connection_manager.broadcast_log(
                text=f"Ошибка сохранения лога {log_name}: {str(e)}",
                level="error",
                device_id=device_id,
                class_name="EnhancedLogsManager",
                action="log_save_error",
                value=log_name
            )
            
            return False
    
    async def save_logs_gsheet(self, device_id: int, log_name: str, content: str, 
                             device_ip: str) -> bool:
        """Сохранение логов в Google Sheets с историей"""
        try:
            # Получаем настройки устройства
            with db_session() as db:
                device = db.query(Devices).filter(Devices.id == device_id).first()
                if not device:
                    return False
                
                params = device.params if isinstance(device.params, dict) else {}
                gsheet_config = params.get('gsheet_logs', {})
                
                if not gsheet_config.get('enabled', False):
                    return False
                
                sheet_id = gsheet_config.get('sheet_id')
                worksheet_name = gsheet_config.get('worksheet_name', 'Logs')
                
                if not sheet_id:
                    return False
            
            # Создаем запись лога
            log_entry = LogEntry(device_id, log_name, content)
            
            # Получаем историю из Google Sheets при первом сохранении
            if gsheet_config.get('load_history_on_first_save', True):
                await self._load_history_from_gsheet(device_id, sheet_id, worksheet_name)
            
            # Подготавливаем данные для записи
            log_data = {
                'device_id': device_id,
                'device_name': device.name,
                'log_name': log_name,
                'content': content,
                'timestamp': log_entry.timestamp.isoformat(),
                'size': log_entry.size,
                'device_ip': device_ip
            }
            
            # Записываем в Google Sheets
            success = await self.google_connector.append_to_sheet(
                sheet_id, worksheet_name, log_data
            )
            
            if success:
                print(f"[Logs] Saved log {log_name} to Google Sheets")
                
                # Логируем успешное сохранение в Google Sheets
                from utils.socket_utils import connection_manager
                connection_manager.broadcast_log(
                    text=f"Лог {log_name} сохранен в Google Sheets (ID: {sheet_id})",
                    level="info",
                    device_id=device_id,
                    class_name="EnhancedLogsManager",
                    action="log_saved_to_gsheet",
                    value=log_name
                )
                
                # Также сохраняем в таблицу
                with db_session() as db:
                    logs_table = self._get_logs_table(db)
                    logs_table.save_log(log_entry)
                return True
            else:
                print(f"[Logs] Failed to save log {log_name} to Google Sheets")
                
                # Логируем ошибку сохранения в Google Sheets
                from utils.socket_utils import connection_manager
                connection_manager.broadcast_log(
                    text=f"Не удалось сохранить лог {log_name} в Google Sheets",
                    level="error",
                    device_id=device_id,
                    class_name="EnhancedLogsManager",
                    action="log_gsheet_save_failed",
                    value=log_name
                )
                return False
                
        except Exception as e:
            print(f"[Logs] Failed to save log to Google Sheets: {e}")
            
            # Логируем ошибку сохранения в Google Sheets
            from utils.socket_utils import connection_manager
            connection_manager.broadcast_log(
                text=f"Ошибка сохранения лога {log_name} в Google Sheets: {str(e)}",
                level="error",
                device_id=device_id,
                class_name="EnhancedLogsManager",
                action="log_gsheet_save_error",
                value=log_name
            )
            return False
    
    async def _load_history_from_gsheet(self, device_id: int, sheet_id: str, 
                                      worksheet_name: str) -> bool:
        """Загрузка истории логов из Google Sheets при первом сохранении"""
        try:
            print(f"[Logs] Loading history from Google Sheets for device {device_id}")
            
            # Получаем данные из Google Sheets
            data = await self.google_connector.get_sheet_data(sheet_id, worksheet_name)
            if not data:
                return False
            
            # Обрабатываем данные и сохраняем в таблицу
            with db_session() as db:
                logs_table = self._get_logs_table(db)
                
                for row in data:
                    if len(row) >= 6:  # Минимальное количество колонок
                        try:
                            # Парсим данные из строки
                            timestamp_str = row[4] if len(row) > 4 else None
                            timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()
                            
                            log_entry = LogEntry(
                                device_id=device_id,
                                log_name=row[2] if len(row) > 2 else 'unknown',
                                content=row[3] if len(row) > 3 else '',
                                timestamp=timestamp
                            )
                            
                            logs_table.save_log(log_entry)
                            
                        except Exception as e:
                            print(f"[Logs] Failed to parse history row: {e}")
                            continue
            
            print(f"[Logs] Loaded {len(data)} history entries from Google Sheets")
            return True
            
        except Exception as e:
            print(f"[Logs] Failed to load history from Google Sheets: {e}")
            return False
    
    async def get_device_logs(self, device_id: int, log_name: str = None, 
                            limit: int = 100) -> List[Dict[str, Any]]:
        """Получение логов устройства из таблицы"""
        try:
            with db_session() as db:
                logs_table = self._get_logs_table(db)
                return logs_table.get_logs(device_id, log_name, limit)
        except Exception as e:
            print(f"[Logs] Failed to get device logs: {e}")
            return []
    
    async def get_device_log_names(self, device_id: int) -> List[str]:
        """Получение списка имен логов для устройства"""
        try:
            with db_session() as db:
                logs_table = self._get_logs_table(db)
                return logs_table.get_log_names(device_id)
        except Exception as e:
            print(f"[Logs] Failed to get log names: {e}")
            return []
    
    async def cleanup_old_logs(self, device_id: int, days_to_keep: int = 30):
        """Очистка старых логов"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            with db_session() as db:
                from sqlalchemy import text
                
                delete_sql = text("""
                DELETE FROM device_logs 
                WHERE device_id = :device_id AND timestamp < :cutoff_date
                """)
                
                result = db.execute(delete_sql, {
                    'device_id': device_id,
                    'cutoff_date': cutoff_date
                })
                
                db.commit()
                deleted_count = result.rowcount
                
                print(f"[Logs] Cleaned up {deleted_count} old log entries for device {device_id}")
                return deleted_count
                
        except Exception as e:
            print(f"[Logs] Failed to cleanup old logs: {e}")
            return 0
    
    def _update_device_logs_export_time(self, device_id: int, log_name: str):
        """Обновляет время последнего экспорта логов в параметрах устройства"""
        try:
            from db_models.devices import Devices as DbDevices
            
            with db_session() as db:
                device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
                if device:
                    params = device.params if isinstance(device.params, dict) else {}
                    
                    current_time = datetime.now().isoformat()
                    params['last_logs_export'] = current_time
                    
                    # Добавляем лог в список экспортированных файлов
                    uploaded_files = params.get('uploaded_files', [])
                    if log_name not in uploaded_files:
                        uploaded_files.append(log_name)
                    params['uploaded_files'] = uploaded_files
                    
                    device.params = params
                    db.commit()
                    
                    # Отправляем WebSocket уведомление об обновлении устройства
                    self._broadcast_device_update(device_id, device.to_dict())
        except Exception as e:
            print(f"Error updating device logs export time: {e}")
    
    def _broadcast_device_update(self, device_id: int, device_data: dict):
        """
        Отправляет WebSocket уведомление об обновлении устройства
        """
        try:
            from utils.socket_utils import connection_manager
            import asyncio
            import threading
            
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
            print(f"Error broadcasting device update: {e}")


# Глобальный экземпляр менеджера логов
enhanced_logs_manager = EnhancedLogsManager()
