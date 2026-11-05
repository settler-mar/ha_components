"""
API endpoints for automation modules and automations
"""
import json
import os
import uuid
import yaml
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel
from utils.logger import api_logger as logger
from utils.configs import get_data_dir


class ModulePort(BaseModel):
    """Порт модуля автоматизации"""
    name: str
    description: Optional[str] = None
    purpose: str  # input, output
    is_list: bool = False  # Единичный или список
    entity_id: Optional[str] = None  # Для HA портов
    required: bool = False


class ModuleParameter(BaseModel):
    """Параметр модуля"""
    name: str
    description: Optional[str] = None
    type: str = "float"  # Тип данных: float, int, str, bool
    default: Optional[Union[str, int, float, bool]] = None  # Значение по умолчанию
    allowed_sources: List[str] = ["fixed", "ha", "myhome"]  # Разрешенные источники: fixed, ha, myhome
    # При использовании: value может быть либо фиксированным значением (если source="fixed"),
    # либо entity_id (если source="ha" или "myhome")
    required: bool = False


class ModuleVisualComponent(BaseModel):
    """Визуальный компонент для интеграции на панель Home Assistant"""
    name: str  # Имя компонента
    description: Optional[str] = None  # Описание компонента
    parameters: Dict[str, Any] = {}  # Параметры компонента (любые ключ-значение)


class ModuleVersion(BaseModel):
    """Версия модуля (файл)"""
    version: str  # Например "1.0.0"
    min_compatible_version: Optional[str] = None  # Минимальная версия для перехода
    created_at: Optional[str] = None
    file_path: Optional[str] = None  # Путь к файлу версии
    # Метаданные (извлекаются из файла или задаются отдельно, но не редактируются)
    input_ports: List[ModulePort] = []  # Порты входа
    output_ports: List[ModulePort] = []  # Порты выхода
    parameters: List[ModuleParameter] = []  # Параметры модуля
    visual_components: List[ModuleVisualComponent] = []  # Визуальные компоненты для HA панели


class AutomationModule(BaseModel):
    """Модуль автоматизации (файл/скрипт)"""
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    file_path: Optional[str] = None  # Путь к файлу модуля
    versions: List[ModuleVersion] = []
    current_version: Optional[str] = None  # Текущая версия по умолчанию


class AutomationInstance(BaseModel):
    """Экземпляр автоматизации (использование модуля)"""
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    module_id: str  # ID модуля
    module_version: str  # Версия модуля
    active: bool = True
    input_ports: Dict[str, Any] = {}  # Связь портов модуля с entity
    output_ports: Dict[str, Any] = {}  # Связь портов модуля с entity
    parameters: Dict[str, Any] = {}  # Значения параметров


def get_automation_data_file() -> str:
    """Получает путь к файлу с данными автоматизации"""
    data_dir = get_data_dir()
    automation_file = os.path.join(data_dir, "automation.json")
    return automation_file


def get_modules_dir() -> str:
    """Получает путь к директории для хранения файлов модулей"""
    data_dir = get_data_dir()
    modules_dir = os.path.join(data_dir, "automation_modules")
    os.makedirs(modules_dir, exist_ok=True)
    return modules_dir


def get_module_versions_dir(module_id: str) -> str:
    """Получает путь к директории для хранения файлов версий модуля"""
    modules_dir = get_modules_dir()
    versions_dir = os.path.join(modules_dir, module_id, "versions")
    os.makedirs(versions_dir, exist_ok=True)
    return versions_dir


