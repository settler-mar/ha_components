"""
Глобальный логгер для всего проекта с цветным выводом и временными метками
"""
import sys
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel
from fastapi import APIRouter


class LogLevel(Enum):
  """Уровни логирования"""
  DEBUG = "DEBUG"
  INFO = "INFO"
  WARNING = "WARNING"
  ERROR = "ERROR"
  CRITICAL = "CRITICAL"
  SUCCESS = "SUCCESS"

  @property
  def icon(self) -> str:
    """Получить иконку для уровня логирования"""
    icon_map = {
      LogLevel.DEBUG: "🔍",
      LogLevel.INFO: "ℹ️",
      LogLevel.WARNING: "⚠️",
      LogLevel.ERROR: "❌",
      LogLevel.CRITICAL: "🚨",
      LogLevel.SUCCESS: "✅"
    }
    return icon_map.get(self, "📝")


class Colors:
  """Цвета для консольного вывода"""
  RED = '\033[91m'
  GREEN = '\033[92m'
  YELLOW = '\033[93m'
  BLUE = '\033[94m'
  MAGENTA = '\033[95m'
  CYAN = '\033[96m'
  WHITE = '\033[97m'
  BOLD = '\033[1m'
  UNDERLINE = '\033[4m'
  END = '\033[0m'


class ProjectLogger:
  """Глобальный логгер для всего проекта"""

  def __init__(self, module_name: str = "Project", enable_colors: bool = True, min_level: LogLevel = LogLevel.INFO):
    self.module_name = module_name
    self.enable_colors = enable_colors and sys.stdout.isatty()
    self.min_level = min_level
    self.level_priority = {
      LogLevel.DEBUG: 0,
      LogLevel.INFO: 1,
      LogLevel.WARNING: 2,
      LogLevel.ERROR: 3,
      LogLevel.CRITICAL: 4,
      LogLevel.SUCCESS: 1
    }
    self._config = LoggerConfig()

  def _get_timestamp(self) -> str:
    """Получить текущее время в формате HH:MM:SS.mmm"""
    return datetime.now().strftime('%H:%M:%S.%f')[:-3]

  def _get_color(self, level: LogLevel) -> str:
    """Получить цвет для уровня логирования"""
    if not self.enable_colors:
      return ""

    color_map = {
      LogLevel.DEBUG: Colors.BLUE,
      LogLevel.INFO: Colors.GREEN,
      LogLevel.WARNING: Colors.YELLOW,
      LogLevel.ERROR: Colors.RED,
      LogLevel.CRITICAL: Colors.BOLD + Colors.RED,
      LogLevel.SUCCESS: Colors.BOLD + Colors.GREEN
    }
    return color_map.get(level, Colors.WHITE)

  def _format_message(self, level: LogLevel, message: str) -> str:
    """Форматировать сообщение с временной меткой, иконкой и цветом"""
    # Проверяем, включен ли модуль
    module_config = self._config.get_module_config(self.module_name)
    if not module_config.get("enabled", True):
      return ""

    # Проверяем уровень логирования
    if self.level_priority[level] < self.level_priority[self.min_level]:
      return ""

    # Проверяем глобальный минимальный уровень
    global_min_level = self._config.get_global_setting("min_global_level")
    if global_min_level and self.level_priority[level] < self.level_priority[global_min_level]:
      return ""

    # Формируем сообщение
    parts = []

    # Временная метка
    if self._config.get_global_setting("enable_timestamps"):
      timestamp = self._get_timestamp()
      if self.enable_colors:
        parts.append(f"{Colors.CYAN}[{timestamp}]{Colors.END}")
      else:
        parts.append(f"[{timestamp}]")

    # Иконка и уровень
    if self._config.get_global_setting("enable_icons"):
      icon = level.icon
    else:
      icon = ""

    color = self._get_color(level) if self.enable_colors else ""
    reset = Colors.END if self.enable_colors else ""

    if self.enable_colors:
      parts.append(f"{color}{icon} {level.value}{reset}")
    else:
      parts.append(f"{icon} {level.value}")

    # Имя модуля
    if self._config.get_global_setting("show_module_names"):
      if self.enable_colors:
        parts.append(f"{Colors.BLUE}[{self.module_name}]{Colors.END}")
      else:
        parts.append(f"[{self.module_name}]")

    # Сообщение
    parts.append(message)

    return " ".join(parts)

  def _log(self, level: LogLevel, message: str):
    """Базовый метод логирования"""
    formatted_message = self._format_message(level, message)
    if formatted_message:
      print(formatted_message)

  def debug(self, message: str):
    """Отладочное сообщение (синий)"""
    self._log(LogLevel.DEBUG, message)

  def info(self, message: str):
    """Информационное сообщение (зеленый)"""
    self._log(LogLevel.INFO, message)

  def warning(self, message: str):
    """Предупреждение (желтый)"""
    self._log(LogLevel.WARNING, message)

  def error(self, message: str):
    """Ошибка (красный)"""
    self._log(LogLevel.ERROR, message)

  def critical(self, message: str):
    """Критическая ошибка (жирный красный)"""
    self._log(LogLevel.CRITICAL, message)

  def success(self, message: str):
    """Успешное действие (жирный зеленый)"""
    self._log(LogLevel.SUCCESS, message)

  def set_level(self, level: LogLevel):
    """Установить минимальный уровень логирования"""
    self.min_level = level

  def set_colors(self, enable: bool):
    """Включить/выключить цветной вывод"""
    self.enable_colors = enable and sys.stdout.isatty()

  def set_module_name(self, name: str):
    """Установить имя модуля"""
    self.module_name = name

  def update_config(self):
    """Обновить конфигурацию логгера из глобальных настроек"""
    module_config = self._config.get_module_config(self.module_name)
    self.min_level = module_config.get("level", self.min_level)
    self.enable_colors = module_config.get("colors", self.enable_colors) and sys.stdout.isatty()

  def is_enabled(self) -> bool:
    """Проверить, включен ли логгер для этого модуля"""
    module_config = self._config.get_module_config(self.module_name)
    return module_config.get("enabled", True)


