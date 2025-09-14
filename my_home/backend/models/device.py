# services/myhome_device_client.py
import asyncio
import json
import aiohttp
from typing import Callable, Dict, Any, List, Optional
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from utils.values import flatten_ports
from utils.db_utils import db_session
from db_models.devices import Devices as DbDevices
from db_models.ports import Ports as DbPorts
from utils.logs import log_print
from datetime import datetime

_ROUTES_ADDED = False


class MyHomeDeviceClient:
  """
  Клиент конкретного устройства MyHome:
  - HTTP bootstrap: http://{ip}/values  → кэш портов
  - WS: ws://{ip}:81/ (TEXT), формат сообщений 'code#value'
  - API: /api/myhome/device/{id}, /ports, /params
  """

  _routes_added = False
  _online = False  # флаг, что устройство сейчас онлайн

  def __init__(
      self,
      *,
      device_id: int,
      code: str,
      name: str,
      model: str,
      vendor: str,
      type_: str,
      description: str,
      params: Dict[str, Any],
      on_initial_ports: Callable[[int, List[Dict[str, Any]]], None],
      on_value: Callable[[int, Dict[str, Any]], None],
      on_connect: Optional[Callable[[int], None]] = None,
      on_disconnect: Optional[Callable[[int], None]] = None,
      http_timeout: float = 5.0,
      ping_interval: float = 20.0,
      reconnect_delay: float = 5.0,
      ws_port: int = 81,  # << новый параметр
  ):
    # публичные поля
    self.device_id = device_id
    self.id = device_id
    self.code = code
    self.name = name
    self.model = model
    self.vendor = vendor
    self.type = type_
    self.description = description
    self.params: Dict[str, Any] = dict(params or {})
    self.ip: Optional[str] = (self.params or {}).get("ip")

    # колбэки/настройки
    self.on_initial_ports = on_initial_ports
    self.on_value = on_value
    self.on_connect = on_connect
    self.on_disconnect = on_disconnect
    self.http_timeout = http_timeout
    self.ping_interval = ping_interval
    self.reconnect_delay = reconnect_delay
    self.ws_port = ws_port

    # runtime
    self._task: Optional[asyncio.Task] = None
    self._stop = asyncio.Event()
    self._ports: List[Dict[str, Any]] = []
    self._ports_index: Dict[str, Dict[str, Any]] = {}
    self._ports_lock = asyncio.Lock()

  # ---------- фабрика ----------
  @classmethod
  def from_db_device(
      cls,
      device: "DbDevices",
      *,
      on_initial_ports: Callable[[int, List[Dict[str, Any]]], None],
      on_value: Callable[[int, Dict[str, Any]], None],
      on_connect: Optional[Callable[[int], None]] = None,
      on_disconnect: Optional[Callable[[int], None]] = None,
  ) -> "MyHomeDeviceClient":
    if isinstance(device, dict):
      # если передали словарь, то создаём объект DbDevices
      return cls(
        device_id=device.get("id"),
        code=device.get("code", ""),
        name=device.get("name", ""),
        model=device.get("model", ""),
        vendor=device.get("vendor", ""),
        type_=device.get("type", ""),
        description=device.get("description", ""),
        params=device.get("params", {}),
        on_initial_ports=on_initial_ports,
        on_value=on_value,
        on_connect=on_connect,
        on_disconnect=on_disconnect,
      )
    return cls(
      device_id=device.id,
      code=device.code,
      name=device.name,
      model=device.model,
      vendor=device.vendor,
      type_=device.type,
      description=device.description or "",
      params=device.params or {},
      on_initial_ports=on_initial_ports,
      on_value=on_value,
      on_connect=on_connect,
      on_disconnect=on_disconnect,
    )

  @property
  def meta(self) -> Dict[str, Any]:
    return {
      "device_id": self.device_id,
      "id": self.id,
      "online": self._online,
      "code": self.code,
      "name": self.name,
      "model": self.model,
      "vendor": self.vendor,
      "type": self.type,
      "description": self.description,
      "params": self.params,
      "ip": self.ip,
    }

  # ---------- старт/стоп ----------
  def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
    loop = loop or asyncio.get_running_loop()
    if not self._task or self._task.done():
      self._stop.clear()
      self._task = loop.create_task(self._run_loop())

  async def stop(self):
    self._stop.set()
    if self._task:
      await asyncio.wait([self._task], timeout=2)

  # ---------- HTTP bootstrap ----------
  async def _fetch_values(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    if not self.ip:
      raise RuntimeError(f"Device {self.device_id}: IP is not set in params")
    url = f"http://{self.ip}/values"
    async with session.get(url, timeout=self.http_timeout) as r:
      txt = await r.text()
      if r.status != 200:
        raise RuntimeError(f"GET {url} -> {r.status}")
      payload = json.loads(txt)
    ports = flatten_ports(payload)

    now = datetime.now().isoformat()
    for p in ports:
      p["last_update"] = now

    async with self._ports_lock:
      self._ports = ports
      self._ports_index = {p["code"]: p for p in ports if p.get("code")}
    return ports

  # ---------- WS (порт 81) ----------
  async def _open_ws(self, session: aiohttp.ClientSession) -> aiohttp.ClientWebSocketResponse:
    if not self.ip:
      raise RuntimeError(f"Device {self.device_id}: IP is not set in params")
    url = f"ws://{self.ip}:{self.ws_port}/"
    print(f'[MyHomeDeviceClient][{self.device_id}] Connecting to WS:', url)
    return await session.ws_connect(url, autoping=True, heartbeat=self.ping_interval)

  @staticmethod
  def _parse_ws_line(line: str) -> Optional[Dict[str, Any]]:
    """Парсер TEXT-сообщений вида 'code#value'. Возвращает dict или None."""
    if not line:
      return None
    # Берём до первого '#'
    if "#" not in line:
      # если формат иной — можно расширить позже
      return None
    code, value = line.split("#", 1)
    code = code.strip()
    value = value.strip()
    if not code:
      return None
    # Ничего не предполагаем про тип значения — отдаём строкой как есть
    return {
      "code": code,  # например "clock.time" или "in.temp"
      "val": value,  # "23:44:06"
      "direction": None,
      "kind": None,
      "raw": line,
    }

  async def _run_loop(self):
    while not self._stop.is_set():
      try:
        async with aiohttp.ClientSession() as session:
          # 1) bootstrap
          ports = await self._fetch_values(session)
          self.on_initial_ports(self.device_id, ports)

          # 2) WS
          ws = await self._open_ws(session)
          self._online = True
          if self.on_connect:
            self.on_connect(self.device_id)

          async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
              event = self._parse_ws_line(msg.data)
              if not event:
                continue

              code = event["code"]
              now = datetime.now().isoformat()

              async with self._ports_lock:
                p = self._ports_index.get(code)
                if p is not None:
                  p["val"] = event["val"]
                  p["last_update"] = now
                else:
                  # создаём виртуальный порт для событий, которых нет в /values
                  self._ports_index[code] = {
                    "code": code,
                    "val": event["val"],
                    "last_update": now,
                    "direction": event.get("direction"),
                    "kind": event.get("kind"),
                    "raw": event["raw"],
                  }
                  self._ports.append(self._ports_index[code])

              # проброс наверх
              self.on_value(self.device_id, event)

      except Exception as e:
        self._online = False
        if self.on_disconnect:
          self.on_disconnect(self.device_id)
        print(f'[MyHomeDeviceClient][{self.device_id}] Error in WS loop, reconnecting...')
        print(f'Exception: {str(e)}')
        await asyncio.sleep(self.reconnect_delay)
      else:
        self._online = False
        if self.on_disconnect:
          self.on_disconnect(self.device_id)
        print(f'[MyHomeDeviceClient][{self.device_id}] Connection closed, reconnecting...')
        await asyncio.sleep(self.reconnect_delay)

  # ---------- публичные методы данных ----------
  async def get_ports_cached(self) -> List[Dict[str, Any]]:
    async with self._ports_lock:
      return list(self._ports)

  async def refresh_ports_http(self) -> List[Dict[str, Any]]:
    async with aiohttp.ClientSession() as session:
      ports = await self._fetch_values(session)
    self.on_initial_ports(self.device_id, ports)
    return ports

  # ---------- обновление параметров ----------
  async def update_params(self, patch: Dict[str, Any]) -> Dict[str, Any]:
    if not patch:
      return self.meta

    ip_before = self.ip
    top_fields = {"name", "description", "model", "vendor", "type"}
    top_updates = {k: v for k, v in patch.items() if k in top_fields}
    params_patch = patch.get("params") if isinstance(patch.get("params"), dict) else {}

    with db_session() as db:
      db_dev = db.query(DbDevices).filter(DbDevices.id == self.device_id).first()
      if not db_dev:
        raise RuntimeError(f"Device {self.device_id} not found")

      for k, v in top_updates.items():
        setattr(db_dev, k, v)
        setattr(self, k if k != "type" else "type", v)

      merged = dict(db_dev.params or {})
      merged.update(params_patch)
      db_dev.params = merged
      db.commit()
      db.refresh(db_dev)

      self.params = dict(db_dev.params or {})
      self.ip = self.params.get("ip")

    if ip_before != self.ip:
      try:
        await self.stop()
      except Exception:
        pass
      try:
        self.start()
      except Exception:
        pass

    return self.meta


def add_myhome_device_routes(
    app: APIRouter,
    *,
    resolver: Callable[[int], Optional["MyHomeDeviceClient"]],
):
  """
  Регистрирует REST-эндпоинты для работы с MyHome-устройствами.
  resolver(device_id) должен вернуть инстанс MyHomeDeviceClient или None.
  """
  global _ROUTES_ADDED
  if _ROUTES_ADDED:
    return
  _ROUTES_ADDED = True

  @app.get("/api/myhome/device/{device_id}", tags=['devices'])
  async def myhome_get_device_meta(device_id: int):
    client = resolver(device_id)
    if not client:
      return JSONResponse({"error": "device not found"}, 404)
    return client.meta

  @app.get("/api/myhome/device/{device_id}/ports", tags=['devices'])
  async def myhome_get_ports(device_id: int, refresh: bool = False):
    client = resolver(device_id)
    if not client:
      return JSONResponse({"error": "device not found"}, 404)
    if refresh:
      try:
        ports = await client.refresh_ports_http()
      except Exception as e:
        return JSONResponse({"error": str(e)}, 422)
    else:
      ports = await client.get_ports_cached()
      if not ports:
        try:
          ports = await client.refresh_ports_http()
        except Exception:
          # оставим пусто, если девайс сейчас недоступен
          ports = []
    return {"device": client.meta, "ports": ports}

  @app.post("/api/myhome/device/{device_id}/params", tags=['devices'])
  async def myhome_update_params(device_id: int, patch: Dict[str, Any]):
    client = resolver(device_id)
    if not client:
      return JSONResponse({"error": "device not found"}, 404)
    try:
      meta = await client.update_params(patch or {})
    except Exception as e:
      return JSONResponse({"error": str(e)}, 422)
    return meta