def load_automation_data() -> Dict[str, Any]:
    """Загружает данные автоматизации из файла"""
    automation_file = get_automation_data_file()
    if os.path.exists(automation_file):
        try:
            with open(automation_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.error(f"Error loading automation data: {e}")
            return {"modules": [], "instances": []}
    return {"modules": [], "instances": []}


def clean_module_data(module: dict) -> dict:
    """Очищает модуль от устаревших полей"""
    cleaned = module.copy()
    # Удаляем устаревшие поля
    cleaned.pop("ha_ports", None)
    cleaned.pop("virtual_ports", None)
    # Очищаем версии
    if "versions" in cleaned:
        cleaned["versions"] = [
            {k: v for k, v in version.items() if k not in ["ha_ports", "virtual_ports"]}
            for version in cleaned["versions"]
        ]
    return cleaned

def save_automation_data(data: Dict[str, Any]):
    """Сохраняет данные автоматизации в файл"""
    # Очищаем устаревшие поля перед сохранением
    if "modules" in data:
        data["modules"] = [clean_module_data(module) for module in data["modules"]]
    
    automation_file = get_automation_data_file()
    try:
        os.makedirs(os.path.dirname(automation_file), exist_ok=True)
        with open(automation_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Automation data saved to {automation_file}")
    except Exception as e:
        logger.error(f"Error saving automation data: {e}")
        raise


def add_automation_routes(app: APIRouter):
    """Добавление маршрутов для управления модулями автоматизации и автоматизациями"""
    from datetime import datetime
    
    # Создаем тестовый модуль при первом запуске (если модулей нет)
    try:
        data = load_automation_data()
        if not data.get("modules"):
            logger.info("Creating test automation module...")
            from models.create_test_module import create_test_module
            create_test_module()
            logger.info("Test automation module created")
    except Exception as e:
        logger.warning(f"Failed to create test module: {e}")
    
    # ========== МОДУЛИ ==========
    
    @app.get("/api/automation/modules", tags=["automation"])
    async def get_automation_modules():
        """Получение всех модулей автоматизации"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            # Добавляем информацию об использовании и очищаем данные
            instances = data.get("instances", [])
            cleaned_modules = []
            for module in modules:
                module_instances = [i for i in instances if i.get("module_id") == module.get("id")]
                module["usage"] = [
                    {
                        "instance_id": inst.get("id"),
                        "instance_name": inst.get("name"),
                        "version": inst.get("module_version")
                    }
                    for inst in module_instances
                ]
                cleaned_modules.append(clean_module_data(module))
            return {
                "success": True,
                "modules": cleaned_modules
            }
        except Exception as e:
            logger.error(f"Error getting automation modules: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/automation/modules/{module_id}", tags=["automation"])
    async def get_automation_module(module_id: str):
        """Получение модуля автоматизации по ID"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            module = next((m for m in modules if m.get("id") == module_id), None)
            if not module:
                raise HTTPException(status_code=404, detail="Module not found")
            
            # Добавляем информацию об использовании
            instances = data.get("instances", [])
            module_instances = [i for i in instances if i.get("module_id") == module_id]
            module["usage"] = [
                {
                    "instance_id": inst.get("id"),
                    "instance_name": inst.get("name"),
                    "version": inst.get("module_version")
                }
                for inst in module_instances
            ]
            
            # Очищаем устаревшие поля
            cleaned_module = clean_module_data(module)
            
            return {
                "success": True,
                "module": cleaned_module
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting automation module: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/automation/modules", tags=["automation"])
    async def create_automation_module(file: UploadFile = File(...)):
        """Создание нового модуля автоматизации (загрузка файла)"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            
            # Читаем содержимое файла для извлечения метаданных
            content_bytes = await file.read()
            content = content_bytes.decode('utf-8', errors='ignore')
            filename = file.filename or 'module.py'
            
            # Извлекаем метаданные из файла (из класса)
            metadata = extract_module_metadata_from_file(content, filename)
            
            # Генерируем ID
            module_id = str(uuid.uuid4())
            
            # Создаем директорию для модуля
            modules_dir = get_modules_dir()
            module_dir = os.path.join(modules_dir, module_id)
            os.makedirs(module_dir, exist_ok=True)
            
            # Сохраняем файл модуля
            module_file_path = os.path.join(module_dir, filename)
            with open(module_file_path, 'wb') as f:
                f.write(content_bytes)
            
            # Извлекаем версию из метаданных
            version = metadata.get("version") or "1.0.0"
            min_compatible_version = metadata.get("min_compatible_version")
            
            # Создаем директорию для версий
            versions_dir = get_module_versions_dir(module_id)
            os.makedirs(versions_dir, exist_ok=True)
            
            # Сохраняем файл как первую версию
            file_extension = os.path.splitext(filename)[1] or '.py'
            version_filename = f"{version}{file_extension}"
            version_file_path = os.path.join(versions_dir, version_filename)
            with open(version_file_path, 'wb') as f:
                f.write(content_bytes)
            
            # Создаем структуру модуля
            module_dict = {
                "id": module_id,
                "name": metadata["name"],
                "description": metadata.get("description") or "",
                "icon": metadata.get("icon") or "mdi-folder",
                "color": metadata.get("color") or "#1976d2",
                "file_path": filename,
                "current_version": version,
                "versions": [
                    {
                        "version": version,
                        "min_compatible_version": min_compatible_version,
                        "created_at": datetime.now().isoformat(),
                        "file_path": version_filename,
                        "input_ports": metadata.get("input_ports", []),
                        "output_ports": metadata.get("output_ports", []),
                        "parameters": metadata.get("parameters", []),
                        "visual_components": metadata.get("visual_components", [])
                    }
                ]
            }
            
            modules.append(module_dict)
            data["modules"] = modules
            save_automation_data(data)
            
            logger.info(f"Module created from file: {module_file_path} (id: {module_id})")
            
            return {
                "success": True,
                "module": module_dict
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating automation module: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put("/api/automation/modules/{module_id}", tags=["automation"])
    async def update_automation_module(module_id: str, module: AutomationModule):
        """Обновление модуля автоматизации (только общие сведения, не версии)"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            
            module_index = next((i for i, m in enumerate(modules) if m.get("id") == module_id), None)
            if module_index is None:
                raise HTTPException(status_code=404, detail="Module not found")
            
            # Сохраняем существующие версии
            existing_versions = modules[module_index].get("versions", [])
            existing_current_version = modules[module_index].get("current_version")
            
            module_dict = module.dict()
            module_dict["id"] = module_id
            module_dict["versions"] = existing_versions
            if existing_current_version:
                module_dict["current_version"] = existing_current_version
            
            modules[module_index] = module_dict
            data["modules"] = modules
            save_automation_data(data)
            
            return {
                "success": True,
                "module": module_dict
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating automation module: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/automation/modules/{module_id}/versions", tags=["automation"])
    async def add_module_version(
        module_id: str, 
        file: UploadFile = File(...)
    ):
        """Добавление новой версии модуля (загрузка файла версии)"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            
            module_index = next((i for i, m in enumerate(modules) if m.get("id") == module_id), None)
            if module_index is None:
                raise HTTPException(status_code=404, detail="Module not found")
            
            module = modules[module_index]
            versions = module.get("versions", [])
            
            # Читаем содержимое файла для извлечения версии
            content_bytes = await file.read()
            content = content_bytes.decode('utf-8', errors='ignore')
            filename = file.filename or ''
            
            # Извлекаем версию из файла
            version_info = extract_version_from_file(content, filename)
            version = version_info["version"]
            min_compatible_version = version_info["min_compatible_version"]
            
            # Проверяем, что версия не существует
            if any(v.get("version") == version for v in versions):
                raise HTTPException(status_code=400, detail=f"Version {version} already exists")
            
            # Сохраняем файл версии
            versions_dir = get_module_versions_dir(module_id)
            file_extension = os.path.splitext(file.filename)[1] if file.filename else '.py'
            version_filename = f"{version}{file_extension}"
            file_path = os.path.join(versions_dir, version_filename)
            
            with open(file_path, 'wb') as f:
                f.write(content_bytes)
            
            # Создаем запись версии
            version_dict = {
                "version": version,
                "min_compatible_version": min_compatible_version,
                "created_at": datetime.now().isoformat(),
                "file_path": version_filename,
                # Метаданные можно извлечь из файла позже или задать отдельно
                "input_ports": [],
                "output_ports": [],
                "parameters": [],
                "visual_components": [],
                "visual_components": []
            }
            
            versions.append(version_dict)
            module["versions"] = versions
            
            # Если это первая версия или текущая версия не установлена, устанавливаем как текущую
            if not module.get("current_version"):
                module["current_version"] = version
            
            modules[module_index] = module
            data["modules"] = modules
            save_automation_data(data)
            
            logger.info(f"Module version file uploaded: {file_path} (version: {version})")
            
            return {
                "success": True,
                "version": version_dict
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error adding module version: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/automation/modules/{module_id}/{action}", tags=["automation"])
    async def get_module_file(
        module_id: str,
        action: str
    ):
        """Получение содержимого или файла модуля по имени файла
        
        Args:
            module_id: ID модуля (это имя файла без расширения)
            action: Действие - 'content' (просмотр) или 'download' (скачивание)
        
        Примечание: module_id может быть либо UUID модуля, либо имя файла без расширения.
        Функция ищет файл в директории модуля по имени, совпадающему с module_id.
        
        Примеры:
            GET /api/automation/modules/{module_id}/content - получить содержимое файла модуля
            GET /api/automation/modules/{module_id}/download - скачать файл модуля
        """
        try:
            # Валидация action
            if action not in ["content", "download"]:
                raise HTTPException(status_code=400, detail=f"Invalid action: {action}. Allowed: content, download")
            
            modules_dir = get_modules_dir()
            
            # Сначала пробуем найти файл напрямую в директории modules с расширением .py
            # Это может быть файл, сохраненный напрямую в automation_modules/
            direct_file_path = os.path.join(modules_dir, f"{module_id}.py")
            if os.path.exists(direct_file_path) and os.path.isfile(direct_file_path):
                logger.debug(f"Found file directly in modules dir: {direct_file_path}")
                if action == "download":
                    return FileResponse(
                        direct_file_path,
                        media_type='application/octet-stream',
                        filename=f"{module_id}.py"
                    )
                else:
                    with open(direct_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return {
                        "success": True,
                        "content": content,
                        "filename": f"{module_id}.py"
                    }
            
            # Ищем модуль по ID
            data = load_automation_data()
            modules = data.get("modules", [])
            module = next((m for m in modules if m.get("id") == module_id), None)
            
            if module:
                # Если модуль найден, используем его директорию
                module_dir = os.path.join(modules_dir, module_id)
                module_file_path = module.get("file_path")
                
                # Логируем для отладки
                logger.debug(f"Getting file for module_id={module_id}, action={action}")
                logger.debug(f"Module dir: {module_dir}")
                logger.debug(f"Module file_path: {module_file_path}")
                
                # 1. Пробуем найти файл по file_path из модуля (с расширением .py если не указано)
                if module_file_path:
                    # Если file_path не имеет расширения, добавляем .py
                    file_path_with_ext = module_file_path
                    if not os.path.splitext(file_path_with_ext)[1]:
                        file_path_with_ext = f"{file_path_with_ext}.py"
                    
                    file_path = os.path.join(module_dir, file_path_with_ext)
                    if os.path.exists(file_path) and os.path.isfile(file_path):
                        logger.debug(f"Found module file by file_path: {file_path}")
                        if action == "download":
                            return FileResponse(
                                file_path,
                                media_type='application/octet-stream',
                                filename=os.path.basename(file_path_with_ext)
                            )
                        else:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            return {
                                "success": True,
                                "content": content,
                                "filename": os.path.basename(file_path_with_ext)
                            }
                    
                    # Если не найден, пробуем с оригинальным именем (без добавления расширения)
                    file_path = os.path.join(module_dir, module_file_path)
                    if os.path.exists(file_path) and os.path.isfile(file_path):
                        logger.debug(f"Found module file by file_path (original): {file_path}")
                        if action == "download":
                            return FileResponse(
                                file_path,
                                media_type='application/octet-stream',
                                filename=os.path.basename(module_file_path)
                            )
                        else:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            return {
                                "success": True,
                                "content": content,
                                "filename": os.path.basename(module_file_path)
                            }
                
                # 2. Пробуем найти файл с именем равным module_id (с расширением .py)
                if os.path.exists(module_dir):
                    possible_files = [
                        f"{module_id}.py",  # Имя файла = ID модуля + .py
                    ]
                    
                    for possible_file in possible_files:
                        file_path = os.path.join(module_dir, possible_file)
                        if os.path.exists(file_path) and os.path.isfile(file_path):
                            logger.debug(f"Found file by module_id: {file_path}")
                            if action == "download":
                                return FileResponse(
                                    file_path,
                                    media_type='application/octet-stream',
                                    filename=possible_file
                                )
                            else:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                return {
                                    "success": True,
                                    "content": content,
                                    "filename": possible_file
                                }
                    
                    # 3. Пробуем найти любой .py файл в директории модуля
                    for file in os.listdir(module_dir):
                        if file.endswith('.py') and os.path.isfile(os.path.join(module_dir, file)):
                            file_path = os.path.join(module_dir, file)
                            logger.debug(f"Found Python file in module dir: {file_path}")
                            if action == "download":
                                return FileResponse(
                                    file_path,
                                    media_type='application/octet-stream',
                                    filename=file
                                )
                            else:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                return {
                                    "success": True,
                                    "content": content,
                                    "filename": file
                                }
            
            # Если модуль не найден, пробуем найти файл напрямую по имени (если module_id это имя файла)
            # Пробуем с расширением .py
            possible_file_paths = [
                os.path.join(modules_dir, f"{module_id}.py"),  # Прямо в директории modules
            ]
            
            for file_path in possible_file_paths:
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    filename = os.path.basename(file_path)
                    logger.debug(f"Found file directly by name: {file_path}")
                    if action == "download":
                        return FileResponse(
                            file_path,
                            media_type='application/octet-stream',
                            filename=filename
                        )
                    else:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        return {
                            "success": True,
                            "content": content,
                            "filename": filename
                        }
            
            # Если ничего не найдено
            logger.error(f"File not found for module_id={module_id}")
            logger.error(f"Modules dir: {modules_dir}")
            logger.error(f"Modules dir exists: {os.path.exists(modules_dir)}")
            if os.path.exists(modules_dir):
                logger.error(f"Files in modules dir: {os.listdir(modules_dir)}")
            raise HTTPException(status_code=404, detail=f"Module file not found. Module dir: {modules_dir}")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting module file: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/api/automation/modules/{module_id}/versions/{version}", tags=["automation"])
    async def delete_module_version(module_id: str, version: str):
        """Удаление версии модуля (только если не используется)"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            instances = data.get("instances", [])
            
            module_index = next((i for i, m in enumerate(modules) if m.get("id") == module_id), None)
            if module_index is None:
                raise HTTPException(status_code=404, detail="Module not found")
            
            module = modules[module_index]
            versions = module.get("versions", [])
            
            version_index = next((i for i, v in enumerate(versions) if v.get("version") == version), None)
            if version_index is None:
                raise HTTPException(status_code=404, detail="Version not found")
            
            # Проверяем, используется ли версия
            if any(i.get("module_id") == module_id and i.get("module_version") == version for i in instances):
                raise HTTPException(status_code=400, detail="Version is in use and cannot be deleted")
            
            version_data = versions[version_index]
            
            # Удаляем файл версии
            if version_data.get("file_path"):
                versions_dir = get_module_versions_dir(module_id)
                file_path = os.path.join(versions_dir, version_data["file_path"])
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"Deleted version file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete version file: {e}")
            
            # Если удаляемая версия была текущей, устанавливаем другую версию или None
            if module.get("current_version") == version:
                remaining_versions = [v for v in versions if v.get("version") != version]
                if remaining_versions:
                    module["current_version"] = remaining_versions[0].get("version")
                else:
                    module["current_version"] = None
            
            versions.pop(version_index)
            module["versions"] = versions
            modules[module_index] = module
            data["modules"] = modules
            save_automation_data(data)
            
            return {
                "success": True,
                "message": "Version deleted"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting module version: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put("/api/automation/modules/{module_id}/current-version", tags=["automation"])
    async def set_current_module_version(module_id: str, version: str = Query(...)):
        """Установка текущей версии модуля по умолчанию"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            
            module_index = next((i for i, m in enumerate(modules) if m.get("id") == module_id), None)
            if module_index is None:
                raise HTTPException(status_code=404, detail="Module not found")
            
            module = modules[module_index]
            versions = module.get("versions", [])
            
            # Проверяем, что версия существует
            if not any(v.get("version") == version for v in versions):
                raise HTTPException(status_code=404, detail="Version not found")
            
            module["current_version"] = version
            modules[module_index] = module
            data["modules"] = modules
            save_automation_data(data)
            
            return {
                "success": True,
                "current_version": version
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error setting current module version: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/automation/modules/{module_id}/upload", tags=["automation"])
    async def upload_module_file(module_id: str, file: UploadFile = File(...)):
        """Загрузка файла модуля"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            
            module_index = next((i for i, m in enumerate(modules) if m.get("id") == module_id), None)
            if module_index is None:
                raise HTTPException(status_code=404, detail="Module not found")
            
            module = modules[module_index]
            modules_dir = get_modules_dir()
            
            # Определяем имя файла (используем имя модуля или имя загруженного файла)
            file_extension = os.path.splitext(file.filename)[1] if file.filename else '.py'
            module_filename = f"{module_id}{file_extension}"
            file_path = os.path.join(modules_dir, module_filename)
            
            # Сохраняем файл
            with open(file_path, 'wb') as f:
                content = await file.read()
                f.write(content)
            
            # Обновляем путь к файлу в модуле
            module["file_path"] = module_filename
            modules[module_index] = module
            data["modules"] = modules
            save_automation_data(data)
            
            logger.info(f"Module file uploaded: {file_path}")
            
            return {
                "success": True,
                "file_path": module_filename,
                "message": "File uploaded successfully"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading module file: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/automation/modules/{module_id}/file", tags=["automation"])
    async def get_module_file(module_id: str):
        """Получение файла модуля"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            module = next((m for m in modules if m.get("id") == module_id), None)
            
            if not module:
                raise HTTPException(status_code=404, detail="Module not found")
            
            if not module.get("file_path"):
                raise HTTPException(status_code=404, detail="Module file not found")
            
            modules_dir = get_modules_dir()
            file_path = os.path.join(modules_dir, module["file_path"])
            
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Module file not found on disk")
            
            return FileResponse(
                file_path,
                media_type='application/octet-stream',
                filename=module["file_path"]
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting module file: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/automation/modules/{module_id}/file/content", tags=["automation"])
    async def get_module_file_content(module_id: str):
        """Получение содержимого файла модуля"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            module = next((m for m in modules if m.get("id") == module_id), None)
            
            if not module:
                raise HTTPException(status_code=404, detail="Module not found")
            
            if not module.get("file_path"):
                raise HTTPException(status_code=404, detail="Module file not found")
            
            modules_dir = get_modules_dir()
            file_path = os.path.join(modules_dir, module["file_path"])
            
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Module file not found on disk")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "success": True,
                "content": content,
                "filename": module["file_path"]
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting module file content: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/api/automation/modules/{module_id}", tags=["automation"])
    async def delete_automation_module(module_id: str):
        """Удаление модуля автоматизации"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            instances = data.get("instances", [])
            
            # Проверяем, используется ли модуль
            if any(i.get("module_id") == module_id for i in instances):
                raise HTTPException(status_code=400, detail="Module is in use and cannot be deleted")
            
            module_index = next((i for i, m in enumerate(modules) if m.get("id") == module_id), None)
            if module_index is None:
                raise HTTPException(status_code=404, detail="Module not found")
            
            module = modules[module_index]
            
            # Удаляем файл модуля если он существует
            if module.get("file_path"):
                modules_dir = get_modules_dir()
                file_path = os.path.join(modules_dir, module["file_path"])
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"Deleted module file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete module file: {e}")
            
            modules.pop(module_index)
            data["modules"] = modules
            save_automation_data(data)
            
            return {
                "success": True,
                "message": "Module deleted"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting automation module: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # ========== АВТОМАТИЗАЦИИ (ЭКЗЕМПЛЯРЫ) ==========
    
    @app.get("/api/automation/instances", tags=["automation"])
    async def get_automation_instances():
        """Получение всех экземпляров автоматизаций"""
        try:
            data = load_automation_data()
            instances = data.get("instances", [])
            return {
                "success": True,
                "instances": instances
            }
        except Exception as e:
            logger.error(f"Error getting automation instances: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/automation/instances/{instance_id}", tags=["automation"])
    async def get_automation_instance(instance_id: str):
        """Получение экземпляра автоматизации по ID"""
        try:
            data = load_automation_data()
            instances = data.get("instances", [])
            instance = next((i for i in instances if i.get("id") == instance_id), None)
            if not instance:
                raise HTTPException(status_code=404, detail="Instance not found")
            return {
                "success": True,
                "instance": instance
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting automation instance: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/automation/instances", tags=["automation"])
    async def create_automation_instance(instance: AutomationInstance):
        """Создание нового экземпляра автоматизации"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            instances = data.get("instances", [])
            
            # Проверяем, что модуль существует
            module = next((m for m in modules if m.get("id") == instance.module_id), None)
            if not module:
                raise HTTPException(status_code=404, detail="Module not found")
            
            # Проверяем, что версия существует
            versions = module.get("versions", [])
            if not any(v.get("version") == instance.module_version for v in versions):
                raise HTTPException(status_code=404, detail="Module version not found")
            
            # Генерируем ID если не указан
            if not instance.id:
                instance.id = str(uuid.uuid4())
            
            # Проверяем, что ID уникален
            if any(i.get("id") == instance.id for i in instances):
                raise HTTPException(status_code=400, detail="Instance with this ID already exists")
            
            instance_dict = instance.dict()
            instances.append(instance_dict)
            data["instances"] = instances
            save_automation_data(data)
            
            return {
                "success": True,
                "instance": instance_dict
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating automation instance: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put("/api/automation/instances/{instance_id}", tags=["automation"])
    async def update_automation_instance(instance_id: str, instance: AutomationInstance):
        """Обновление экземпляра автоматизации"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            instances = data.get("instances", [])
            
            instance_index = next((i for i, inst in enumerate(instances) if inst.get("id") == instance_id), None)
            if instance_index is None:
                raise HTTPException(status_code=404, detail="Instance not found")
            
            # Если изменяется версия модуля, проверяем её существование
            if instance.module_version:
                module = next((m for m in modules if m.get("id") == instance.module_id), None)
                if module:
                    versions = module.get("versions", [])
                    if not any(v.get("version") == instance.module_version for v in versions):
                        raise HTTPException(status_code=404, detail="Module version not found")
            
            instance_dict = instance.dict()
            instance_dict["id"] = instance_id
            instances[instance_index] = instance_dict
            data["instances"] = instances
            save_automation_data(data)
            
            return {
                "success": True,
                "instance": instance_dict
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating automation instance: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put("/api/automation/instances/{instance_id}/version", tags=["automation"])
    async def change_instance_version(instance_id: str, new_version: str = Query(...)):
        """Изменение версии модуля для экземпляра автоматизации"""
        try:
            data = load_automation_data()
            modules = data.get("modules", [])
            instances = data.get("instances", [])
            
            instance_index = next((i for i, inst in enumerate(instances) if inst.get("id") == instance_id), None)
            if instance_index is None:
                raise HTTPException(status_code=404, detail="Instance not found")
            
            instance = instances[instance_index]
            module_id = instance.get("module_id")
            current_version = instance.get("module_version")
            
            # Проверяем, что модуль существует
            module = next((m for m in modules if m.get("id") == module_id), None)
            if not module:
                raise HTTPException(status_code=404, detail="Module not found")
            
            # Проверяем, что новая версия существует
            versions = module.get("versions", [])
            new_version_data = next((v for v in versions if v.get("version") == new_version), None)
            if not new_version_data:
                raise HTTPException(status_code=404, detail="Module version not found")
            
            # Проверяем совместимость версий
            min_compatible = new_version_data.get("min_compatible_version")
            if min_compatible and current_version:
                # Простая проверка совместимости (можно улучшить)
                current_parts = current_version.split(".")
                min_parts = min_compatible.split(".")
                if current_parts < min_parts:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot upgrade from {current_version} to {new_version}. Minimum required version: {min_compatible}"
                    )
            
            instance["module_version"] = new_version
            instances[instance_index] = instance
            data["instances"] = instances
            save_automation_data(data)
            
            return {
                "success": True,
                "instance": instance
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error changing instance version: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/api/automation/instances/{instance_id}", tags=["automation"])
    async def delete_automation_instance(instance_id: str):
        """Удаление экземпляра автоматизации"""
        try:
            data = load_automation_data()
            instances = data.get("instances", [])
            
            instance_index = next((i for i, inst in enumerate(instances) if inst.get("id") == instance_id), None)
            if instance_index is None:
                raise HTTPException(status_code=404, detail="Instance not found")
            
            instances.pop(instance_index)
            data["instances"] = instances
            save_automation_data(data)
            
            return {
                "success": True,
                "message": "Instance deleted"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting automation instance: {e}")
            raise HTTPException(status_code=500, detail=str(e))


def extract_version_from_file(content: str, filename: str = "") -> Dict[str, Optional[str]]:
    """Извлекает версию и минимальную совместимую версию из файла"""
    import re
    
    version = None
    min_compatible_version = None
    
    # Ищем в комментариях версию
    # Форматы: version: 1.0.0, version = "1.0.0", @version 1.0.0, # version: 1.0.0
    version_patterns = [
        r'version\s*[:=]\s*["\']?([\d.]+)["\']?',
        r'@version\s+([\d.]+)',
        r'#\s*version\s*[:=]\s*([\d.]+)',
        r'"""\s*version\s*[:=]\s*([\d.]+)',
    ]
    
    for pattern in version_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            version = match.group(1)
            break
    
    # Ищем минимальную совместимую версию
    min_version_patterns = [
        r'min_compatible_version\s*[:=]\s*["\']?([\d.]+)["\']?',
        r'min_version\s*[:=]\s*["\']?([\d.]+)["\']?',
        r'@min_version\s+([\d.]+)',
        r'#\s*min_compatible_version\s*[:=]\s*([\d.]+)',
        r'"""\s*min_compatible_version\s*[:=]\s*([\d.]+)',
    ]
    
    for pattern in min_version_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            min_compatible_version = match.group(1)
            break
    
    # Если версия не найдена, пытаемся извлечь из имени файла
    if not version and filename:
        filename_match = re.search(r'[\d.]+', filename)
        if filename_match:
            version = filename_match.group(0)
    
    # Если версия все еще не найдена, генерируем дефолтную
    if not version:
        version = "1.0.0"
    
    return {
        "version": version,
        "min_compatible_version": min_compatible_version
    }


def extract_module_metadata_from_file(content: str, filename: str = "") -> Dict[str, Any]:
    """Извлекает метаданные модуля из YAML блока в комментариях"""
    import re
    
    metadata = {
        "name": None,
        "description": None,
        "icon": None,
        "color": None,
        "version": None,
        "min_compatible_version": None,
        "class_name": None,
        "input_ports": [],
        "output_ports": [],
        "parameters": [],
        "visual_components": [],
        "visual_components": []
    }
    
    try:
        # Ищем блок MODULE_METADATA в docstring (двойные кавычки)
        # Паттерн: ищем начало блока с MODULE_METADATA: и извлекаем YAML до конца docstring
        pattern = r'"""[\s\n]*MODULE_METADATA:[\s\n]*(.*?)(?:"""|$)'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            # Если не нашли в docstring, ищем в комментариях
            # Ищем блок между MODULE_METADATA: и следующим пустым комментарием или концом комментариев
            pattern = r'#\s*MODULE_METADATA:[\s\n]*(.*?)(?=\n\s*\n|\n\s*class\s|\n\s*def\s|$)'
            match = re.search(pattern, content, re.DOTALL)
        
        if match:
            yaml_content = match.group(1).strip()
            
            # Парсим YAML
            try:
                yaml_data = yaml.safe_load(yaml_content)
                if yaml_data and isinstance(yaml_data, dict):
                    # Копируем данные из YAML
                    for key in metadata.keys():
                        if key in yaml_data:
                            metadata[key] = yaml_data[key]
            except yaml.YAMLError as e:
                logger.warning(f"Error parsing YAML metadata: {e}")
        
        # Если class_name не указан в YAML, пытаемся найти класс в коде
        if not metadata.get("class_name"):
            import ast
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        metadata["class_name"] = node.name
                        break
            except Exception:
                pass
        
        # Если метаданные не найдены, пытаемся извлечь из класса (fallback)
        if not metadata.get("name") or not metadata.get("version"):
            class_metadata = extract_metadata_from_class(content, filename)
            # Заполняем только отсутствующие поля
            for key in metadata.keys():
                if not metadata.get(key) and class_metadata.get(key):
                    metadata[key] = class_metadata[key]
        
        # Если name не найден, используем имя файла
        if not metadata["name"]:
            if filename:
                metadata["name"] = os.path.splitext(filename)[0]
            else:
                metadata["name"] = "Новый модуль"
        
        # Если version не найден, используем дефолтную
        if not metadata["version"]:
            metadata["version"] = "1.0.0"
        
        # Значения по умолчанию
        if not metadata["icon"]:
            metadata["icon"] = "mdi-folder"
        if not metadata["color"]:
            metadata["color"] = "#1976d2"
        
    except Exception as e:
        logger.warning(f"Error extracting metadata from YAML, using fallback: {e}")
        return extract_metadata_fallback(content, filename)
    
    return metadata


def extract_metadata_from_class(content: str, filename: str = "") -> Dict[str, Any]:
    """Извлекает метаданные из атрибутов класса (fallback)"""
    import ast
    
    metadata = {
        "name": None,
        "description": None,
        "icon": None,
        "color": None,
        "version": None,
        "min_compatible_version": None,
        "input_ports": [],
        "output_ports": [],
        "parameters": [],
        "visual_components": [],
        "visual_components": []
    }
    
    try:
        tree = ast.parse(content)
        
        # Ищем класс
        module_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                module_class = node
                break
        
        if not module_class:
            return metadata
        
        # Извлекаем имя класса
        metadata["name"] = module_class.name
        
        # Извлекаем docstring
        if ast.get_docstring(module_class):
            metadata["description"] = ast.get_docstring(module_class).strip()[:200]
        
        # Проходим по атрибутам класса
        for node in module_class.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        attr_name = target.id
                        value = None
                        if isinstance(node.value, (ast.Str, ast.Constant)):
                            if isinstance(node.value, ast.Constant):
                                value = node.value.value
                            else:
                                value = node.value.s
                        
                        if attr_name in metadata:
                            if attr_name in ["input_ports", "output_ports", "parameters", "visual_components"]:
                                if isinstance(node.value, (ast.List, ast.Dict)):
                                    metadata[attr_name] = extract_list_or_dict_from_ast(node.value)
                            else:
                                if value:
                                    if attr_name == "version" or attr_name == "min_compatible_version":
                                        metadata[attr_name] = str(value)
                                    elif attr_name == "description":
                                        metadata[attr_name] = str(value)[:200]
                                    else:
                                        metadata[attr_name] = value
        
    except Exception as e:
        logger.debug(f"Error extracting metadata from class: {e}")
    
    return metadata


def extract_list_or_dict_from_ast(node) -> list:
    """Извлекает список или словарь из AST узла"""
    if isinstance(node, ast.List):
        result = []
        for elt in node.elts:
            if isinstance(elt, (ast.Str, ast.Constant)):
                if isinstance(elt, ast.Constant):
                    result.append(elt.value)
                else:
                    result.append(elt.s)
            elif isinstance(elt, ast.Dict):
                # Словарь в списке
                dict_item = {}
                for k, v in zip(elt.keys, elt.values):
                    key = None
                    if isinstance(k, (ast.Str, ast.Constant)):
                        if isinstance(k, ast.Constant):
                            key = k.value
                        else:
                            key = k.s
                    if key:
                        value = None
                        if isinstance(v, (ast.Str, ast.Constant)):
                            if isinstance(v, ast.Constant):
                                value = v.value
                            else:
                                value = v.s
                        dict_item[key] = value
                result.append(dict_item)
        return result
    elif isinstance(node, ast.Dict):
        result = {}
        for k, v in zip(node.keys, node.values):
            key = None
            if isinstance(k, (ast.Str, ast.Constant)):
                if isinstance(k, ast.Constant):
                    key = k.value
                else:
                    key = k.s
            if key:
                value = None
                if isinstance(v, (ast.Str, ast.Constant)):
                    if isinstance(v, ast.Constant):
                        value = v.value
                    else:
                        value = v.s
                result[key] = value
        return result
    return []


def extract_metadata_fallback(content: str, filename: str = "") -> Dict[str, Any]:
    """Извлекает метаданные из файла используя regex (fallback метод)"""
    import re
    
    metadata = {
        "name": None,
        "description": None,
        "icon": None,
        "color": None,
        "version": None,
        "min_compatible_version": None,
        "input_ports": [],
        "output_ports": [],
        "parameters": [],
        "visual_components": [],
        "visual_components": []
    }
    
    # Ищем в комментариях или docstring
    patterns = {
        "name": [
            r'name\s*[:=]\s*["\']([^"\']+)["\']',
            r'@name\s+([^\n]+)',
            r'#\s*name\s*[:=]\s*([^\n]+)',
        ],
        "description": [
            r'description\s*[:=]\s*["\']([^"\']+)["\']',
            r'@description\s+([^\n]+)',
            r'#\s*description\s*[:=]\s*([^\n]+)',
        ],
        "icon": [
            r'icon\s*[:=]\s*["\']([^"\']+)["\']',
            r'@icon\s+([^\n]+)',
            r'#\s*icon\s*[:=]\s*([^\n]+)',
        ],
        "color": [
            r'color\s*[:=]\s*["\']?([#\w]+)["\']?',
            r'@color\s+([#\w]+)',
            r'#\s*color\s*[:=]\s*([#\w]+)',
        ]
    }
    
    search_content = content[:2000]
    
    for key, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, search_content, re.IGNORECASE | re.MULTILINE)
            if match:
                metadata[key] = match.group(1).strip()
                break
    
    # Извлекаем версию
    version_info = extract_version_from_file(content, filename)
    metadata["version"] = version_info["version"]
    metadata["min_compatible_version"] = version_info["min_compatible_version"]
    
    # Если имя не найдено, используем имя файла
    if not metadata["name"] and filename:
        metadata["name"] = os.path.splitext(filename)[0]
    elif not metadata["name"]:
        metadata["name"] = "Новый модуль"
    
    # Если description не найдено, пытаемся извлечь из docstring
    if not metadata["description"]:
        docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(1).strip()
            docstring = re.sub(r'(version|min_compatible_version|name|description|icon|color)\s*[:=]\s*[^\n]+', '', docstring, flags=re.IGNORECASE)
            metadata["description"] = docstring.strip()[:200]
    
    # Значения по умолчанию
    if not metadata["icon"]:
        metadata["icon"] = "mdi-folder"
    if not metadata["color"]:
        metadata["color"] = "#1976d2"
    
    return metadata

