from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Cookie, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime
import json

from utils.socket_utils import connection_manager
from os import path
from utils.db_utils import init_db
from utils.configs import config
from models.my_home import MyHomeClass
from models.my_home import add_routes as my_home_routes
from models.device import add_myhome_device_routes
from models.ha_routes import add_ha_routes
from models.logs_backup_routes import add_logs_backup_routes
from models.ports_settings_routes import add_ports_settings_routes

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
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Ingress request: {request.method} {request.url}")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Headers: {dict(request.headers)}")
    
    # Проверяем, является ли это ingress запросом
    path = request.url.path
    if path.startswith('/api/hassio_ingress/'):
        # Извлекаем токен из пути
        parts = path.split('/')
        if len(parts) >= 4:
            token = parts[3]
            # Убираем ingress префикс из пути
            new_path = '/' + '/'.join(parts[4:]) if len(parts) > 4 else '/'
            # Создаем новый request с исправленным путем
            request.scope['path'] = new_path
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Ingress token: {token}, new path: {new_path}")
    
    response = await call_next(request)
    return response

print()
print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Starting FastAPI server...")
config.create_routes(app)
init_db(app)

my_home: MyHomeClass = None


def init(add_routes=True):
  global my_home
  my_home = MyHomeClass()
  my_home_routes(app, my_home)
  add_myhome_device_routes(app, resolver=my_home.get_client)
  add_ha_routes(app)
  add_logs_backup_routes(app)
  add_ports_settings_routes(app)
  
  # Загружаем устройства из базы данных
  my_home.load_devices()


async def handle_device_command(message):
  """
  Обрабатывает команды для устройств от фронтенда
  """
  try:
    device_id = message.get('device_id')
    code = message.get('code')
    value = message.get('value')
    
    if not all([device_id, code, value is not None]):
      print(f"[WebSocket] Invalid command message: missing required fields")
      return
    
    # Получаем клиент устройства
    client = my_home.get_client(device_id)
    if not client:
      print(f"[WebSocket] Device client not found: {device_id}")
      return
    
    # Отправляем команду на устройство в формате ESP: "code#value"
    success = await send_command_to_device_ws(client, code, value)
    
    if not success:
      print(f"[WebSocket] Failed to send command to device {device_id}")
      
  except Exception as e:
    print(f"[WebSocket] Error handling device command: {e}")


async def send_command_to_device_ws(client, code: str, value) -> bool:
  """
  Отправляет команду на устройство через WebSocket в формате ESP
  """
  try:
    # Используем метод send_command клиента
    success = await client.send_command(code, value)
    return success
    
  except Exception as e:
    print(f"[DeviceControl] Error sending command to device {client.device_id}: {e}")
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
  print('start restart')
  from models.singelton import SingletonClass
  SingletonClass.restart_all()
  init(False)
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
        print(f"Error handling WebSocket message: {e}")
        
  except WebSocketDisconnect:
    connection_manager.disconnect(websocket)
    await connection_manager.broadcast("A client just disconnected.")

# WebSocket endpoint для ingress (будет обрабатываться middleware)
@app.websocket("/{token}/ws")
async def websocket_ingress_endpoint(websocket: WebSocket, token: str, access_token=Cookie(None)):
  print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Ingress WebSocket connection with token: {token}")
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
      path.join(build_dir, 'dist'),  # Локальный путь в backend
      path.join(build_dir, 'frontend', 'dist'),
      '/backend/dist',  # Docker путь
      path.join(build_dir, '..', 'frontend', 'dist')
    ]
    
    build_dir = None
    for possible_path in possible_paths:
      print(f'Checking path: {possible_path} - exists: {path.exists(possible_path)}')
      if path.exists(possible_path):
        build_dir = possible_path
        break
    
    if not build_dir:
      print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - No build directory found")
      return
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Frontend build directory: {build_dir}")
    index_path = path.join(build_dir, "index.html")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Index file: {index_path} - exists: {path.exists(index_path)}")

    # Serve assets files from the build directory
    assets_path = path.join(build_dir, "assets")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Assets directory: {assets_path} - exists: {path.exists(assets_path)}")
    if path.exists(assets_path):
      # Логируем содержимое папки assets
      try:
        import os
        assets_files = os.listdir(assets_path)
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Assets files: {assets_files}")
      except Exception as e:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Error listing assets: {e}")
      
      app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
      print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Assets mounted at /assets")
      
      # Также монтируем статические файлы для всех файлов в build_dir
      app.mount("/static", StaticFiles(directory=build_dir), name="static")
      print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Static files mounted at /static")

    # Catch-all route for SPA
    @app.get("/{catchall:path}")
    async def serve_spa(catchall: str):
      print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Serving request: /{catchall}")
      if catchall.startswith("api/"):
        # явно возвращаем 404
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"API endpoint({catchall}) not found")

      # Проверяем, является ли это запросом к assets
      if catchall.startswith("assets/"):
        file_path = path.join(build_dir, catchall)
        if path.exists(file_path) and path.isfile(file_path):
          print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Serving asset file: {file_path}")
          return FileResponse(file_path)
        else:
          print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Asset file not found: {file_path}")
          from fastapi import HTTPException
          raise HTTPException(status_code=404, detail=f"Asset not found: {catchall}")

      file_path = path.join(build_dir, catchall)
      if path.exists(file_path) and path.isfile(file_path):
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Serving file: {file_path}")
        return FileResponse(file_path)
      print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Serving index.html for: /{catchall}")
      return FileResponse(index_path)

    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Frontend successfully configured")

  except RuntimeError:
    # The build directory does not exist
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - No build directory found. Running in development mode.")


GoogleConnector(False)


join_dist()

print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Running FastAPI app...")
print(" - FastAPI is available at " + f"http://localhost:{PORT}/api")
print(" - Swagger UI is available at " + f"http://localhost:{PORT}/docs")
print(" - Redoc is available at " + f"http://localhost:{PORT}/redoc")
print("")
