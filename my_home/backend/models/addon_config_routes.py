"""
API endpoints for Home Assistant addon configuration (options.json)
"""
import os
import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Dict, Any, Optional
from utils.logger import api_logger as logger
from utils.configs import (
    get_options_path,
    get_addon_config_schema,
    get_addon_config_defaults,
    get_addon_config_flat_schema,
    validate_addon_config_value,
    config
)


def get_redirect_uri(request: Request) -> str:
    """
    Определяет правильный redirect URI на основе контекста запроса
    """
    # Получаем базовый URL из заголовков или URL запроса
    # Используем X-Forwarded-Proto и X-Forwarded-Host для определения реального URL
    scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme) or "http"
    host = request.headers.get("X-Forwarded-Host", request.url.hostname) or request.url.hostname
    
    # Проверяем порт из заголовков или URL
    forwarded_port = request.headers.get("X-Forwarded-Port")
    if forwarded_port:
        port = int(forwarded_port)
    else:
        port = request.url.port
    
    # Проверяем, находимся ли мы в Home Assistant ingress
    path = request.url.path
    is_ha_ingress = '/hassio/ingress/' in path or '/api/hassio_ingress/' in path
    
    if is_ha_ingress:
        # Для HA используем ingress путь
        if '/hassio/ingress/' in path:
            # Старый формат: /hassio/ingress/local_my_home_devices/...
            parts = path.split('/hassio/ingress/')
            if len(parts) > 1:
                addon_slug = parts[1].split('/')[0]
                # Формируем redirect URI для HA
                base_url = f"{scheme}://{host}"
                if port and port not in (80, 443):
                    base_url += f":{port}"
                redirect_uri = f"{base_url}/hassio/ingress/{addon_slug}/api/addon/config/google-auth/callback"
            else:
                base_url = f"{scheme}://{host}"
                if port and port not in (80, 443):
                    base_url += f":{port}"
                redirect_uri = f"{base_url}/api/addon/config/google-auth/callback"
        else:
            # Новый формат: /api/hassio_ingress/{token}/...
            # Извлекаем токен из пути для сохранения в redirect_uri
            parts = path.split('/api/hassio_ingress/')
            if len(parts) > 1:
                token = parts[1].split('/')[0]
                base_url = f"{scheme}://{host}"
                if port and port not in (80, 443):
                    base_url += f":{port}"
                redirect_uri = f"{base_url}/api/hassio_ingress/{token}/api/addon/config/google-auth/callback"
            else:
                base_url = f"{scheme}://{host}"
                if port and port not in (80, 443):
                    base_url += f":{port}"
                redirect_uri = f"{base_url}/api/addon/config/google-auth/callback"
    else:
        # Для локальной разработки используем localhost
        if port:
            redirect_uri = f"http://127.0.0.1:{port}/api/addon/config/google-auth/callback"
        else:
            redirect_uri = f"http://127.0.0.1:8081/api/addon/config/google-auth/callback"
    
    logger.info(f"Determined redirect_uri: {redirect_uri} (is_ha_ingress: {is_ha_ingress}, path: {path}, host: {host}, port: {port})")
    return redirect_uri