# Глобальные настройки логгера
class LoggerConfig:
  """Конфигурация глобального логгера с возможностью сохранения"""

  # Путь к файлу конфигурации
  CONFIG_FILE = "logger_config.json"

  # Настройки по умолчанию
  DEFAULT_LEVEL = LogLevel.INFO
  DEFAULT_COLORS = True
  DEFAULT_MODULE = "Project"

  # Настройки для разных модулей по умолчанию
  DEFAULT_MODULE_SETTINGS = {
    "HA-Manager": {"level": LogLevel.INFO, "colors": True, "enabled": True},
    "MyHome": {"level": LogLevel.INFO, "colors": True, "enabled": False},
    "Database": {"level": LogLevel.WARNING, "colors": True, "enabled": False},
    "WebSocket": {"level": LogLevel.DEBUG, "colors": True, "enabled": False},
    "API": {"level": LogLevel.INFO, "colors": True, "enabled": False},
    "Config": {"level": LogLevel.WARNING, "colors": True, "enabled": False},
    "Device": {"level": LogLevel.INFO, "colors": True, "enabled": False},
    "Port": {"level": LogLevel.DEBUG, "colors": True, "enabled": False},
    "GoogleConnector": {"level": LogLevel.INFO, "colors": True, "enabled": False},
    "Singleton": {"level": LogLevel.DEBUG, "colors": True, "enabled": False},
  }

  # Глобальные настройки по умолчанию
  DEFAULT_GLOBAL_SETTINGS = {
    "enable_timestamps": True,
    "enable_icons": True,
    "enable_colors": True,
    "show_module_names": True,
    "min_global_level": LogLevel.DEBUG
  }

  def __init__(self):
    """Инициализация конфигурации"""
    self.module_settings = self.DEFAULT_MODULE_SETTINGS.copy()
    self.global_settings = self.DEFAULT_GLOBAL_SETTINGS.copy()
    self.load_config()

  def load_config(self):
    """Загрузить конфигурацию из файла"""
    try:
      if os.path.exists(self.CONFIG_FILE):
        with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
          config_data = json.load(f)

        # Загружаем настройки модулей
        if 'module_settings' in config_data:
          for module, settings in config_data['module_settings'].items():
            if module in self.module_settings:
              # Преобразуем строковые уровни обратно в enum
              if 'level' in settings and isinstance(settings['level'], str):
                try:
                  settings['level'] = LogLevel(settings['level'])
                except ValueError:
                  settings['level'] = self.DEFAULT_LEVEL
              self.module_settings[module].update(settings)

        # Загружаем глобальные настройки
        if 'global_settings' in config_data:
          for key, value in config_data['global_settings'].items():
            if key in self.global_settings:
              # Преобразуем строковые уровни обратно в enum
              if key == 'min_global_level' and isinstance(value, str):
                try:
                  value = LogLevel(value)
                except ValueError:
                  value = self.DEFAULT_LEVEL
              self.global_settings[key] = value
    except Exception as e:
      print(f"Error loading logger config: {e}")

  def save_config(self):
    """Сохранить конфигурацию в файл"""
    try:
      config_data = {
        'module_settings': {},
        'global_settings': {}
      }

      # Сохраняем настройки модулей
      for module, settings in self.module_settings.items():
        config_data['module_settings'][module] = {}
        for key, value in settings.items():
          if isinstance(value, LogLevel):
            config_data['module_settings'][module][key] = value.value
          else:
            config_data['module_settings'][module][key] = value

      # Сохраняем глобальные настройки
      for key, value in self.global_settings.items():
        if isinstance(value, LogLevel):
          config_data['global_settings'][key] = value.value
        else:
          config_data['global_settings'][key] = value

      with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
      print(f"Error saving logger config: {e}")

  def reset_to_defaults(self):
    """Сбросить конфигурацию к значениям по умолчанию"""
    self.module_settings = self.DEFAULT_MODULE_SETTINGS.copy()
    self.global_settings = self.DEFAULT_GLOBAL_SETTINGS.copy()
    self.save_config()

  def get_module_config(self, module_name: str) -> Dict[str, Any]:
    """Получить конфигурацию для модуля"""
    return self.module_settings.get(module_name, {
      "level": self.DEFAULT_LEVEL,
      "colors": self.DEFAULT_COLORS,
      "enabled": True
    })

  def set_module_level(self, module_name: str, level: LogLevel):
    """Установить уровень логирования для модуля"""
    if module_name not in self.module_settings:
      self.module_settings[module_name] = {"level": level, "colors": True, "enabled": True}
    else:
      self.module_settings[module_name]["level"] = level
    self.save_config()

  def set_module_colors(self, module_name: str, enabled: bool):
    """Включить/выключить цвета для модуля"""
    if module_name not in self.module_settings:
      self.module_settings[module_name] = {"level": self.DEFAULT_LEVEL, "colors": enabled, "enabled": True}
    else:
      self.module_settings[module_name]["colors"] = enabled
    self.save_config()

  def set_module_enabled(self, module_name: str, enabled: bool):
    """Включить/выключить логирование для модуля"""
    if module_name not in self.module_settings:
      self.module_settings[module_name] = {"level": self.DEFAULT_LEVEL, "colors": True, "enabled": enabled}
    else:
      self.module_settings[module_name]["enabled"] = enabled
    self.save_config()

  def set_global_setting(self, setting: str, value: Any):
    """Установить глобальную настройку"""
    if setting in self.global_settings:
      self.global_settings[setting] = value
      self.save_config()

  def get_global_setting(self, setting: str) -> Any:
    """Получить глобальную настройку"""
    return self.global_settings.get(setting)

  def list_modules(self) -> list:
    """Получить список всех модулей"""
    return list(self.module_settings.keys())

  def get_module_status(self, module_name: str) -> Dict[str, Any]:
    """Получить статус модуля"""
    config = self.get_module_config(module_name)
    return {
      "module": module_name,
      "level": config["level"].value,
      "colors": config["colors"],
      "enabled": config["enabled"]
    }

  def get_all_status(self) -> Dict[str, Dict[str, Any]]:
    """Получить статус всех модулей"""
    return {module: self.get_module_status(module) for module in self.list_modules()}


