from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from utils.socket_utils import connection_manager
from os import path
from utils.db_utils import init_db
from utils.configs import config
from models.my_home import MyHomeClass
from models.my_home import add_routes as my_home_routes
from models.device import add_myhome_device_routes

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

print()
print("Starting FastAPI server...")
config.create_routes(app)
init_db(app)

my_home: MyHomeClass = None


def init(add_routes=True):
  global my_home
  my_home = MyHomeClass()
  my_home_routes(app, my_home)
  add_myhome_device_routes(app, resolver=my_home.get_client)


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
      await connection_manager.broadcast(f"Message text was: {data}")
  except WebSocketDisconnect:
    connection_manager.disconnect(websocket)
    await connection_manager.broadcast("A client just disconnected.")


def join_dist():
  # Serve the Vue app in production mode
  try:
    # Directory where Vue app build output is located
    build_dir = path.realpath(path.join(path.dirname(__file__), ".."))
    if path.exists(path.join(build_dir, 'dist')):
      build_dir = path.join(build_dir, 'dist')
    elif path.exists(path.join(build_dir, 'frontend')) and path.exists(path.join(build_dir, 'frontend', 'dist')):
      build_dir = path.join(build_dir, 'frontend', 'dist')
    else:
      print('No build directory found')
      return
    print('build_dir', build_dir)
    index_path = path.join(build_dir, "index.html")

    # Serve assets files from the build directory
    app.mount("/assets", StaticFiles(directory=path.join(build_dir, "assets")), name="assets")

    # Catch-all route for SPA
    @app.get("/{catchall:path}")
    async def serve_spa(catchall: str):
      if catchall.startswith("api/"):
        # явно возвращаем 404
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"API endpoint({catchall}) not found")

      file_path = path.join(build_dir, catchall)
      if path.exists(file_path) and path.isfile(file_path):
        return FileResponse(file_path)
      return FileResponse(index_path)

  except RuntimeError:
    # The build directory does not exist
    print("No build directory found. Running in development mode.")


GoogleConnector(False)
join_dist()

print("\nRunning FastAPI app...")
print(" - FastAPI is available at " + f"http://localhost:{PORT}/api")
print(" - Swagger UI is available at " + f"http://localhost:{PORT}/docs")
print(" - Redoc is available at " + f"http://localhost:{PORT}/redoc")
print("")
