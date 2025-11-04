import yaml
from typing import Any, Dict, Optional
from utils.logger import config_logger as logger

from fastapi import FastAPI
import random
import string
import os
import json


def get_data_dir():
    """
    Определяет путь к директории data в зависимости от окружения.
    В Home Assistant используется /data (монтируется отдельно).
    В других случаях используется относительный путь от корня проекта.
    """
    # Проверяем, находимся ли мы в Home Assistant
    # В HA переменная SUPERVISOR_TOKEN указывает на HA окружение
    # Также проверяем наличие специфичных для HA директорий
    supervisor_token = os.environ.get('SUPERVISOR_TOKEN')
    has_hassio = os.path.exists('/usr/share/hassio')
    has_addons = os.path.exists('/addons')
    has_data = os.path.exists('/data')
    
    is_ha = (
        supervisor_token is not None or
        has_hassio or
        (has_addons and has_data)
    )
    
    if is_ha:
        # В Home Assistant используем /data (монтируется отдельно)
        data_dir = '/data'
        # В HA /data всегда должен существовать и быть смонтированным
        if not has_data:
            logger.warning("/data directory does not exist in Home Assistant environment")
    else:
        # Для локальной разработки или docker-compose используем относительный путь
        # От backend/utils/ к корню проекта: ../../data
        current_file = os.path.abspath(__file__)
        backend_dir = os.path.dirname(os.path.dirname(current_file))
        data_dir = os.path.realpath(os.path.join(backend_dir, '..', 'data'))
    
    # Создаем директорию, если её нет (только для локальной разработки)
    if not is_ha and not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create data directory {data_dir}: {e}")
    
    # Проверяем доступность директории для записи
    if os.path.exists(data_dir):
        try:
            test_file = os.path.join(data_dir, '.test_write')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.debug(f"Data directory {data_dir} is writable")
        except Exception as e:
            logger.warning(f"Data directory {data_dir} may not be writable: {e}")
            # Не падаем сразу, возможно SQLite сам справится
    else:
        logger.warning(f"Data directory {data_dir} does not exist")
        if is_ha:
            logger.error("In Home Assistant /data should always exist and be mounted!")
    
    logger.info(f"Using data directory: {data_dir} (HA: {is_ha})")
    return data_dir


