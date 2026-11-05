"""
API endpoints for virtual ports management
Virtual ports are entities in Home Assistant with prefix "virtual"
used for interaction with automation and energy modules
"""
import json
import os
import shutil
import tempfile
import threading
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.logger import virtual_ports_logger as virtual_ports_logger
from utils.configs import get_data_dir
from utils.ha_manager import ha_manager
from utils.home_assistant import PortConfig, PortType, ControlType
import asyncio
from datetime import datetime


# File updates can be triggered by several WebSocket callbacks at the same
# time.  A lock prevents interleaved writes; atomic replacement prevents a
# reader from ever seeing a half-written JSON document.
_VIRTUAL_PORTS_IO_LOCK = threading.RLock()
_LOAD_ERROR_STATE = {"signature": None, "logged_at": 0.0}


def _virtual_ports_backup_file(file_path: str) -> str:
    return f"{file_path}.bak"


def _validate_virtual_ports_payload(data: Any) -> Dict[str, Any]:
    """Validate the persisted shape before it becomes the active file."""
    if not isinstance(data, dict):
        raise ValueError("virtual ports root must be an object")
    if not isinstance(data.get("ports", []), list):
        raise ValueError("virtual ports 'ports' must be an array")
    # Catch non-JSON values before touching the active file.
    json.dumps(data, ensure_ascii=False)
    return data


