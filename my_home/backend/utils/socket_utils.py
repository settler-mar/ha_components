from fastapi import WebSocket, WebSocketDisconnect
from typing import List
import asyncio

from datetime import datetime
import json
from utils.logs import log_print
from utils.logger import api_logger as logger
import threading


# Define a custom function to serialize datetime objects
def serialize_datetime(obj):
  if isinstance(obj, datetime):
    return obj.isoformat()
  logger.error(f"Type not serializable: {obj}")
  raise TypeError("Type not serializable")


class ConnectionManager:
  logs_queue = []
  logs_history = []
  max_history = 10 ** 5

  def __init__(self):
    self.active_connections: List[WebSocket] = []
    self._thread = threading.Thread(target=self._thread_main, daemon=True)
    self._loop = None
    self._stop_event = threading.Event()
    self._thread.start()

  def _thread_main(self):
    asyncio.set_event_loop(asyncio.new_event_loop())
    self._loop = asyncio.get_event_loop()
    self._loop.create_task(self._process_queue())
    self._loop.run_forever()

  async def _process_queue(self):
    while not self._stop_event.is_set():
      while self.logs_queue:
        try:
          data, permission = self.logs_queue.pop(0)
          self.logs_history.append((data, permission))
          self.logs_history = self.logs_history[-self.max_history:]
          await self.broadcast(data)
        except Exception as e:
          logger.error(f"Error processing item: {e}")
      await asyncio.sleep(0.1)

  async def connect(self, websocket: WebSocket):
    token = websocket.cookies.get("token")
    logger.info(f"WebSocket connection established from {websocket.client.host} with token: {token}")
    # todo check auth

    await websocket.accept()
    self.active_connections.append(websocket)

  def disconnect(self, websocket: WebSocket):
    if websocket in self.active_connections:
      self.active_connections.remove(websocket)

  async def broadcast(self, data: dict, permission: str = 'all'):
    # Отправляем всем активным клиентам без подписки
    for connection in self.active_connections:
      try:
        json_data = json.dumps(data, default=serialize_datetime)
        await asyncio.create_task(connection.send_text(json_data))
      except WebSocketDisconnect:
        logger.info(f"WebSocket disconnecting from {connection.client.host}")
        self.disconnect(connection)
      except Exception as e:
        logger.error(f"Error sending to client: {e}")

  def broadcast_log(self,
                    text: str = None,
                    message: str = None,
                    level: str = 'info',
                    permission: str = 'all',
                    device_id: int = None,
                    dag_id: int = None,
                    dag_port_id: str = None,
                    dag: "DAGNode" = None,
                    port_id: int = None,
                    pin_id: int = None,
                    pin_name: str = None,
                    value: str = None,
                    class_name: str = None,
                    value_raw: str = None,
                    direction: str = None,
                    action: str = None,
                    _type="log"):
    """
    Send log message to all connected clients
    level: 'info', 'warning', 'error', 'debug', 'value'
    permission: 'all', 'admin', 'root'
    direction: 'in', 'out', 'params', None
    """
    if isinstance(value, dict) and 'new_value' in value and len(value['new_value']) == 2:
      value = value['new_value'][0]
    class_name = class_name or (dag and dag.__class__.__name__)
    data = {
      "type": _type,
      "level": level,
      "permission": permission,
      "message": text or message,
      "device_id": device_id,
      "dag_id": dag_id or (dag and dag.id),
      "dag_port_id": dag_port_id,
      "pin_id": pin_id,
      "pin_name": pin_name,
      "port_id": port_id,
      "direction": direction,
      "class_name": str(class_name) if class_name else None,
      "value": value,
      "value_raw": value_raw,
      "action": action,
      "ts": datetime.now().timestamp()
    }
    data = {k: v for k, v in data.items() if v is not None}
    
    # Логируем через наш новый логгер
    log_message = data.get('message', '')
    log_level = data.get('level', 'info')
    device_id = data.get('device_id')
    class_name = data.get('class_name', 'SocketUtils')
    action = data.get('action', '')
    value = data.get('value')
    
    # Формируем сообщение для логгера
    if device_id:
        log_message = f"[Device {device_id}] {log_message}"
    if action:
        log_message = f"{log_message} (Action: {action})"
    if value:
        log_message = f"{log_message} (Value: {value})"
    
    # Выбираем уровень логирования
    if log_level == 'info':
        logger.info(log_message)
    elif log_level == 'warning':
        logger.warning(log_message)
    elif log_level == 'error':
        logger.error(log_message)
    elif log_level == 'debug':
        logger.debug(log_message)
    else:
        logger.info(log_message)
    
    self.logs_queue.append((data, permission))


connection_manager = ConnectionManager()