# Схема конфигурации аддона для Home Assistant
# Определяет параметры, их группы, описания, типы, значения по умолчанию
ADDON_CONFIG_SCHEMA = {
    "network": {
        "name": "Сетевые настройки",
        "description": "Параметры сетевого сканирования и подключения",
        "endpoint": "/api/addon/config/network",
        "fields": {
            "local_network": {
                "type": "str",
                "name": "Локальная сеть",
                "description": "CIDR-нотация для сканирования сети (например: 192.168.0.1/24)",
                "default": "192.168.0.1/24",
                "required": True,
                "pattern": r"^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$"
            },
            "scan_timeout": {
                "type": "int",
                "name": "Таймаут сканирования",
                "description": "Время ожидания ответа от устройства при сканировании (секунды)",
                "default": 2,
                "min": 1,
                "max": 60,
                "required": True
            },
            "is_fast_scan": {
                "type": "bool",
                "name": "Быстрое сканирование",
                "description": "Использовать быстрый режим сканирования сети",
                "default": True,
                "required": True
            }
        }
    },
    "backup": {
        "name": "Настройки бэкапа",
        "description": "Параметры автоматического резервного копирования",
        "endpoint": "/api/addon/config/backup",
        "fields": {
            "save_config_hour": {
                "type": "int",
                "name": "Час сохранения конфигурации",
                "description": "Час дня для автоматического сохранения конфигурации устройств (0-23)",
                "default": 1,
                "min": 0,
                "max": 23,
                "required": True
            },
            "save_logs_period": {
                "type": "int",
                "name": "Период сохранения логов",
                "description": "Период автоматического сохранения логов (часы)",
                "default": 2,
                "min": 1,
                "max": 24,
                "required": True
            },
            "save_logs_hour": {
                "type": "int",
                "name": "Час сохранения логов",
                "description": "Час дня для автоматического сохранения логов (0-23)",
                "default": 1,
                "min": 0,
                "max": 23,
                "required": True
            }
        }
    },
    "integrations": {
        "name": "Интеграции",
        "description": "Настройки внешних сервисов",
        "endpoint": "/api/addon/config/integrations",
        "fields": {
            "gsheet": {
                "type": "str",
                "name": "Google Sheet ID",
                "description": "ID Google таблицы для сохранения логов (необязательно)",
                "default": "",
                "required": False
            }
        }
    },
    "homeassistant": {
        "name": "Home Assistant",
        "description": "Настройки интеграции с Home Assistant",
        "endpoint": "/api/addon/config/homeassistant",
        "fields": {
            "ha_url": {
                "type": "str",
                "name": "URL Home Assistant",
                "description": "URL адрес Home Assistant (например: http://homeassistant.local:8123 или http://192.168.0.1:8123)",
                "default": "homeassistant.local:8123",
                "required": True,
                "pattern": r"^(https?://)?([\w\.-]+)(:\d+)?(/.*)?$"
            },
            "ha_token": {
                "type": "str",
                "name": "Токен Home Assistant",
                "description": "Long-lived access token для доступа к Home Assistant API",
                "default": "",
                "required": False
            },
            "ha_timeout": {
                "type": "int",
                "name": "Таймаут запросов",
                "description": "Таймаут запросов к Home Assistant API (секунды)",
                "default": 30,
                "min": 5,
                "max": 300,
                "required": True
            },
            "ha_retry_attempts": {
                "type": "int",
                "name": "Количество попыток",
                "description": "Количество попыток при ошибках запросов к Home Assistant",
                "default": 3,
                "min": 1,
                "max": 10,
                "required": True
            },
            "ha_log_requests": {
                "type": "bool",
                "name": "Логировать запросы",
                "description": "Логировать все запросы к Home Assistant API",
                "default": True,
                "required": True
            },
            "ha_log_responses": {
                "type": "bool",
                "name": "Логировать ответы",
                "description": "Логировать все ответы от Home Assistant API",
                "default": False,
                "required": True
            }
        }
    },
    "logging": {
        "name": "Настройки логирования",
        "description": "Параметры уровней логирования для различных модулей системы",
        "endpoint": "/api/addon/config/logging",
        "fields": {
            "log_global_min_level": {
                "type": "select",
                "name": "Минимальный глобальный уровень",
                "description": "Минимальный уровень логирования для всех модулей",
                "default": "DEBUG",
                "required": True,
                "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "log_global_timestamps": {
                "type": "bool",
                "name": "Показывать временные метки",
                "description": "Включает отображение времени в логах",
                "default": True,
                "required": True
            },
            "log_global_icons": {
                "type": "bool",
                "name": "Показывать иконки",
                "description": "Включает отображение иконок для уровней логирования",
                "default": True,
                "required": True
            },
            "log_global_colors": {
                "type": "bool",
                "name": "Цветной вывод",
                "description": "Включает цветной вывод в консоли",
                "default": True,
                "required": True
            },
            "log_global_module_names": {
                "type": "bool",
                "name": "Показывать имена модулей",
                "description": "Включает отображение имен модулей в логах",
                "default": True,
                "required": True
            },
            "log_module_HA_Manager_level": {
                "type": "select",
                "name": "HA-Manager: Уровень",
                "description": "Уровень логирования для модуля Home Assistant Manager",
                "default": "INFO",
                "required": True,
                "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "log_module_HA_Manager_enabled": {
                "type": "bool",
                "name": "HA-Manager: Включен",
                "description": "Включает логирование для модуля Home Assistant Manager",
                "default": True,
                "required": True
            },
            "log_module_MyHome_level": {
                "type": "select",
                "name": "MyHome: Уровень",
                "description": "Уровень логирования для модуля MyHome",
                "default": "INFO",
                "required": True,
                "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "log_module_MyHome_enabled": {
                "type": "bool",
                "name": "MyHome: Включен",
                "description": "Включает логирование для модуля MyHome",
                "default": False,
                "required": True
            },
            "log_module_Database_level": {
                "type": "select",
                "name": "Database: Уровень",
                "description": "Уровень логирования для модуля Database",
                "default": "WARNING",
                "required": True,
                "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "log_module_Database_enabled": {
                "type": "bool",
                "name": "Database: Включен",
                "description": "Включает логирование для модуля Database",
                "default": False,
                "required": True
            },
            "log_module_WebSocket_level": {
                "type": "select",
                "name": "WebSocket: Уровень",
                "description": "Уровень логирования для модуля WebSocket",
                "default": "DEBUG",
                "required": True,
                "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "log_module_WebSocket_enabled": {
                "type": "bool",
                "name": "WebSocket: Включен",
                "description": "Включает логирование для модуля WebSocket",
                "default": False,
                "required": True
            },
            "log_module_API_level": {
                "type": "select",
                "name": "API: Уровень",
                "description": "Уровень логирования для модуля API",
                "default": "INFO",
                "required": True,
                "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "log_module_API_enabled": {
                "type": "bool",
                "name": "API: Включен",
                "description": "Включает логирование для модуля API",
                "default": False,
                "required": True
            },
            "log_module_Config_level": {
                "type": "select",
                "name": "Config: Уровень",
                "description": "Уровень логирования для модуля Config",
                "default": "WARNING",
                "required": True,
                "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "log_module_Config_enabled": {
                "type": "bool",
                "name": "Config: Включен",
                "description": "Включает логирование для модуля Config",
                "default": False,
                "required": True
            },
            "log_module_Device_level": {
                "type": "select",
                "name": "Device: Уровень",
                "description": "Уровень логирования для модуля Device",
                "default": "INFO",
                "required": True,
                "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "log_module_Device_enabled": {
                "type": "bool",
                "name": "Device: Включен",
                "description": "Включает логирование для модуля Device",
                "default": False,
                "required": True
            },
            "log_module_Port_level": {
                "type": "select",
                "name": "Port: Уровень",
                "description": "Уровень логирования для модуля Port",
                "default": "DEBUG",
                "required": True,
                "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "log_module_Port_enabled": {
                "type": "bool",
                "name": "Port: Включен",
                "description": "Включает логирование для модуля Port",
                "default": False,
                "required": True
            },
            "log_module_GoogleConnector_level": {
                "type": "select",
                "name": "GoogleConnector: Уровень",
                "description": "Уровень логирования для модуля GoogleConnector",
                "default": "INFO",
                "required": True,
                "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "log_module_GoogleConnector_enabled": {
                "type": "bool",
                "name": "GoogleConnector: Включен",
                "description": "Включает логирование для модуля GoogleConnector",
                "default": False,
                "required": True
            },
            "log_module_Singleton_level": {
                "type": "select",
                "name": "Singleton: Уровень",
                "description": "Уровень логирования для модуля Singleton",
                "default": "DEBUG",
                "required": True,
                "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "log_module_Singleton_enabled": {
                "type": "bool",
                "name": "Singleton: Включен",
                "description": "Включает логирование для модуля Singleton",
                "default": False,
                "required": True
            }
        }
    }
}