def add_addon_config_routes(app: APIRouter):
    """Добавляет маршруты для работы с конфигурацией аддона"""
    
    @app.get("/api/addon/config/schema", tags=["addon-config"])
    async def get_schema():
        """Получение схемы конфигурации аддона"""
        try:
            # Возвращаем плоскую схему для совместимости с фронтендом
            flat_schema = get_addon_config_flat_schema()
            
            # Получаем HA конфиг для дефолтных значений
            ha_config = config._config.get('homeassistant', {}) if hasattr(config, '_config') else {}
            defaults = get_addon_config_defaults(ha_config)
            
            from utils.configs import LOGGER_MODULE_DESCRIPTIONS
            return {
                "schema": flat_schema,
                "defaults": defaults,
                "groups": get_addon_config_schema(),  # Полная схема с группами
                "logger_module_descriptions": LOGGER_MODULE_DESCRIPTIONS
            }
        except Exception as e:
            logger.error(f"Error getting addon config schema: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/addon/config/schema/groups", tags=["addon-config"])
    async def get_addon_config_schema_groups():
        """Получение схемы конфигурации с группировкой"""
        try:
            from utils.configs import LOGGER_MODULE_DESCRIPTIONS
            return {
                "schema": get_addon_config_schema(),
                "defaults": get_addon_config_defaults(),
                "logger_module_descriptions": LOGGER_MODULE_DESCRIPTIONS
            }
        except Exception as e:
            logger.error(f"Error getting addon config schema groups: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/addon/config/options", tags=["addon-config"])
    async def get_addon_options():
        """Получение текущих опций аддона из options.json и config.yaml"""
        try:
            options_path = get_options_path()
            
            # Загружаем опции из options.json
            if os.path.exists(options_path):
                with open(options_path, 'r', encoding='utf-8') as f:
                    options = json.load(f)
            else:
                # Если файла нет, возвращаем значения по умолчанию из configs.py
                ha_config = config._config.get('homeassistant', {}) if hasattr(config, '_config') else {}
                options = get_addon_config_defaults(ha_config)
            
            # Добавляем параметры Home Assistant из config.yaml
            ha_config = config._config.get('homeassistant', {}) if hasattr(config, '_config') else {}
            if ha_config:
                options['ha_url'] = ha_config.get('url', 'homeassistant.local:8123')
                options['ha_token'] = ha_config.get('token', '')
                options['ha_timeout'] = ha_config.get('timeout', 30)
                options['ha_retry_attempts'] = ha_config.get('retry_attempts', 3)
                options['ha_log_requests'] = ha_config.get('log_requests', True)
                options['ha_log_responses'] = ha_config.get('log_responses', False)
            
            # Добавляем текущие значения логирования из logger_config.json
            try:
                from utils.logger import get_logger_config, LogLevel
                logger_config = get_logger_config()
                
                # Глобальные настройки
                global_settings = logger_config.global_settings
                min_level = global_settings.get('min_global_level', LogLevel.DEBUG)
                if isinstance(min_level, LogLevel):
                    min_level = min_level.value
                else:
                    min_level = str(min_level) if min_level else 'DEBUG'
                options['log_global_min_level'] = min_level
                options['log_global_timestamps'] = global_settings.get('enable_timestamps', True)
                options['log_global_icons'] = global_settings.get('enable_icons', True)
                options['log_global_colors'] = global_settings.get('enable_colors', True)
                options['log_global_module_names'] = global_settings.get('show_module_names', True)
                
                # Настройки модулей
                module_settings = logger_config.module_settings
                for module_name in ['HA-Manager', 'MyHome', 'Database', 'WebSocket', 'API', 'Config', 'Device', 'Port', 'GoogleConnector', 'Singleton']:
                    module_config = module_settings.get(module_name, {})
                    level = module_config.get('level', LogLevel.INFO)
                    if isinstance(level, LogLevel):
                        level = level.value
                    options[f'log_module_{module_name}_level'] = level
                    options[f'log_module_{module_name}_enabled'] = module_config.get('enabled', False)
            except Exception as e:
                logger.warning(f"Failed to load logger options: {e}")
            
            return {
                "success": True,
                "options": options
            }
        except Exception as e:
            logger.error(f"Error getting addon options: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/addon/config/options", tags=["addon-config"])
    async def save_addon_options(options_data: Dict[str, Any]):
        """Сохранение опций аддона в options.json"""
        try:
            # Получаем плоскую схему для валидации
            flat_schema = get_addon_config_flat_schema()
            
            # Валидируем и очищаем данные
            validated_options = {}
            for key, value in options_data.items():
                # Валидируем только известные поля из схемы
                if key in flat_schema:
                    is_valid, error_msg = validate_addon_config_value(key, value)
                    if not is_valid:
                        raise HTTPException(
                            status_code=400,
                            detail=f"{key}: {error_msg}"
                        )
                    
                    # Приводим к нужному типу
                    field_type = flat_schema[key].get('type', 'str')
                    if field_type == 'int':
                        value = int(value)
                    elif field_type == 'bool':
                        value = bool(value) if isinstance(value, bool) else str(value).lower() in ('true', '1', 'yes', 'on')
                    elif field_type == 'select':
                        # Для select просто оставляем строку
                        value = str(value)
                    elif field_type == 'str':
                        value = str(value)
                    
                    validated_options[key] = value
                else:
                    # Разрешаем сохранять дополнительные поля (для совместимости)
                    validated_options[key] = value
            
            # Обрабатываем поле gsheet - извлекаем ID из URL если это URL
            if 'gsheet' in validated_options and validated_options['gsheet']:
                gsheet_value = validated_options['gsheet'].strip()
                if gsheet_value:
                    # Извлекаем ID из URL Google таблицы
                    # Формат: https://docs.google.com/spreadsheets/d/{ID}/edit...
                    if '/spreadsheets/d/' in gsheet_value:
                        try:
                            # Извлекаем ID из URL
                            parts = gsheet_value.split('/spreadsheets/d/')
                            if len(parts) > 1:
                                spreadsheet_id = parts[1].split('/')[0].split('?')[0].split('#')[0]
                                validated_options['gsheet'] = spreadsheet_id
                                logger.info(f"Extracted Google Sheet ID from URL: {spreadsheet_id}")
                        except Exception as e:
                            logger.warning(f"Failed to extract ID from Google Sheet URL: {e}")
                    # Если это просто ID, оставляем как есть
                    elif len(gsheet_value) > 20 and '/' not in gsheet_value:
                        # Похоже на ID (длинная строка без слешей)
                        validated_options['gsheet'] = gsheet_value
                    # Если есть слеши, но не наш формат - возможно неправильный URL
                    elif '/' in gsheet_value:
                        logger.warning(f"Google Sheet value looks like URL but format is unexpected: {gsheet_value}")
            
            # Разделяем опции на аддон-опции, HA-конфигурацию и настройки логирования
            addon_options = {}
            ha_options = {}
            logger_options = {}
                   
            for key, value in validated_options.items():
                if key.startswith('ha_'):
                    # Параметры HA сохраняем в config.yaml
                    ha_key = key.replace('ha_', '')
                    ha_options[ha_key] = value
                elif key.startswith('log_'):
                    # Параметры логирования сохраняем отдельно и применяем к logger
                    logger_options[key] = value
                else:
                    # Остальные опции сохраняем в options.json
                    addon_options[key] = value
            
            # Применяем настройки логирования
            if logger_options:
                try:
                    from utils.logger import get_logger_config, LogLevel, set_module_level, set_module_enabled, set_global_setting
                    logger_config = get_logger_config()
                    
                    # Применяем глобальные настройки
                    if 'log_global_min_level' in logger_options:
                        level = LogLevel(logger_options['log_global_min_level'])
                        set_global_setting('min_global_level', level)
                    
                    if 'log_global_timestamps' in logger_options:
                        set_global_setting('enable_timestamps', logger_options['log_global_timestamps'])
                    
                    if 'log_global_icons' in logger_options:
                        set_global_setting('enable_icons', logger_options['log_global_icons'])
                    
                    if 'log_global_colors' in logger_options:
                        set_global_setting('enable_colors', logger_options['log_global_colors'])
                    
                    if 'log_global_module_names' in logger_options:
                        set_global_setting('show_module_names', logger_options['log_global_module_names'])
                    
                    # Применяем настройки модулей
                    module_names = ['HA-Manager', 'MyHome', 'Database', 'WebSocket', 'API', 'Config', 'Device', 'Port', 'GoogleConnector', 'Singleton']
                    for module_name in module_names:
                        level_key = f'log_module_{module_name}_level'
                        enabled_key = f'log_module_{module_name}_enabled'
                        
                        if level_key in logger_options:
                            level = LogLevel(logger_options[level_key])
                            set_module_level(module_name, level)
                        
                        if enabled_key in logger_options:
                            set_module_enabled(module_name, logger_options[enabled_key])
                    
                    logger.info("Logger configuration updated from addon config")
                except Exception as e:
                    logger.warning(f"Failed to apply logger settings: {e}")
            
            # Сохраняем опции аддона в options.json
            options_path = get_options_path()
            data_dir = os.path.dirname(options_path)
            
            # Создаем директорию, если её нет
            if not os.path.exists(data_dir):
                os.makedirs(data_dir, mode=0o755, exist_ok=True)
            
            # Сохраняем опции аддона
            with open(options_path, 'w', encoding='utf-8') as f:
                json.dump(addon_options, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Addon options saved to {options_path}")

            # Применяем обычные настройки сразу, без перезапуска процесса.
            # Сканер устройств использует этот же объект конфигурации.
            config._config.update(addon_options)
            if 'local_network' in addon_options:
                # Совместимость со старым ключом, который использовали
                # предыдущие версии сканера.
                config._config['local_networks'] = addon_options['local_network']
            
            # Сохраняем параметры HA в config.yaml
            if ha_options:
                if 'homeassistant' not in config._config:
                    config._config['homeassistant'] = {}
                
                # Запоминаем старые значения для проверки изменений
                old_url = config._config['homeassistant'].get('url')
                old_token = config._config['homeassistant'].get('token')
                
                # Обновляем параметры HA
                ha_mapping = {
                    'url': 'url',
                    'token': 'token',
                    'timeout': 'timeout',
                    'retry_attempts': 'retry_attempts',
                    'log_requests': 'log_requests',
                    'log_responses': 'log_responses'
                }
                
                for ha_key, config_key in ha_mapping.items():
                    if ha_key in ha_options:
                        config._config['homeassistant'][config_key] = ha_options[ha_key]
                
                config.save_yaml()
                logger.info("Home Assistant configuration saved to config.yaml")
                
                # Переподключаемся к WebSocket если изменился URL или токен
                new_url = config._config['homeassistant'].get('url')
                new_token = config._config['homeassistant'].get('token')
                
                if (old_url != new_url or old_token != new_token):
                    try:
                        from utils.home_assistant import ha_websocket
                        import asyncio
                        # Пытаемся переподключиться (если WebSocket инициализирован)
                        if hasattr(ha_websocket, 'disconnect'):
                            asyncio.create_task(ha_websocket.disconnect())
                        if hasattr(ha_websocket, 'connect'):
                            asyncio.create_task(ha_websocket.connect())
                        logger.info("Home Assistant WebSocket reconnection triggered")
                    except Exception as e:
                        logger.warning(f"Could not reconnect HA WebSocket: {e}")
            
            # Объединяем все опции для ответа
            all_options = {**addon_options, **validated_options}
            
            return {
                "success": True,
                "message": "Configuration saved successfully",
                "options": all_options
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error saving addon options: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/addon/config/homeassistant/test-host", tags=["addon-config"])
    async def test_ha_host(ha_url: str = Query(..., description="URL Home Assistant для проверки")):
        """Проверка доступности хоста Home Assistant"""
        try:
            import socket
            
            # Парсим URL (убираем протокол, извлекаем хост и порт)
            url = ha_url.strip()
            if url.startswith('http://'):
                url = url[7:]
            elif url.startswith('https://'):
                url = url[8:]
            
            # Разделяем на хост и порт
            if ':' in url:
                host, port_str = url.split(':', 1)
                try:
                    port = int(port_str)
                except ValueError:
                    return {
                        "success": False,
                        "error": f"Неверный формат порта: {port_str}"
                    }
            else:
                host = url
                port = 8123  # Стандартный порт HA
            
            if not host:
                return {
                    "success": False,
                    "error": f"Неверный формат URL: {ha_url}"
                }
            
            # Проверяем доступность хоста через сокет
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    return {
                        "success": True,
                        "message": f"Хост {host}:{port} доступен",
                        "host": host,
                        "port": port
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Хост {host}:{port} недоступен (код ошибки: {result})",
                        "host": host,
                        "port": port
                    }
            except socket.gaierror as e:
                return {
                    "success": False,
                    "error": f"Ошибка DNS для {host}: {str(e)}",
                    "host": host,
                    "port": port
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Ошибка подключения: {str(e)}",
                    "host": host,
                    "port": port
                }
        except Exception as e:
            logger.error(f"Error testing HA host: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @app.post("/api/addon/config/googlesheet/test", tags=["addon-config"])
    async def test_google_sheet(gsheet_id: str = Query(..., description="ID Google таблицы для проверки")):
        """Проверка доступности Google таблицы"""
        try:
            # Извлекаем ID из URL если это URL
            spreadsheet_id = gsheet_id.strip()
            if '/spreadsheets/d/' in spreadsheet_id:
                try:
                    parts = spreadsheet_id.split('/spreadsheets/d/')
                    if len(parts) > 1:
                        spreadsheet_id = parts[1].split('/')[0].split('?')[0].split('#')[0]
                except Exception as e:
                    logger.warning(f"Failed to extract ID from Google Sheet URL: {e}")
                    return {
                        "success": False,
                        "error": f"Неверный формат URL: {gsheet_id}"
                    }
            
            if not spreadsheet_id or len(spreadsheet_id) < 20:
                return {
                    "success": False,
                    "error": "Неверный формат ID Google таблицы"
                }
            
            # Проверяем доступность через GoogleConnector
            try:
                from utils.google_connector import GoogleConnector
                google_connector = GoogleConnector(False, allow_console_auth=False)
                
                if not google_connector or not google_connector.enabled:
                    return {
                        "success": False,
                        "error": "Google Connector не настроен. Проверьте авторизацию Google."
                    }
                
                # Пытаемся получить информацию о таблице
                try:
                    spreadsheet = google_connector.service.spreadsheets().get(
                        spreadsheetId=spreadsheet_id
                    ).execute()
                    
                    return {
                        "success": True,
                        "message": f"Таблица доступна: {spreadsheet.get('properties', {}).get('title', 'Неизвестное название')}",
                        "spreadsheet_id": spreadsheet_id,
                        "title": spreadsheet.get('properties', {}).get('title', ''),
                        "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
                    }
                except Exception as e:
                    error_msg = str(e)
                    if '404' in error_msg or 'not found' in error_msg.lower():
                        return {
                            "success": False,
                            "error": "Таблица не найдена. Проверьте ID и права доступа."
                        }
                    elif '403' in error_msg or 'permission' in error_msg.lower():
                        return {
                            "success": False,
                            "error": "Нет доступа к таблице. Проверьте права доступа Google аккаунта."
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Ошибка доступа к таблице: {error_msg}"
                        }
            except Exception as e:
                logger.error(f"Error testing Google Sheet: {e}")
                return {
                    "success": False,
                    "error": f"Ошибка проверки таблицы: {str(e)}"
                }
        except Exception as e:
            logger.error(f"Error testing Google Sheet: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @app.post("/api/addon/config/homeassistant/test-token", tags=["addon-config"])
    async def test_ha_token(
        ha_url: str = Query(..., description="URL Home Assistant"),
        ha_token: str = Query(..., description="Токен Home Assistant для проверки")
    ):
        """Проверка токена Home Assistant"""
        try:
            # Проверка на пустоту токена
            if not ha_token or not ha_token.strip():
                return {
                    "success": False,
                    "error": "Токен не может быть пустым"
                }
            
            import aiohttp
            from utils.configs import config
            
            # Формируем URL для проверки токена (используем /api/ endpoint)
            # Убираем протокол из URL если есть
            url = ha_url
            if not url.startswith('http://') and not url.startswith('https://'):
                url = f"http://{url}"
            
            # Проверяем подключение к HA API с токеном
            api_url = f"{url}/api/"
            headers = {
                "Authorization": f"Bearer {ha_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(
                        api_url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return {
                                "success": True,
                                "message": "Токен валиден",
                                "version": data.get("version", "unknown")
                            }
                        elif response.status == 401:
                            return {
                                "success": False,
                                "error": "Токен невалиден или не авторизован"
                            }
                        else:
                            text = await response.text()
                            return {
                                "success": False,
                                "error": f"Ошибка подключения: HTTP {response.status}",
                                "details": text[:200] if text else None
                            }
                except asyncio.TimeoutError:
                    return {
                        "success": False,
                        "error": "Таймаут подключения к Home Assistant"
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Ошибка подключения: {str(e)}"
                    }
        except Exception as e:
            logger.error(f"Error testing HA token: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @app.get("/api/addon/config/google-auth/status", tags=["addon-config"])
    async def get_google_auth_status():
        """Проверка статуса Google авторизации"""
        try:
            from utils.configs import get_data_dir
            
            data_dir = get_data_dir()
            token_path = os.path.join(data_dir, "google_token.json")
            credentials_path = os.path.join(data_dir + "_src", "google_credentials.json")
            
            token_exists = os.path.exists(token_path)
            credentials_exists = os.path.exists(credentials_path)
            
            return {
                "success": True,
                "token_exists": token_exists,
                "credentials_exists": credentials_exists,
                "ready_for_auth": credentials_exists and not token_exists,
                "paths": {
                    "token": token_path,
                    "credentials": credentials_path
                }
            }
        except Exception as e:
            logger.error(f"Error getting Google auth status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/addon/config/google-auth/instructions", tags=["addon-config"])
    async def get_google_auth_instructions():
        """Получение инструкций по настройке Google авторизации"""
        try:
            from utils.configs import get_data_dir
            
            data_dir = get_data_dir()
            credentials_path = os.path.join(data_dir + "_src", "google_credentials.json")
            credentials_exists = os.path.exists(credentials_path)
            
            instructions = []
            
            if not credentials_exists:
                instructions.append({
                    "step": 1,
                    "title": "Создание OAuth клиента в Google Cloud Console",
                    "description": "Для работы с Google Sheets необходимо создать OAuth 2.0 клиент",
                    "details": [
                        "1. Перейдите в Google Cloud Console: https://console.cloud.google.com/",
                        "2. Выберите существующий проект или создайте новый",
                        "3. Включите необходимые API:",
                        "   - Google Sheets API",
                        "   - Google Drive API",
                        "   (APIs & Services → Library → найдите и включите нужные API)",
                        "",
                        "4. Создайте OAuth 2.0 Client ID:",
                        "   - Перейдите в 'APIs & Services' → 'Credentials'",
                        "   - Нажмите 'Create Credentials' → 'OAuth client ID'",
                        "   - Если запросит OAuth consent screen, настройте его:",
                        "     * Выберите 'External' (для тестирования)",
                        "     * Заполните обязательные поля (App name, User support email)",
                        "     * Добавьте Test users (ваш email)",
                        "",
                        "5. Настройте OAuth клиент:",
                        "   - Application type: выберите 'Desktop app'",
                        "   - Name: укажите имя (например, 'MyHome Devices')",
                        "",
                        "6. Настройте Authorized redirect URIs:",
                        "   - В разделе 'Authorized redirect URIs' нажмите 'Add URI'",
                        "   - Добавьте один из следующих URI в зависимости от вашего окружения:",
                        "",
                        "   📍 Локальная разработка:",
                        "      http://127.0.0.1:8081/api/addon/config/google-auth/callback",
                        "",
                        "   📍 Home Assistant (замените ВАШ_IP на IP вашего HA):",
                        "      http://ВАШ_IP:8123/hassio/ingress/local_my_home_devices/api/addon/config/google-auth/callback",
                        "",
                        "   ⚠️ ВАЖНО: URI должен точно совпадать, включая протокол (http/https)",
                        "",
                        "7. Скачайте JSON файл:",
                        "   - После создания клиента нажмите 'Download JSON'",
                        "   - Сохраните файл как 'google_credentials.json'",
                        "",
                        f"8. Поместите файл в директорию:",
                        f"   {data_dir}_src/google_credentials.json",
                        "",
                        "💡 Подсказка: Если вы уже создали OAuth клиент ранее:",
                        "   - Перейдите в 'Credentials' → выберите ваш OAuth client ID",
                        "   - В разделе 'Authorized redirect URIs' добавьте нужный URL",
                        "   - Сохраните изменения",
                        "   - Не забудьте обновить файл google_credentials.json, если изменили настройки"
                    ]
                })
            else:
                instructions.append({
                    "step": 1,
                    "title": "Файл google_credentials.json найден",
                    "description": "Файл credentials обнаружен. Можете перейти к получению токена."
                })
            
            instructions.append({
                "step": 2,
                "title": "Получение токена авторизации",
                "description": "После размещения файла google_credentials.json вы можете получить токен:",
                "details": [
                    "1. В интерфейсе аддона нажмите кнопку 'Получить токен'",
                    "",
                    "2. В открывшемся окне браузера:",
                    "   - Войдите в ваш Google аккаунт",
                    "   - Разрешите доступ приложению к Google Sheets и Google Drive",
                    "   - После успешной авторизации окно закроется автоматически",
                    "",
                    "3. Токен будет сохранен автоматически",
                    "   - Статус обновится в интерфейсе через несколько секунд",
                    "   - Вы получите уведомление об успешном сохранении",
                    "",
                    "⚠️ Если возникли проблемы:",
                    "   - Проверьте, что redirect URI в Google Cloud Console совпадает с тем,",
                    "     который используется вашим окружением",
                    "   - Убедитесь, что файл google_credentials.json находится в правильной директории",
                    "   - Проверьте логи аддона для подробной информации об ошибках"
                ]
            })
            
            return {
                "success": True,
                "credentials_exists": credentials_exists,
                "credentials_path": credentials_path,
                "instructions": instructions
            }
        except Exception as e:
            logger.error(f"Error getting Google auth instructions: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/addon/config/google-auth/get-url", tags=["addon-config"])
    async def get_google_auth_url(request: Request):
        """Получение OAuth URL для авторизации Google"""
        try:
            from utils.configs import get_data_dir
            
            data_dir = get_data_dir()
            credentials_path = os.path.join(data_dir + "_src", "google_credentials.json")
            
            if not os.path.exists(credentials_path):
                raise HTTPException(
                    status_code=400,
                    detail="Файл google_credentials.json не найден. Добавьте его в /data_src/"
                )
            
            # Определяем redirect_uri на основе текущего запроса
            redirect_uri = get_redirect_uri(request)
            
            # Читаем credentials для определения типа клиента
            with open(credentials_path, 'r') as f:
                credentials_data = json.load(f)
            
            # Определяем тип клиента
            client_type = None
            if 'installed' in credentials_data:
                client_type = 'installed'
            elif 'web' in credentials_data:
                client_type = 'web'
            
            from google_auth_oauthlib.flow import InstalledAppFlow, Flow
            
            SCOPES = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            
            # Создаем flow для получения авторизационного URL
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path,
                SCOPES
            )
            
            # Устанавливаем динамический redirect_uri
            flow.redirect_uri = redirect_uri
            logger.info(f"Using redirect_uri: {redirect_uri} (client_type: {client_type})")
            
            # Генерируем URL для получения authorization code
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'  # Принудительно запрашиваем consent для получения refresh_token
            )
            
            # Сохраняем state, redirect_uri и flow для проверки при callback
            # В реальном приложении лучше использовать сессию или Redis
            # Здесь сохраняем в временный файл
            state_file = os.path.join(data_dir, ".google_oauth_state.json")
            with open(state_file, 'w') as f:
                json.dump({
                    "state": state,
                    "credentials_path": credentials_path,
                    "redirect_uri": redirect_uri or flow.redirect_uri
                }, f)
            
            logger.info(f"OAuth URL generated: {authorization_url[:100]}...")
            
            return {
                "success": True,
                "auth_url": authorization_url,
                "state": state,
                "redirect_uri": redirect_uri or flow.redirect_uri,
                "client_type": client_type
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting Google auth URL: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/addon/config/google-auth/authorize", tags=["addon-config"])
    async def authorize_google(request: Dict[str, Any]):
        """Завершение OAuth авторизации с кодом"""
        try:
            from utils.configs import get_data_dir
            from google_auth_oauthlib.flow import InstalledAppFlow
            from fastapi import Request as FastAPIRequest
            
            code = request.get("code")
            state = request.get("state")
            
            if not code:
                raise HTTPException(status_code=400, detail="Код авторизации не предоставлен")
            
            data_dir = get_data_dir()
            state_file = os.path.join(data_dir, ".google_oauth_state.json")
            
            if not os.path.exists(state_file):
                raise HTTPException(
                    status_code=400,
                    detail="Сессия авторизации не найдена. Начните процесс заново."
                )
            
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            
            credentials_path = state_data.get("credentials_path")
            saved_state = state_data.get("state")
            saved_redirect_uri = state_data.get("redirect_uri")
            
            # Проверяем state (опционально, для безопасности)
            if state and state != saved_state:
                logger.warning(f"State mismatch: expected {saved_state}, got {state}")
                # Не падаем, но логируем
            
            if not os.path.exists(credentials_path):
                raise HTTPException(
                    status_code=400,
                    detail="Файл google_credentials.json не найден"
                )
            
            SCOPES = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            
            # Создаем flow и обмениваем код на токены
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path,
                SCOPES
            )
            
            # Устанавливаем тот же redirect_uri, что использовался при создании URL
            if saved_redirect_uri:
                flow.redirect_uri = saved_redirect_uri
                logger.info(f"Using saved redirect_uri: {saved_redirect_uri}")
            
            # Обмениваем authorization code на токены
            # Используем метод для обмена кода без локального сервера
            flow.fetch_token(code=code)
            
            # Получаем credentials
            credentials = flow.credentials
            
            # Сохраняем токен
            token_path = os.path.join(data_dir, "google_token.json")
            with open(token_path, 'w') as token_file:
                token_file.write(credentials.to_json())
            
            # Удаляем временный файл состояния
            try:
                os.remove(state_file)
            except:
                pass
            
            logger.info("Google token successfully saved")
            
            return {
                "success": True,
                "message": "Токен успешно получен и сохранен"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error authorizing Google: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/addon/config/google-auth/callback", tags=["addon-config"])
    async def google_auth_callback(request: Request):
        """OAuth callback endpoint для обработки redirect от Google"""
        # Получаем все параметры из query string
        query_params = dict(request.query_params)
        error = query_params.get('error')
        code = query_params.get('code')
        state = query_params.get('state')
        scope = query_params.get('scope')
        
        try:
            from utils.configs import get_data_dir
            
            # Обработка ошибок от Google OAuth
            if error:
                error_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Ошибка авторизации Google</title>
                    <meta charset="utf-8">
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background-color: #f5f5f5;
                        }}
                        .container {{
                            background: white;
                            padding: 30px;
                            border-radius: 8px;
                            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                            text-align: center;
                            max-width: 500px;
                        }}
                        .error {{
                            color: #d32f2f;
                            font-size: 18px;
                            margin-bottom: 20px;
                        }}
                        button {{
                            background-color: #1976d2;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 4px;
                            cursor: pointer;
                            font-size: 16px;
                        }}
                        button:hover {{
                            background-color: #1565c0;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="error">❌ Ошибка авторизации</div>
                        <p>Ошибка: {error}</p>
                        <button onclick="window.close()">Закрыть</button>
                    </div>
                </body>
                </html>
                """
                return HTMLResponse(content=error_html, status_code=400)
            
            if not code:
                error_html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Ошибка авторизации Google</title>
                    <meta charset="utf-8">
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background-color: #f5f5f5;
                        }
                        .container {
                            background: white;
                            padding: 30px;
                            border-radius: 8px;
                            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                            text-align: center;
                            max-width: 500px;
                        }
                        .error {
                            color: #d32f2f;
                            font-size: 18px;
                            margin-bottom: 20px;
                        }
                        button {
                            background-color: #1976d2;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 4px;
                            cursor: pointer;
                            font-size: 16px;
                        }
                        button:hover {
                            background-color: #1565c0;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="error">❌ Ошибка авторизации</div>
                        <p>Код авторизации не получен. Пожалуйста, попробуйте снова.</p>
                        <button onclick="window.close()">Закрыть</button>
                    </div>
                </body>
                </html>
                """
                return HTMLResponse(content=error_html, status_code=400)
            
            data_dir = get_data_dir()
            state_file = os.path.join(data_dir, ".google_oauth_state.json")
            
            if not os.path.exists(state_file):
                error_html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Ошибка авторизации Google</title>
                    <meta charset="utf-8">
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background-color: #f5f5f5;
                        }
                        .container {
                            background: white;
                            padding: 30px;
                            border-radius: 8px;
                            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                            text-align: center;
                            max-width: 500px;
                        }
                        .error {
                            color: #d32f2f;
                            font-size: 18px;
                            margin-bottom: 20px;
                        }
                        button {
                            background-color: #1976d2;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 4px;
                            cursor: pointer;
                            font-size: 16px;
                        }
                        button:hover {
                            background-color: #1565c0;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="error">❌ Ошибка авторизации</div>
                        <p>Сессия авторизации не найдена. Начните процесс заново.</p>
                        <button onclick="window.close()">Закрыть</button>
                    </div>
                </body>
                </html>
                """
                return HTMLResponse(content=error_html, status_code=400)
            
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            
            credentials_path = state_data.get("credentials_path")
            saved_state = state_data.get("state")
            saved_redirect_uri = state_data.get("redirect_uri")
            
            # Проверяем state (опционально, для безопасности)
            if state and state != saved_state:
                logger.warning(f"State mismatch: expected {saved_state}, got {state}")
            
            if not os.path.exists(credentials_path):
                error_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Ошибка авторизации Google</title>
                    <meta charset="utf-8">
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background-color: #f5f5f5;
                        }}
                        .container {{
                            background: white;
                            padding: 30px;
                            border-radius: 8px;
                            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                            text-align: center;
                            max-width: 500px;
                        }}
                        .error {{
                            color: #d32f2f;
                            font-size: 18px;
                            margin-bottom: 20px;
                        }}
                        button {{
                            background-color: #1976d2;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 4px;
                            cursor: pointer;
                            font-size: 16px;
                        }}
                        button:hover {{
                            background-color: #1565c0;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="error">❌ Ошибка авторизации</div>
                        <p>Файл google_credentials.json не найден</p>
                        <button onclick="window.close()">Закрыть</button>
                    </div>
                </body>
                </html>
                """
                return HTMLResponse(content=error_html, status_code=400)
            
            # Читаем credentials для получения client_id и client_secret
            with open(credentials_path, 'r') as f:
                credentials_data = json.load(f)
            
            SCOPES = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.oauth2.credentials import Credentials
            import requests
            
            # Создаем flow и обмениваем код на токены
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path,
                SCOPES
            )
            
            # Устанавливаем тот же redirect_uri, что использовался при создании URL
            if saved_redirect_uri:
                flow.redirect_uri = saved_redirect_uri
                logger.info(f"Using saved redirect_uri: {saved_redirect_uri}")
            
            # Обмениваем authorization code на токены
            # Используем прямой обмен через requests для избежания проблем с scope mismatch
            credentials = None
            
            # Получаем client_id и client_secret из credentials
            if 'installed' in credentials_data:
                client_info = credentials_data['installed']
            elif 'web' in credentials_data:
                client_info = credentials_data['web']
            else:
                raise HTTPException(status_code=500, detail="Invalid credentials format")
            
            client_id = client_info['client_id']
            client_secret = client_info['client_secret']
            token_uri = client_info.get('token_uri', 'https://oauth2.googleapis.com/token')
            
            # Обмениваем код напрямую через requests (обход проверки scope)
            token_data = {
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': saved_redirect_uri or flow.redirect_uri,
                'grant_type': 'authorization_code'
            }
            
            logger.info(f"Exchanging code for token (redirect_uri: {token_data['redirect_uri']})")
            
            try:
                response = requests.post(token_uri, data=token_data, timeout=30)
                response.raise_for_status()
                token_info = response.json()
                
                # Проверяем наличие ошибок в ответе
                if 'error' in token_info:
                    error_msg = token_info.get('error_description', token_info.get('error', 'Unknown error'))
                    logger.error(f"Token exchange error: {error_msg}")
                    raise HTTPException(status_code=400, detail=f"Token exchange failed: {error_msg}")
                
                # Получаем scopes из ответа или используем запрошенные
                returned_scopes = token_info.get('scope', '')
                if returned_scopes:
                    actual_scopes = returned_scopes.split()
                else:
                    # Если scope не вернулся, используем из параметров запроса или запрошенные
                    if scope:
                        actual_scopes = scope.split()
                    else:
                        actual_scopes = SCOPES
                
                logger.info(f"Token obtained successfully with scopes: {actual_scopes}")
                
                # Создаем credentials из полученного токена
                credentials_dict = {
                    'token': token_info.get('access_token'),
                    'refresh_token': token_info.get('refresh_token'),
                    'token_uri': token_uri,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'scopes': actual_scopes
                }
                
                # Проверяем наличие обязательных полей
                if not credentials_dict.get('token'):
                    raise HTTPException(status_code=500, detail="No access token received from Google")
                
                credentials = Credentials.from_authorized_user_info(credentials_dict, SCOPES)
                
            except requests.RequestException as e:
                logger.error(f"Request error during token exchange: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to exchange token: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error during token exchange: {e}")
                raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
            
            if not credentials:
                raise HTTPException(status_code=500, detail="Failed to create credentials object")
            
            # Сохраняем токен
            token_path = os.path.join(data_dir, "google_token.json")
            with open(token_path, 'w') as token_file:
                token_file.write(credentials.to_json())
            
            # Удаляем временный файл состояния
            try:
                os.remove(state_file)
            except:
                pass
            
            logger.info("Google token successfully saved via callback")
            
            # Отправляем WebSocket уведомление об обновлении статуса
            try:
                from utils.socket_utils import connection_manager
                import asyncio
                
                ws_data = {
                    "type": "addon_config",
                    "action": "google_auth_updated",
                    "data": {
                        "token_exists": True,
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
                    import threading
                    def broadcast_update():
                        asyncio.run(connection_manager.broadcast(ws_data))
                    threading.Thread(target=broadcast_update, daemon=True).start()
                
                logger.info("WebSocket notification sent: Google auth status updated")
            except Exception as e:
                logger.warning(f"Failed to send WebSocket notification: {e}")
            
            # Показываем страницу успеха
            success_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Успешная авторизация Google</title>
                <meta charset="utf-8">
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background-color: #f5f5f5;
                    }
                    .container {
                        background: white;
                        padding: 30px;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        text-align: center;
                        max-width: 500px;
                    }
                    .success {
                        color: #2e7d32;
                        font-size: 18px;
                        margin-bottom: 20px;
                    }
                    button {
                        background-color: #1976d2;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 16px;
                    }
                    button:hover {
                        background-color: #1565c0;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success">✅ Авторизация успешна!</div>
                    <p>Токен Google успешно получен и сохранен.</p>
                    <p>Вы можете закрыть это окно.</p>
                    <button onclick="window.close()">Закрыть</button>
                </div>
                <script>
                    // Пытаемся закрыть окно автоматически через 2 секунды
                    setTimeout(function() {
                        window.close();
                    }, 2000);
                </script>
            </body>
            </html>
            """
            return HTMLResponse(content=success_html)
        except Exception as e:
            logger.error(f"Error in Google auth callback: {e}")
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Ошибка авторизации Google</title>
                <meta charset="utf-8">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background-color: #f5f5f5;
                    }}
                    .container {{
                        background: white;
                        padding: 30px;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        text-align: center;
                        max-width: 500px;
                    }}
                    .error {{
                        color: #d32f2f;
                        font-size: 18px;
                        margin-bottom: 20px;
                    }}
                    button {{
                        background-color: #1976d2;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 16px;
                    }}
                    button:hover {{
                        background-color: #1565c0;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌ Ошибка авторизации</div>
                    <p>{str(e)}</p>
                    <button onclick="window.close()">Закрыть</button>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=error_html, status_code=500)