def get_logger(module_name: str) -> ProjectLogger:
  """Получить логгер для модуля с предустановленной конфигурацией"""
  config = _global_config.get_module_config(module_name)
  logger = ProjectLogger(
    module_name=module_name,
    enable_colors=config["colors"],
    min_level=config["level"]
  )
  return logger


# Создаем глобальный экземпляр конфигурации
_global_config = LoggerConfig()

# Создаем глобальные логгеры для основных модулей
ha_logger = get_logger("HA-Manager")
myhome_logger = get_logger("MyHome")
db_logger = get_logger("Database")
ws_logger = get_logger("WebSocket")
api_logger = get_logger("API")
config_logger = get_logger("Config")
device_logger = get_logger("Device")
port_logger = get_logger("Port")
virtual_ports_logger = get_logger("VirtualPorts")


# Функции для управления логгерами
def update_all_loggers():
  """Обновить все глобальные логгеры"""
  global ha_logger, myhome_logger, db_logger, ws_logger, api_logger, config_logger, device_logger, port_logger, virtual_ports_logger
  ha_logger.update_config()
  myhome_logger.update_config()
  db_logger.update_config()
  ws_logger.update_config()
  api_logger.update_config()
  config_logger.update_config()
  device_logger.update_config()
  port_logger.update_config()
  virtual_ports_logger.update_config()


def set_module_level(module_name: str, level: LogLevel):
  """Установить уровень логирования для модуля"""
  _global_config.set_module_level(module_name, level)
  update_all_loggers()


def set_module_colors(module_name: str, enabled: bool):
  """Включить/выключить цвета для модуля"""
  _global_config.set_module_colors(module_name, enabled)
  update_all_loggers()


def set_module_enabled(module_name: str, enabled: bool):
  """Включить/выключить логирование для модуля"""
  _global_config.set_module_enabled(module_name, enabled)
  update_all_loggers()