def _read_virtual_ports_file(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as file:
        return _validate_virtual_ports_payload(json.load(file))


def _fsync_directory(directory: str) -> None:
    """Make the rename durable where the platform supports directory fsync."""
    try:
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except (AttributeError, OSError):
        # Windows and some filesystems do not allow opening directories this way.
        pass


def _atomic_write_virtual_ports(file_path: str, data: Dict[str, Any], *, make_backup: bool) -> None:
    """Write JSON through a same-directory temp file and atomic os.replace."""
    directory = os.path.dirname(file_path) or "."
    os.makedirs(directory, exist_ok=True)
    validated = _validate_virtual_ports_payload(data)
    temp_path = None

    try:
        if make_backup and os.path.exists(file_path):
            try:
                _read_virtual_ports_file(file_path)
                shutil.copy2(file_path, _virtual_ports_backup_file(file_path))
            except Exception as error:
                virtual_ports_logger.warning(
                    f"Skipping virtual ports backup because the current file is invalid: {error}"
                )

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix=".virtual_ports.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temp_path = temporary_file.name
            json.dump(validated, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        # Validate the bytes that will actually be installed, not only the
        # in-memory object passed by the caller.
        _read_virtual_ports_file(temp_path)
        os.replace(temp_path, file_path)
        _fsync_directory(directory)
        temp_path = None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class VirtualPort(BaseModel):
    """Виртуальный порт"""
    id: str  # UUID
    name: str  # Имя порта
    entity_id: str  # entity_id в HA (начинается с virtual.)
    type: str = "sensor"  # Тип entity: sensor, switch, number, input_number, input_boolean, input_text, input_select
    description: Optional[str] = None
    unit: Optional[str] = None  # Единица измерения
    device_class: Optional[str] = None  # Класс устройства для HA (temperature, power, energy и т.д.)
    icon: Optional[str] = None  # Иконка
    state_class: Optional[str] = None  # measurement, total, total_increasing
    unit_of_measurement: Optional[str] = None  # Единица измерения (альтернатива unit)
    min_value: Optional[float] = None  # Минимальное значение (для number)
    max_value: Optional[float] = None  # Максимальное значение (для number)
    step: Optional[float] = None  # Шаг изменения (для number)
    mode: Optional[str] = None  # box, slider (для input_number)
    initial_value: Optional[Any] = None  # Начальное значение
    value: Optional[Any] = None  # Текущее значение
    options: Optional[List[str]] = None  # Опции для input_select
    attributes: Dict[str, Any] = {}  # Дополнительные атрибуты
    enabled_by_default: bool = True  # Включен по умолчанию
    entity_category: Optional[str] = None  # config, diagnostic
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def update_module_link_display_ports(link):
    """Publish link values to display-only virtual ports.

    These ports intentionally have no physical binding. They are presentation
    outputs for HA/board dashboards and must never dispatch a device command.
    """
    data = load_virtual_ports()
    changed = False
    states = link.to_dict().get("states", {})
    for port in data.get("ports", []):
        binding = port.get("binding") or {}
        if binding.get("module_link_id") != link.link_id:
            continue
        value_name = binding.get("value_name")
        if value_name not in states:
            continue
        state = states[value_name]
        port["value"] = state.get("value")
        port["online"] = state.get("quality") not in {"offline", "timeout", "invalid"}
        port["offline_reason"] = state.get("error")
        port["quality"] = state.get("quality")
        port["last_source_update"] = state.get("updated_at")
        port["updated_at"] = datetime.now().isoformat()
        changed = True
        try:
            if port.get("entity_id") and ha_manager.ha_client and ha_manager.ha_client.connected:
                asyncio.create_task(ha_manager.ha_client.set_state(
                    port["entity_id"], str(port["value"]), ControlType.UI,
                    {"friendly_name": port.get("name", "Module link display"),
                     "module_link_id": link.link_id,
                     "module_link_value": value_name,
                     "quality": state.get("quality"),
                     "read_only": True,
                     "physical_outputs_protected": True}
                ))
        except Exception as error:
            virtual_ports_logger.debug("Module link display publish failed: %s", error)
    if changed:
        save_virtual_ports(data)


def get_virtual_ports_file() -> str:
    """Получить путь к файлу с виртуальными портами"""
    data_dir = get_data_dir()
    return os.path.join(data_dir, 'virtual_ports.json')


def load_virtual_ports() -> Dict[str, Any]:
    """Load virtual ports and recover automatically from the last good backup."""
    file_path = get_virtual_ports_file()
    with _VIRTUAL_PORTS_IO_LOCK:
        if not os.path.exists(file_path):
            return {"ports": []}

        try:
            return _read_virtual_ports_file(file_path)
        except Exception as error:
            backup_file = _virtual_ports_backup_file(file_path)
            try:
                recovered = _read_virtual_ports_file(backup_file)
                _atomic_write_virtual_ports(file_path, recovered, make_backup=False)
                virtual_ports_logger.warning(
                    f"Recovered virtual ports from backup after invalid JSON: {error}"
                )
                return recovered
            except Exception as backup_error:
                # Do not flood the log on every polling request if both files
                # are broken. The first occurrence and periodic repeats remain
                # visible for diagnosis.
                signature = f"{type(error).__name__}:{error}|backup:{backup_error}"
                now = time.monotonic()
                if (
                    signature != _LOAD_ERROR_STATE["signature"]
                    or now - _LOAD_ERROR_STATE["logged_at"] >= 60
                ):
                    virtual_ports_logger.error(
                        "Error loading virtual ports; active and backup files are invalid: "
                        f"{error}; {backup_error}"
                    )
                    _LOAD_ERROR_STATE.update(signature=signature, logged_at=now)
                return {"ports": []}


def save_virtual_ports(data: Dict[str, Any]) -> None:
    """Persist virtual ports without exposing partially-written JSON."""
    file_path = get_virtual_ports_file()
    try:
        with _VIRTUAL_PORTS_IO_LOCK:
            _atomic_write_virtual_ports(file_path, data, make_backup=True)
    except Exception as error:
        virtual_ports_logger.error(f"Error saving virtual ports: {error}")
        raise HTTPException(status_code=500, detail=f"Error saving virtual ports: {str(error)}")


def _virtual_port_type_to_port_type(virtual_type: str) -> PortType:
    """Преобразовать тип виртуального порта в PortType"""
    type_mapping = {
        "sensor": PortType.SENSOR,
        "switch": PortType.SWITCH,
        "number": PortType.NUMBER,
        "input_number": PortType.INPUT_NUMBER,
        "input_boolean": PortType.INPUT_BOOLEAN,
        "input_text": PortType.INPUT_TEXT,
        "input_select": PortType.INPUT_SELECT,
        "input_button": PortType.INPUT_BUTTON,
    }
    return type_mapping.get(virtual_type, PortType.SENSOR)


def _generate_entity_id(port_type: str, name: str) -> str:
    """Генерировать entity_id в формате <type>.virtual.<name>"""
    # Нормализуем имя (убираем пробелы, приводим к нижнему регистру)
    normalized_name = name.lower().replace(" ", "_").replace("-", "_")
    # Убираем специальные символы
    normalized_name = "".join(c for c in normalized_name if c.isalnum() or c == "_")
    
    # Формат: <type>.virtual.<name>
    return f"{port_type}.virtual.{normalized_name}"


def _normalize_entity_id(entity_id: str, port_type: str) -> str:
    """Нормализовать entity_id в новый формат <type>.virtual.<name>"""
    if not entity_id:
        return entity_id
    
    # Если уже в новом формате, возвращаем как есть
    if "." in entity_id and entity_id.split(".")[0] in ["sensor", "switch", "number", "input_number", "input_boolean", "input_text", "input_select", "input_button"]:
        if ".virtual." in entity_id:
            return entity_id
    
    # Если старый формат virtual.<name>, преобразуем в новый
    if entity_id.startswith("virtual."):
        name = entity_id.replace("virtual.", "")
        return _generate_entity_id(port_type, name)
    
    # Если просто имя, генерируем новый формат
    return _generate_entity_id(port_type, entity_id)


def _get_old_entity_id(port: Dict[str, Any]) -> Optional[str]:
    """Получить старый формат entity_id для миграции"""
    # Если entity_id уже в новом формате, ищем старый формат
    entity_id = port.get("entity_id", "")
    if not entity_id:
        return None
    
    # Если entity_id в новом формате <type>.virtual.<name>
    if ".virtual." in entity_id:
        parts = entity_id.split(".virtual.")
        if len(parts) == 2:
            name = parts[1]
            # Старый формат был virtual.<name>
            old_entity_id = f"virtual.{name}"
            return old_entity_id
    
    return None


async def sync_virtual_port_to_ha(port: Dict[str, Any]) -> bool:
    """
    Синхронизировать виртуальный порт с Home Assistant.
    
    Создает или обновляет entity в HA с параметрами порта.
    Вызывается при создании и обновлении порта.
    """
    try:
        if not ha_manager.ha_client:
            virtual_ports_logger.warning(f"HA client not initialized, cannot sync virtual port {port.get('entity_id')}")
            return False
            
        if not ha_manager.ha_client.connected:
            virtual_ports_logger.warning(f"HA client not connected, cannot sync virtual port {port.get('entity_id')}")
            return False
            
        if not ha_manager.ha_client.authenticated:
            virtual_ports_logger.warning(f"HA client not authenticated, cannot sync virtual port {port.get('entity_id')}")
            return False
        
        entity_id = port.get("entity_id")
        if not entity_id:
            virtual_ports_logger.error(f"Virtual port missing entity_id: {port.get('id')}")
            return False
        
        # Проверяем, есть ли старый entity со старым форматом
        old_entity_id = _get_old_entity_id(port)
        if old_entity_id and old_entity_id != entity_id:
            # Проверяем, существует ли старый entity в HA
            try:
                old_state = await ha_manager.ha_client.get_state(old_entity_id)
                if old_state and old_state.get("state") is not None:
                    virtual_ports_logger.info(f"Found old entity format {old_entity_id}, deleting it before creating new one")
                    # Удаляем старый entity
                    await delete_virtual_port_from_ha(old_entity_id)
            except Exception as e:
                virtual_ports_logger.debug(f"Old entity {old_entity_id} not found or already deleted: {e}")
        
        # Формируем PortConfig
        port_type = _virtual_port_type_to_port_type(port.get("type", "sensor"))
        
        port_config = PortConfig(
            entity_id=entity_id,
            name=port.get("name", "Virtual Port"),
            port_type=port_type,
            device_class=port.get("device_class"),
            unit_of_measurement=port.get("unit_of_measurement"),
            icon=port.get("icon"),
            state_class=port.get("state_class"),
            entity_category=port.get("entity_category"),
            enabled_by_default=port.get("enabled_by_default", True),
            force_update=False,
            attributes={**(port.get("attributes", {}) or {}),
                        "virtual_device_id": port.get("virtual_device_id"),
                        "virtual_source": port.get("source", "manual"),
                        "physical_binding": port.get("binding")}
        )
        
        # Создаем или обновляем entity в HA
        result = await ha_manager.ha_client.create_port(port_config)
        
        if result.get("success"):
            # Публикация — источник истины для HA-индикаторов в UI.
            # Наличие entity_id само по себе не означает, что порт опубликован.
            pdata = load_virtual_ports()
            stored_port = next((item for item in pdata.get("ports", []) if item.get("id") == port.get("id")), None)
            if stored_port is not None:
                stored_port["published"] = True
                stored_port["published_at"] = datetime.now().isoformat()
                save_virtual_ports(pdata)
            # Устанавливаем начальное значение если есть
            initial_value = port.get("value") or port.get("initial_value")
            if initial_value is not None:
                state_str = str(initial_value)
                await ha_manager.ha_client.set_state(
                    entity_id, 
                    state_str, 
                    ControlType.UI,
                    {"friendly_name": port.get("name", "Virtual Port")}
                )
            virtual_ports_logger.info(f"Virtual port synced to HA: {entity_id}")
            virtual_ports_logger.info(f"Synced virtual port {entity_id} to Home Assistant")
            return True
        else:
            virtual_ports_logger.error(f"Failed to sync virtual port to HA: {result.get('error')}")
            return False
            
    except Exception as e:
        virtual_ports_logger.error(f"Error syncing virtual port to HA: {e}")
        return False


async def delete_virtual_port_from_ha(entity_id: str) -> bool:
    """Удалить виртуальный порт из Home Assistant"""
    try:
        # Проверяем подключение к HA
        if not ha_manager.ha_client:
            virtual_ports_logger.warning("HA client not initialized")
            return False

        if not ha_manager.ha_client.connected:
            virtual_ports_logger.warning(f"HA client not connected, cannot delete virtual port {entity_id}")
            return False

        if not ha_manager.ha_client.authenticated:
            virtual_ports_logger.warning(f"HA client not authenticated, cannot delete virtual port {entity_id}")
            return False
        
        result = await ha_manager.ha_client.delete_port(entity_id)
        if result.get("success"):
            virtual_ports_logger.info(f"Virtual port deleted from HA: {entity_id}")
            virtual_ports_logger.info(f"Deleted virtual port {entity_id} from Home Assistant")
            return True
        else:
            virtual_ports_logger.error(f"Failed to delete virtual port from HA: {result.get('error')}")
            return False
            
    except Exception as e:
        virtual_ports_logger.error(f"Error deleting virtual port from HA: {e}")
        return False


async def cleanup_old_virtual_ports_from_ha():
    """Удалить все старые виртуальные порты со старым форматом из HA"""
    try:
        # Проверяем подключение к HA
        if not ha_manager.ha_client:
            virtual_ports_logger.warning("HA client not initialized, cannot cleanup old virtual ports")
            return

        if not ha_manager.ha_client.connected:
            virtual_ports_logger.warning("HA client not connected, cannot cleanup old virtual ports")
            return

        if not ha_manager.ha_client.authenticated:
            virtual_ports_logger.warning("HA client not authenticated, cannot cleanup old virtual ports")
            return
        
        # Получаем все states из HA
        states_result = await ha_manager.ha_client.get_states()
        if not states_result.get("success"):
            virtual_ports_logger.warning("Failed to get states from HA for cleanup")
            return
        
        # Проверяем формат данных - может быть result или data
        states = states_result.get("result", []) or states_result.get("data", [])
        if not isinstance(states, list):
            virtual_ports_logger.warning(f"Unexpected states format: {type(states)}")
            return
        
        old_entities = []
        
        # Ищем все entity со старым форматом virtual.* (но не <type>.virtual.*)
        # И не трогаем обычные порты устройств (myhome.*)
        for state in states:
            entity_id = state.get("entity_id", "")
            if not entity_id:
                continue
            
            # Старый формат: начинается с virtual. но не содержит <type>.virtual.
            # И не является обычным портом устройства (myhome.*)
            if (entity_id.startswith("virtual.") and 
                ".virtual." not in entity_id and
                not entity_id.startswith("myhome")):
                old_entities.append(entity_id)
        
        if old_entities:
            virtual_ports_logger.info(f"Found {len(old_entities)} old virtual port entities to cleanup: {old_entities}")
            virtual_ports_logger.info(f"Cleaning up {len(old_entities)} old virtual port entities")
            for old_entity_id in old_entities:
                try:
                    await delete_virtual_port_from_ha(old_entity_id)
                    virtual_ports_logger.info(f"Cleaned up old virtual port: {old_entity_id}")
                    virtual_ports_logger.info(f"Cleaned up old virtual port entity: {old_entity_id}")
                except Exception as e:
                    virtual_ports_logger.error(f"Error cleaning up old virtual port {old_entity_id}: {e}")
        else:
            virtual_ports_logger.debug("No old virtual port entities found in HA")
            
    except Exception as e:
        virtual_ports_logger.error(f"Error cleaning up old virtual ports from HA: {e}")


async def sync_all_virtual_ports_to_ha():
    """Синхронизировать все виртуальные порты с Home Assistant"""
    try:
        # Проверяем подключение
        if not ha_manager.ha_client or not ha_manager.ha_client.connected:
            virtual_ports_logger.warning("HA client not connected, skipping virtual ports sync")
            return
        
        # Сначала очищаем старые порты со старым форматом (только один раз, не блокируя)
        try:
            await cleanup_old_virtual_ports_from_ha()
        except Exception as e:
            virtual_ports_logger.warning(f"Error during cleanup of old virtual ports (continuing): {e}")
        
        data = load_virtual_ports()
        ports = data.get("ports", [])
        
        if not ports:
            virtual_ports_logger.debug("No virtual ports to sync")
            return
        
        virtual_ports_logger.info(f"Syncing {len(ports)} virtual ports to HA...")
        virtual_ports_logger.info(f"Starting sync of {len(ports)} virtual ports to Home Assistant")
        
        synced_count = 0
        for port in ports:
            try:
                # Создаем задачу для синхронизации каждого порта
                import asyncio
                asyncio.create_task(sync_virtual_port_to_ha(port))
                synced_count += 1
            except Exception as e:
                virtual_ports_logger.error(f"Error syncing virtual port {port.get('entity_id')}: {e}")
                continue
        
        virtual_ports_logger.info(f"Synced {synced_count}/{len(ports)} virtual ports to HA")
        virtual_ports_logger.info(f"Successfully synced {synced_count}/{len(ports)} virtual ports to Home Assistant")
        
    except Exception as e:
        virtual_ports_logger.error(f"Error syncing all virtual ports to HA: {e}")


def add_virtual_ports_routes(app: APIRouter):
    """Добавить маршруты для управления виртуальными портами"""
    
    @app.get("/api/virtual-ports", tags=["virtual-ports"])
    async def get_virtual_ports():
        """Получить список всех виртуальных портов"""
        try:
            data = load_virtual_ports()
            return {
                "success": True,
                "ports": data.get("ports", [])
            }
        except Exception as e:
            virtual_ports_logger.error(f"Error getting virtual ports: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/virtual-ports/{port_id}", tags=["virtual-ports"])
    async def get_virtual_port(port_id: str):
        """Получить виртуальный порт по ID"""
        try:
            data = load_virtual_ports()
            ports = data.get("ports", [])
            port = next((p for p in ports if p.get("id") == port_id), None)
            if not port:
                raise HTTPException(status_code=404, detail="Virtual port not found")
            return {
                "success": True,
                "port": port
            }
        except HTTPException:
            raise
        except Exception as e:
            virtual_ports_logger.error(f"Error getting virtual port: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/virtual-ports", tags=["virtual-ports"])
    async def create_virtual_port(port_data: Dict[str, Any]):
        """Создать новый виртуальный порт"""
        try:
            import uuid
            from datetime import datetime
            
            data = load_virtual_ports()
            ports = data.get("ports", [])
            
            # Генерируем ID если не указан
            port_id = port_data.get("id") or str(uuid.uuid4())
            
            # Проверяем, что ID уникален
            if any(p.get("id") == port_id for p in ports):
                raise HTTPException(status_code=400, detail="Port ID already exists")
            
            # Получаем тип порта
            port_type = port_data.get("type", "sensor")
            
            # Получаем entity_id
            entity_id = port_data.get("entity_id", "")
            if not entity_id:
                # Генерируем entity_id в формате <type>.virtual.<name>
                name = port_data.get("name", "")
                entity_id = _generate_entity_id(port_type, name) if name else f"{port_type}.virtual.port_{port_id[:8]}"
            else:
                # Нормализуем entity_id в новый формат
                entity_id = _normalize_entity_id(entity_id, port_type)
            
            # Проверяем, что entity_id уникален
            if any(p.get("entity_id") == entity_id for p in ports):
                raise HTTPException(status_code=400, detail=f"Entity ID {entity_id} already exists")
            
            port_dict = {
                "id": port_id,
                "name": port_data.get("name", "Virtual Port"),
                "entity_id": entity_id,
                "type": port_data.get("type", "sensor"),
                "description": port_data.get("description"),
                "unit": port_data.get("unit"),
                "unit_of_measurement": port_data.get("unit_of_measurement", port_data.get("unit")),
                "device_class": port_data.get("device_class"),
                "icon": port_data.get("icon"),
                "state_class": port_data.get("state_class"),
                "min_value": port_data.get("min_value"),
                "max_value": port_data.get("max_value"),
                "step": port_data.get("step"),
                "mode": port_data.get("mode"),
                "initial_value": port_data.get("initial_value"),
                "value": port_data.get("value", port_data.get("initial_value")),
                "options": port_data.get("options"),
                "attributes": port_data.get("attributes", {}),
                "enabled_by_default": port_data.get("enabled_by_default", True),
                "entity_category": port_data.get("entity_category"),
                "source": port_data.get("source", "manual"),
                "binding": port_data.get("binding"),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            ports.append(port_dict)
            data["ports"] = ports
            save_virtual_ports(data)
            
            # Синхронизируем с HA (асинхронно, не блокируя ответ)
            try:
                import asyncio
                # В контексте FastAPI всегда есть запущенный event loop
                asyncio.create_task(sync_virtual_port_to_ha(port_dict))
                virtual_ports_logger.info(f"Virtual port created and queued for HA sync: {port_id} ({entity_id})")
            except Exception as e:
                virtual_ports_logger.error(f"Error scheduling virtual port sync to HA: {e}")
                # Порт создан, но не синхронизирован с HA - это не критично, можно синхронизировать позже
            
            virtual_ports_logger.info(f"Virtual port created: {port_id} ({entity_id})")
            virtual_ports_logger.info(f"Created virtual port {entity_id} ({port_type})")
            return {
                "success": True,
                "port": port_dict
            }
        except HTTPException:
            raise
        except Exception as e:
            virtual_ports_logger.error(f"Error creating virtual port: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put("/api/virtual-ports/{port_id}", tags=["virtual-ports"])
    async def update_virtual_port(port_id: str, port_update: Dict[str, Any]):
        """Обновить виртуальный порт"""
        try:
            from datetime import datetime
            
            data = load_virtual_ports()
            ports = data.get("ports", [])
            
            port_index = next((i for i, p in enumerate(ports) if p.get("id") == port_id), None)
            if port_index is None:
                raise HTTPException(status_code=404, detail="Virtual port not found")
            
            port = ports[port_index]
            
            # Сохраняем старый entity_id для удаления из HA
            old_entity_id = port.get("entity_id")
            
            # Обновляем поля (кроме id и created_at)
            for key, value in port_update.items():
                if key not in ["id", "created_at"]:
                    port[key] = value
            
            # Нормализуем entity_id в новый формат если изменился тип, имя или entity_id
            port_type = port.get("type", "sensor")
            new_entity_id = None
            
            # Если entity_id явно указан в обновлении
            if "entity_id" in port_update:
                new_entity_id = _normalize_entity_id(port_update.get("entity_id"), port_type)
                port["entity_id"] = new_entity_id
            # Если изменился тип или имя, нужно перегенерировать entity_id
            elif "type" in port_update or "name" in port_update:
                # Генерируем новый entity_id на основе текущего типа и имени
                current_name = port.get("name", "")
                if current_name:
                    new_entity_id = _generate_entity_id(port_type, current_name)
                elif port.get("entity_id"):
                    # Если имени нет, используем существующий entity_id, но нормализуем его
                    new_entity_id = _normalize_entity_id(port["entity_id"], port_type)
                else:
                    # Если ничего нет, создаем новый
                    new_entity_id = f"{port_type}.virtual.port_{port_id[:8]}"
                port["entity_id"] = new_entity_id
            # Если entity_id уже есть, просто нормализуем его
            elif port.get("entity_id"):
                port["entity_id"] = _normalize_entity_id(port["entity_id"], port_type)
                new_entity_id = port["entity_id"]
            # Если entity_id нет, генерируем новый
            else:
                current_name = port.get("name", "")
                if current_name:
                    new_entity_id = _generate_entity_id(port_type, current_name)
                else:
                    new_entity_id = f"{port_type}.virtual.port_{port_id[:8]}"
                port["entity_id"] = new_entity_id
            
            # Проверяем уникальность нового entity_id (если он изменился)
            if new_entity_id and new_entity_id != old_entity_id:
                if any(p.get("entity_id") == new_entity_id for p in ports if p.get("id") != port_id):
                    raise HTTPException(status_code=400, detail=f"Entity ID {new_entity_id} already exists")
            
            port["updated_at"] = datetime.now().isoformat()
            ports[port_index] = port
            data["ports"] = ports
            save_virtual_ports(data)
            
            # Если entity_id изменился, удаляем старый entity из HA
            if old_entity_id and new_entity_id and old_entity_id != new_entity_id:
                try:
                    import asyncio
                    asyncio.create_task(delete_virtual_port_from_ha(old_entity_id))
                    virtual_ports_logger.info(f"Old virtual port entity scheduled for deletion from HA: {old_entity_id}")
                except Exception as e:
                    virtual_ports_logger.error(f"Error scheduling old virtual port deletion from HA: {e}")

            # Синхронизируем с HA (асинхронно, не блокируя ответ)
            # Обновляем порт в HA с новыми параметрами
            if new_entity_id:
                try:
                    import asyncio
                    asyncio.create_task(sync_virtual_port_to_ha(port))
                    virtual_ports_logger.info(f"Virtual port updated and queued for HA sync: {port_id} ({new_entity_id})")
                except Exception as e:
                    virtual_ports_logger.error(f"Error scheduling virtual port sync to HA: {e}")
                    # Порт обновлен, но не синхронизирован с HA - это не критично
            else:
                virtual_ports_logger.warning(f"Virtual port updated but no entity_id: {port_id}")
            
            virtual_ports_logger.info(f"Virtual port updated: {port_id}")
            virtual_ports_logger.info(f"Updated virtual port {port_id}")
            return {
                "success": True,
                "port": port
            }
        except HTTPException:
            raise
        except Exception as e:
            virtual_ports_logger.error(f"Error updating virtual port: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/api/virtual-ports/{port_id}", tags=["virtual-ports"])
    async def delete_virtual_port(port_id: str):
        """Удалить виртуальный порт"""
        try:
            data = load_virtual_ports()
            ports = data.get("ports", [])
            
            port_index = next((i for i, p in enumerate(ports) if p.get("id") == port_id), None)
            if port_index is None:
                raise HTTPException(status_code=404, detail="Virtual port not found")
            
            port = ports[port_index]
            entity_id = port.get("entity_id")
            ports.pop(port_index)
            data["ports"] = ports
            save_virtual_ports(data)
            
            # Удаляем из HA
            if entity_id:
                try:
                    import asyncio
                    asyncio.create_task(delete_virtual_port_from_ha(entity_id))
                except Exception as e:
                    virtual_ports_logger.error(f"Error deleting virtual port from HA: {e}")
            
            virtual_ports_logger.info(f"Virtual port deleted: {port_id}")
            virtual_ports_logger.info(f"Deleted virtual port {port_id}")
            return {
                "success": True,
                "message": "Virtual port deleted"
            }
        except HTTPException:
            raise
        except Exception as e:
            virtual_ports_logger.error(f"Error deleting virtual port: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/virtual-ports/{port_id}/value", tags=["virtual-ports"])
    async def set_virtual_port_value(port_id: str, value_data: Dict[str, Any]):
        """Установить значение виртуального порта"""
        try:
            from datetime import datetime
            
            data = load_virtual_ports()
            ports = data.get("ports", [])
            
            port_index = next((i for i, p in enumerate(ports) if p.get("id") == port_id), None)
            if port_index is None:
                raise HTTPException(status_code=404, detail="Virtual port not found")
            
            port = ports[port_index]
            port["value"] = value_data.get("value")
            port["updated_at"] = datetime.now().isoformat()
            ports[port_index] = port
            data["ports"] = ports
            save_virtual_ports(data)

            binding = port.get("binding") or {}
            if binding.get("device_id") is not None and binding.get("physical_code"):
                try:
                    from models.my_home import MyHomeClass
                    from utils.command_dispatcher import DeviceCommandDispatcher
                    from utils.state_model import DeviceCommand
                    result = await DeviceCommandDispatcher(MyHomeClass().get_client).dispatch(DeviceCommand(
                        device_id=int(binding["device_id"]), code=binding["physical_code"],
                        value=value_data.get("value"), source="virtual_port"))
                    if not result.get("success"):
                        return {"success": False, "port": port, "command": result, "error": result.get("error")}
                except Exception as error:
                    virtual_ports_logger.error(f"Error forwarding virtual port value: {error}")
                    return {"success": False, "port": port, "error": str(error)}
            
            # Обновляем значение в HA
            entity_id = port.get("entity_id")
            if entity_id and ha_manager.ha_client and ha_manager.ha_client.connected:
                try:
                    state_str = str(value_data.get("value"))
                    import asyncio
                    asyncio.create_task(ha_manager.ha_client.set_state(
                        entity_id,
                        state_str,
                        ControlType.UI,
                        {"friendly_name": port.get("name", "Virtual Port")}
                    ))
                except Exception as e:
                    virtual_ports_logger.error(f"Error updating virtual port value in HA: {e}")
            
            virtual_ports_logger.info(f"Virtual port value updated: {port_id} = {value_data.get('value')}")
            virtual_ports_logger.info(f"Virtual port {port_id} value set to {value_data.get('value')}")
            return {
                "success": True,
                "port": port
            }
        except HTTPException:
            raise
        except Exception as e:
            virtual_ports_logger.error(f"Error setting virtual port value: {e}")
            raise HTTPException(status_code=500, detail=str(e))