# Описания модулей логирования
LOGGER_MODULE_DESCRIPTIONS = {
    "HA-Manager": {
        "description": "Менеджер интеграции с Home Assistant. Управляет подключением, синхронизацией портов с базой данных, двухсторонней обработкой данных между HA и устройствами",
        "functions": [
            "Автоматическое подключение и переподключение к Home Assistant",
            "Синхронизация портов устройств с HA entities",
            "Обработка команд от HA (hard/soft control)",
            "Отправка обновлений значений портов в HA",
            "Управление жизненным циклом WebSocket соединения"
        ]
    },
    "MyHome": {
        "description": "Основной модуль управления устройствами MyHome. Отвечает за общую логику работы с устройствами, их конфигурацию и состояние",
        "functions": [
            "Управление жизненным циклом устройств",
            "Обработка конфигурации устройств",
            "Синхронизация состояния устройств",
            "Управление версиями конфигурации"
        ]
    },
    "Database": {
        "description": "Модуль работы с базой данных SQLite. Логирует операции чтения/записи, запросы и транзакции",
        "functions": [
            "Логирование SQL запросов",
            "Отслеживание операций с базой данных",
            "Мониторинг транзакций",
            "Диагностика проблем производительности БД"
        ]
    },
    "WebSocket": {
        "description": "Модуль WebSocket соединений для реального времени обмена данными между клиентом и сервером",
        "functions": [
            "Логирование подключений и отключений клиентов",
            "Отслеживание отправляемых/получаемых сообщений",
            "Мониторинг состояния соединений",
            "Диагностика проблем связи"
        ]
    },
    "API": {
        "description": "Модуль веб-API (FastAPI). Логирует HTTP запросы, ответы, ошибки и обработку маршрутов",
        "functions": [
            "Логирование HTTP запросов и ответов",
            "Отслеживание времени выполнения запросов",
            "Обработка ошибок API",
            "Мониторинг использования эндпоинтов"
        ]
    },
    "Config": {
        "description": "Модуль управления конфигурацией приложения. Логирует загрузку, сохранение и изменения конфигурационных файлов",
        "functions": [
            "Логирование операций с конфигурацией",
            "Отслеживание изменений настроек",
            "Диагностика проблем загрузки конфига",
            "Мониторинг работы с config.yaml и options.json"
        ]
    },
    "Device": {
        "description": "Модуль работы с клиентами устройств. Логирует подключение устройств, обмен данными и их состояние",
        "functions": [
            "Логирование подключений устройств",
            "Отслеживание команд и ответов от устройств",
            "Мониторинг состояния устройств",
            "Диагностика проблем связи с устройствами"
        ]
    },
    "Port": {
        "description": "Модуль работы с портами устройств. Логирует чтение/запись значений портов, их изменения и валидацию",
        "functions": [
            "Логирование изменений значений портов",
            "Отслеживание операций чтения/записи",
            "Валидация и преобразование значений",
            "Мониторинг синхронизации портов"
        ]
    },
    "GoogleConnector": {
        "description": "Модуль интеграции с Google Sheets. Логирует операции экспорта логов и данных в Google таблицы",
        "functions": [
            "Логирование операций с Google Sheets API",
            "Отслеживание экспорта данных",
            "Обработка авторизации OAuth",
            "Мониторинг синхронизации с Google"
        ]
    },
    "Singleton": {
        "description": "Модуль паттерна Singleton для управления единственными экземплярами классов. Логирует создание и использование синглтонов",
        "functions": [
            "Логирование создания экземпляров",
            "Отслеживание использования синглтонов",
            "Диагностика проблем с инициализацией"
        ]
    }
}


