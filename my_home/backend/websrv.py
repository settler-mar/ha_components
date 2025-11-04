from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Cookie, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from datetime import datetime
import json

from utils.socket_utils import connection_manager
from os import path
from utils.db_utils import init_db
from utils.configs import config
from utils.ha_manager import ha_manager
from utils.logger import api_logger as logger, add_logger_routes
from models.my_home import MyHomeClass
from models.my_home import add_routes as my_home_routes
from models.device import add_myhome_device_routes
from models.ha_routes import add_ha_routes
from models.logs_backup_routes import add_logs_backup_routes
from models.ports_settings_routes import add_ports_settings_routes
from models.addon_config_routes import add_addon_config_routes

from utils.google_connector import GoogleConnector

PORT = 3000

# Initialize the FastAPI app
app = FastAPI()
app.add_middleware(
  CORSMiddleware,
  allow_credentials=True,
  allow_origins=["*"],
  allow_methods=["*"],
  allow_headers=["*"],
)


# Middleware для обработки ingress пути
@app.middleware("http")
async def ingress_middleware(request: Request, call_next):
  # Логируем все запросы для отладки
  # print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Ingress request: {request.method} {request.url}")
  # print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Headers: {dict(request.headers)}")

  # Проверяем, является ли это ingress запросом
  path = request.url.path
  try:
    if path.startswith('/api/hassio_ingress/'):
      # Извлекаем токен из пути
      parts = path.split('/')
      if len(parts) >= 4:
        token = parts[3]
        # Убираем ingress префикс из пути
        new_path = '/' + '/'.join(parts[4:]) if len(parts) > 4 else '/'
        # Создаем новый request с исправленным путем
        request.scope['path'] = new_path
        logger.debug(f"Ingress token: {token}, new path: {new_path}")
    
    response = await call_next(request)
    return response
  except Exception as e:
    logger.error(f"Ingress middleware error: {e}", exc_info=True)
    # Возвращаем 503 если произошла ошибка в middleware
    from fastapi.responses import JSONResponse
    return JSONResponse(
      status_code=503,
      content={"detail": f"Service temporarily unavailable: {str(e)}"}
    )


logger.info("Starting FastAPI server...")
config.create_routes(app)
init_db(app)

my_home: MyHomeClass = None


def init(add_routes=True):
  global my_home
  my_home = MyHomeClass()

  if add_routes:
    my_home_routes(app, my_home)
    add_myhome_device_routes(app, resolver=my_home.get_client)
    add_ha_routes(app)
    add_logs_backup_routes(app)
    add_ports_settings_routes(app)
    add_logger_routes(app)
    add_addon_config_routes(app)
    logger.info("Routes added to FastAPI app")

  # Загружаем устройства из базы данных
  my_home.load_devices()
  logger.info(f"Loaded {len(my_home._devices)} devices")


async def handle_device_command(message):
  """
  Обрабатывает команды для устройств от фронтенда
  """
  try:
    device_id = message.get('device_id')
    code = message.get('code')
    value = message.get('value')

    if not all([device_id, code, value is not None]):
      logger.warning("Invalid command message: missing required fields")
      return

    # Получаем клиент устройства
    client = my_home.get_client(device_id)
    if not client:
      logger.warning(f"Device client not found: {device_id}")
      return

    # Отправляем команду на устройство в формате ESP: "code#value"
    success = await send_command_to_device_ws(client, code, value)

    if not success:
      logger.error(f"Failed to send command to device {device_id}")

  except Exception as e:
    logger.error(f"Error handling device command: {e}")


async def send_command_to_device_ws(client, code: str, value) -> bool:
  """
  Отправляет команду на устройство через WebSocket в формате ESP
  """
  try:
    # Используем метод send_command клиента
    success = await client.send_command(code, value)
    return success

  except Exception as e:
    logger.error(f"Error sending command to device {client.device_id}: {e}")
    return False


init()


# Add alive status route
@app.get("/api")
async def alive():
  """
  Check if the server is alive
  """
  return {"status": "alive"}


@app.get("/api/restart")
async def restart():
  """
  Restart the server
  """
  logger.info("Starting restart...")
  from models.singelton import SingletonClass
  SingletonClass.restart_all()
  await init(False)
  return {"status": "restarting", "message": "Server will restart"}


# Websocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, access_token=Cookie(None)):
  # if access_token is None:
  #   await websocket.close()
  await connection_manager.connect(websocket)
  try:
    while True:
      data = await websocket.receive_text()

      # Обрабатываем команды от фронтенда
      try:
        message = json.loads(data)
        if message.get('type') == 'device_command':
          await handle_device_command(message)
      except json.JSONDecodeError:
        # Если это не JSON, игнорируем
        pass
      except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")

  except WebSocketDisconnect:
    connection_manager.disconnect(websocket)
    await connection_manager.broadcast("A client just disconnected.")


# WebSocket endpoint для ingress (будет обрабатываться middleware)
@app.websocket("/{token}/ws")
async def websocket_ingress_endpoint(websocket: WebSocket, token: str, access_token=Cookie(None)):
  logger.info(f"Ingress WebSocket connection with token: {token}")
  # if access_token is None:
  #   await websocket.close()
  await connection_manager.connect(websocket)
  try:
    while True:
      data = await websocket.receive_text()
      # Убираем входящие сообщения от устройств - не пересылаем их
  except WebSocketDisconnect:
    connection_manager.disconnect(websocket)
    await connection_manager.broadcast("A client just disconnected.")