def set_global_setting(setting: str, value: Any):
  """Установить глобальную настройку"""
  _global_config.set_global_setting(setting, value)
  update_all_loggers()


def get_logger_status():
  """Получить статус всех логгеров"""
  return _global_config.get_all_status()


def print_logger_status():
  """Вывести статус всех логгеров"""
  status = get_logger_status()
  print("\n📊 Logger Status:")
  print("=" * 60)
  for module, config in status.items():
    enabled_icon = "✅" if config["enabled"] else "❌"
    color_icon = "🎨" if config["colors"] else "⚫"
    print(f"{enabled_icon} {color_icon} {module:15} | Level: {config['level']:8} | Colors: {config['colors']}")
  print("=" * 60)


def reset_logger_config():
  """Сбросить конфигурацию логгера к значениям по умолчанию"""
  _global_config.reset_to_defaults()
  update_all_loggers()


def get_logger_config():
  """Получить объект конфигурации логгера"""
  return _global_config


# Pydantic модели для API


class ModuleLevelRequest(BaseModel):
  module: str
  level: str


class ModuleColorsRequest(BaseModel):
  module: str
  enabled: bool


class ModuleEnabledRequest(BaseModel):
  module: str
  enabled: bool


class GlobalSettingRequest(BaseModel):
  setting: str
  value: Union[str, bool, int, float]


def add_logger_routes(app: APIRouter):
  """Добавить API маршруты для управления логгером"""
  
  @app.get("/api/logger/status", tags=["logger"])
  async def get_logger_status_api():
    """Получить статус всех логгеров"""
    return get_logger_status()

  @app.post("/api/logger/module/level", tags=["logger"])
  async def set_module_level_api(request: ModuleLevelRequest):
    """Установить уровень логирования для модуля"""
    try:
      level_enum = LogLevel(request.level.upper())
      set_module_level(request.module, level_enum)
      api_logger.info(f"Set module {request.module} level to {request.level}")
      return {"success": True, "message": f"Module {request.module} level set to {request.level}"}
    except ValueError:
      return {"success": False, "message": f"Invalid level: {request.level}"}
    except Exception as e:
      api_logger.error(f"Error setting module level: {e}")
      return {"success": False, "message": str(e)}

  @app.post("/api/logger/module/colors", tags=["logger"])
  async def set_module_colors_api(request: ModuleColorsRequest):
    """Включить/выключить цвета для модуля"""
    try:
      set_module_colors(request.module, request.enabled)
      api_logger.info(f"Set module {request.module} colors to {request.enabled}")
      return {"success": True, "message": f"Module {request.module} colors set to {request.enabled}"}
    except Exception as e:
      api_logger.error(f"Error setting module colors: {e}")
      return {"success": False, "message": str(e)}

  @app.post("/api/logger/module/enabled", tags=["logger"])
  async def set_module_enabled_api(request: ModuleEnabledRequest):
    """Включить/выключить логирование для модуля"""
    try:
      set_module_enabled(request.module, request.enabled)
      api_logger.info(f"Set module {request.module} enabled to {request.enabled}")
      return {"success": True, "message": f"Module {request.module} enabled set to {request.enabled}"}
    except Exception as e:
      api_logger.error(f"Error setting module enabled: {e}")
      return {"success": False, "message": str(e)}

  @app.post("/api/logger/global/setting", tags=["logger"])
  async def set_global_setting_api(request: GlobalSettingRequest):
    """Установить глобальную настройку"""
    try:
      set_global_setting(request.setting, request.value)
      api_logger.info(f"Set global setting {request.setting} to {request.value}")
      return {"success": True, "message": f"Global setting {request.setting} set to {request.value}"}
    except Exception as e:
      api_logger.error(f"Error setting global setting: {e}")
      return {"success": False, "message": str(e)}

  @app.post("/api/logger/reset", tags=["logger"])
  async def reset_logger_config_api():
    """Сбросить конфигурацию логгера к значениям по умолчанию"""
    try:
      reset_logger_config()
      api_logger.info("Logger configuration reset to defaults")
      return {"success": True, "message": "Logger configuration reset to defaults"}
    except Exception as e:
      api_logger.error(f"Error resetting logger config: {e}")
      return {"success": False, "message": str(e)}


# Экспортируем основные логгеры
__all__ = [
  'ProjectLogger', 'LoggerConfig', 'LogLevel', 'Colors',
  'get_logger', 'ha_logger', 'myhome_logger', 'db_logger',
  'ws_logger', 'api_logger', 'config_logger', 'device_logger', 'port_logger',
  'update_all_loggers', 'set_module_level', 'set_module_colors', 'set_module_enabled',
  'set_global_setting', 'get_logger_status', 'print_logger_status',
  'reset_logger_config', 'get_logger_config', 'add_logger_routes'
]