def get_addon_config_schema() -> Dict[str, Any]:
    """
    Получает полную схему конфигурации аддона
    Возвращает структуру с группами, полями и их метаданными
    """
    return ADDON_CONFIG_SCHEMA


def get_addon_config_defaults(ha_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Получает значения по умолчанию для всех параметров конфигурации
    
    Args:
        ha_config: Опциональный словарь с конфигурацией Home Assistant
    """
    defaults = {}
    for group_name, group_data in ADDON_CONFIG_SCHEMA.items():
        for field_name, field_data in group_data.get("fields", {}).items():
            defaults[field_name] = field_data.get("default")
    
    # Добавляем значения по умолчанию для HA из переданного конфига
    if ha_config:
        defaults['ha_url'] = ha_config.get('url', 'homeassistant.local:8123')
        defaults['ha_token'] = ha_config.get('token', '')
        defaults['ha_timeout'] = ha_config.get('timeout', 30)
        defaults['ha_retry_attempts'] = ha_config.get('retry_attempts', 3)
        defaults['ha_log_requests'] = ha_config.get('log_requests', True)
        defaults['ha_log_responses'] = ha_config.get('log_responses', False)
    
    # Добавляем текущие значения логирования из logger_config.json
    try:
        from utils.logger import get_logger_config, LogLevel
        logger_config = get_logger_config()
        
        # Глобальные настройки
        global_settings = logger_config.global_settings
        defaults['log_global_min_level'] = global_settings.get('min_global_level', LogLevel.DEBUG).value
        defaults['log_global_timestamps'] = global_settings.get('enable_timestamps', True)
        defaults['log_global_icons'] = global_settings.get('enable_icons', True)
        defaults['log_global_colors'] = global_settings.get('enable_colors', True)
        defaults['log_global_module_names'] = global_settings.get('show_module_names', True)
        
        # Настройки модулей
        module_settings = logger_config.module_settings
        for module_name in ['HA-Manager', 'MyHome', 'Database', 'WebSocket', 'API', 'Config', 'Device', 'Port', 'GoogleConnector', 'Singleton']:
            module_config = module_settings.get(module_name, {})
            level = module_config.get('level', LogLevel.INFO)
            if isinstance(level, LogLevel):
                level = level.value
            defaults[f'log_module_{module_name}_level'] = level
            defaults[f'log_module_{module_name}_enabled'] = module_config.get('enabled', False)
    except Exception as e:
        logger.warning(f"Failed to load logger defaults: {e}")
    
    return defaults


def get_addon_config_field_schema(field_key: str) -> Optional[Dict[str, Any]]:
    """
    Получает схему конкретного поля по ключу
    """
    for group_data in ADDON_CONFIG_SCHEMA.values():
        if field_key in group_data.get("fields", {}):
            field_schema = group_data["fields"][field_key].copy()
            field_schema["key"] = field_key
            field_schema["group"] = group_data.get("name", "Общие")
            return field_schema
    return None


def get_addon_config_flat_schema() -> Dict[str, Dict[str, Any]]:
    """
    Получает плоскую схему (без группировки) для совместимости со старым API
    """
    flat_schema = {}
    for group_data in ADDON_CONFIG_SCHEMA.values():
        for field_key, field_data in group_data.get("fields", {}).items():
            flat_schema[field_key] = {
                "key": field_key,
                "type": field_data.get("type", "str"),
                "name": field_data.get("name", field_key),
                "description": field_data.get("description", ""),
                "default": field_data.get("default"),
                "required": field_data.get("required", False),
                "group": group_data.get("name", "Общие")
            }
            # Добавляем дополнительные параметры
            if "min" in field_data:
                flat_schema[field_key]["min"] = field_data["min"]
            if "max" in field_data:
                flat_schema[field_key]["max"] = field_data["max"]
            if "pattern" in field_data:
                flat_schema[field_key]["pattern"] = field_data["pattern"]
            if "options" in field_data:
                flat_schema[field_key]["options"] = field_data["options"]
            # Для select полей указываем type как select
            if field_data.get("type") == "select":
                flat_schema[field_key]["type"] = "select"
    return flat_schema


def validate_addon_config_value(field_key: str, value: Any) -> tuple[bool, Optional[str]]:
    """
    Валидирует значение поля конфигурации
    Возвращает (is_valid, error_message)
    """
    field_schema = get_addon_config_field_schema(field_key)
    if not field_schema:
        return False, f"Unknown field: {field_key}"
    
    field_type = field_schema.get("type", "str")
    
    # Валидация типа
    if field_type == "int":
        try:
            int_value = int(value)
            if "min" in field_schema and int_value < field_schema["min"]:
                return False, f"Значение {int_value} меньше минимального {field_schema['min']}"
            if "max" in field_schema and int_value > field_schema["max"]:
                return False, f"Значение {int_value} больше максимального {field_schema['max']}"
        except (ValueError, TypeError):
            return False, "Должно быть числом"
    
    elif field_type == "bool":
        if not isinstance(value, bool):
            try:
                value = str(value).lower() in ("true", "1", "yes", "on")
            except:
                return False, "Должно быть логическим значением"
    
    elif field_type == "str":
        value = str(value)
        if field_schema.get("required") and not value.strip():
            return False, "Обязательное поле"
        if "pattern" in field_schema:
            import re
            if not re.match(field_schema["pattern"], value):
                return False, f"Не соответствует формату"
    
    return True, None


def get_options_path() -> str:
    """
    Получает путь к options.json (файл конфигурации аддона в Home Assistant)
    """
    data_dir = get_data_dir()
    return os.path.join(data_dir, 'options.json')


class AppConfig:
  _config: dict = {}
  _need_save: bool = False

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

  def __init__(self, config_path: str = None):
    # Используем универсальную функцию для определения пути к data
    config_dir = get_data_dir()
    
    # Обновляем URL базы данных в зависимости от окружения
    db_path = os.path.join(config_dir, 'sql_app.db')
    
    # Убеждаемся, что директория существует и доступна для записи
    try:
      if not os.path.exists(config_dir):
        logger.warning(f"Data directory {config_dir} does not exist, creating...")
        os.makedirs(config_dir, mode=0o755, exist_ok=True)
      
      # Проверяем доступность директории для записи
      test_file = os.path.join(config_dir, '.db_write_test')
      try:
        with open(test_file, 'w') as f:
          f.write('test')
        os.remove(test_file)
        logger.debug(f"Data directory {config_dir} is writable")
      except Exception as e:
        logger.error(f"Data directory {config_dir} is not writable: {e}")
        raise
      
      # SQLite требует специального формата для абсолютных путей:
      # - sqlite:///relative/path (3 слэша) - относительный путь
      # - sqlite:////absolute/path (4 слэша) - абсолютный путь на Unix/Linux
      # - sqlite:///C:/path (3 слэша) - абсолютный путь на Windows
      if os.path.isabs(db_path):
        # Для абсолютного пути используем 4 слэша
        if db_path.startswith('/'):
          db_url = f'sqlite:////{db_path}'
        else:
          # Windows путь
          db_url = f'sqlite:///{db_path}'
      else:
        # Для относительного пути используем 3 слэша
        db_url = f'sqlite:///{db_path}'
      
      self.default_config['db']['url'] = db_url
      logger.info(f"=== Database Configuration ===")
      logger.info(f"Config directory: {config_dir}")
      logger.info(f"Database path: {db_path}")
      logger.info(f"Database URL: {db_url}")
      logger.info(f"Database file exists: {os.path.exists(db_path)}")
      logger.info(f"Directory writable: {os.access(config_dir, os.W_OK)}")
      logger.info(f"Directory permissions: {oct(os.stat(config_dir).st_mode) if os.path.exists(config_dir) else 'N/A'}")
      logger.info(f"================================")
      
    except Exception as e:
      logger.error(f"Error configuring database path: {e}")
      raise
    if config_path is None:
      config_path = os.path.join(config_dir, 'config.yaml')
    self._config_path = config_path
    self._config = self._load_yaml()
    self._config.update(self._load_json())
    
    # ВАЖНО: Устанавливаем правильный URL базы данных ДО _test_config
    # чтобы избежать перезаписи из default_config
    if 'db' not in self._config:
      self._config['db'] = {}
    self._config['db']['url'] = db_url
    
    self._test_config()
    
    # ВАЖНО: После _test_config принудительно обновляем URL базы данных еще раз
    # чтобы гарантировать использование правильного пути (/data в HA)
    # даже если в сохраненном конфиге был старый путь
    self._config['db']['url'] = db_url
    logger.info(f"Database URL forced to: {db_url} (after config load and test)")
    
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
    root_default = root_default or self.default_config
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