def join_dist():
  # Serve the Vue app in production mode
  try:
    # Directory where Vue app build output is located
    build_dir = path.realpath(path.join(path.dirname(__file__), ".."))

    # Проверяем разные возможные пути для фронтенда
    possible_paths = [
      path.join(build_dir, 'dist'),  # Локальный путь в проекте (для Docker/HA)
      path.join(build_dir, 'frontend', 'dist'),  # Для локальной разработки
      path.join(build_dir, '..', 'frontend', 'dist'),  # Альтернативный путь
      '/my_home/dist',  # Прямой путь для контейнера
      '/addons/my_addons/my_home/dist',  # Прямой путь для Home Assistant (исходный)
    ]

    build_dir = None
    for possible_path in possible_paths:
      logger.debug(f'Checking path: {possible_path} - exists: {path.exists(possible_path)}')
      if path.exists(possible_path):
        build_dir = possible_path
        break

    if not build_dir:
      logger.warning("No build directory found")
      return
    logger.info(f"Frontend build directory: {build_dir}")
    index_path = path.join(build_dir, "index.html")
    logger.debug(f"Index file: {index_path} - exists: {path.exists(index_path)}")

    # Serve assets files from the build directory
    assets_path = path.join(build_dir, "assets")
    logger.debug(f"Assets directory: {assets_path} - exists: {path.exists(assets_path)}")
    if path.exists(assets_path):
      # Логируем содержимое папки assets
      try:
        import os
        assets_files = os.listdir(assets_path)
        logger.debug(f"Assets files: {assets_files}")
      except Exception as e:
        logger.error(f"Error listing assets: {e}")

      app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
      logger.info("Assets mounted at /assets")

      # Также монтируем статические файлы для всех файлов в build_dir
      app.mount("/static", StaticFiles(directory=build_dir), name="static")
      logger.info("Static files mounted at /static")

    # Catch-all route for SPA
    @app.get("/{catchall:path}")
    async def serve_spa(catchall: str):
      logger.debug(f"Serving request: /{catchall}")
      if catchall.startswith("api/"):
        # явно возвращаем 404
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"API endpoint({catchall}) not found")

      # Проверяем, является ли это запросом к assets
      if catchall.startswith("assets/"):
        file_path = path.join(build_dir, catchall)
        if path.exists(file_path) and path.isfile(file_path):
          logger.debug(f"Serving asset file: {file_path}")
          return FileResponse(file_path)
        else:
          logger.warning(f"Asset file not found: {file_path}")
          from fastapi import HTTPException
          raise HTTPException(status_code=404, detail=f"Asset not found: {catchall}")

      file_path = path.join(build_dir, catchall)
      if path.exists(file_path) and path.isfile(file_path):
        logger.debug(f"Serving file: {file_path}")
        # Для index.html добавляем заголовки, запрещающие кеширование
        if catchall == "index.html" or file_path == index_path:
          with open(file_path, 'rb') as f:
            content = f.read()
          return Response(
            content=content,
            media_type="text/html",
            headers={
              "Cache-Control": "no-cache, no-store, must-revalidate",
              "Pragma": "no-cache",
              "Expires": "0"
            }
          )
        return FileResponse(file_path)
      logger.debug(f"Serving index.html for: /{catchall}")
      # Для index.html добавляем заголовки, запрещающие кеширование
      with open(index_path, 'rb') as f:
        content = f.read()
      return Response(
        content=content,
        media_type="text/html",
        headers={
          "Cache-Control": "no-cache, no-store, must-revalidate",
          "Pragma": "no-cache",
          "Expires": "0"
        }
      )

    logger.success("Frontend successfully configured")

  except RuntimeError:
    # The build directory does not exist
    logger.warning("No build directory found. Running in development mode.")


# GoogleConnector инициализируется лениво при необходимости
# Автоматическое открытие браузера отключено (allow_console_auth=False)
# Токен должен быть получен через UI в настройках аддона


# Инициализация HA Manager
@app.on_event("startup")
async def startup_event():
  """Инициализация при запуске приложения"""
  try:
    logger.info("FastAPI startup event triggered")

    # Проверяем инициализацию my_home
    if my_home is None:
      logger.error("my_home is None in startup_event")
    else:
      logger.info(f"my_home status: {len(my_home._devices)} devices loaded")

    # Проверяем, что маршруты добавлены
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    live_routes = [route for route in routes if '/api/live' in route]
    logger.info(f"Live routes registered: {live_routes}")

    # Инициализируем HA Manager
    ha_manager.set_my_home(my_home)
    await ha_manager.initialize()
    logger.success("HA Manager initialized")
  except Exception as e:
    logger.error(f"Error in startup event: {e}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")


@app.on_event("shutdown")
async def shutdown_event():
  """Завершение работы приложения"""
  try:
    await ha_manager.shutdown()
    logger.success("HA Manager shutdown")
  except Exception as e:
    logger.error(f"Error shutting down HA Manager: {e}")


join_dist()

logger.success("Running FastAPI app...")
logger.info(f"FastAPI is available at http://localhost:{PORT}/api")
logger.info(f"Swagger UI is available at http://localhost:{PORT}/docs")
logger.info(f"Redoc is available at http://localhost:{PORT}/redoc")
