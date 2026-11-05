# services/myhome_device_client.py
import asyncio
import aiohttp
import time
from typing import Callable, Dict, Any, List, Optional
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from utils.device_protocol import DeviceProtocolAdapter, parse_ws_message, values_statistics
from utils.command_dispatcher import DeviceCommandDispatcher
from utils.state_model import DeviceCommand, DeviceState
from utils.db_utils import db_session
from db_models.devices import Devices as DbDevices
from db_models.ports import Ports as DbPorts
from utils.logs import log_print
from utils.logger import device_logger as logger
from datetime import datetime
from utils.diagnostics import diagnostics

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
    self._board_info: Dict[str, Any] = {}
    self._sync_state = DeviceState(device_id=device_id, online=False)

    # runtime
    self._task: Optional[asyncio.Task] = None
    self._stop = asyncio.Event()
    self._ports: List[Dict[str, Any]] = []
    self._ports_index: Dict[str, List[Dict[str, Any]]] = {}
    self._ports_lock = asyncio.Lock()
    self._command_lock = asyncio.Lock()
    self._ports_initialized = False  # Флаг для отслеживания инициализации портов
    self._last_uptime: Optional[float] = None
    self._config_monitor_task: Optional[asyncio.Task] = None

  # ---------- фабрика ----------
  @classmethod
  def is_ip_already_used(cls, ip: str, existing_devices: dict) -> bool:
    """
    Проверяет, используется ли IP адрес уже другим устройством
    """
    if not ip:
      return False
    for device_id, client in existing_devices.items():
      if hasattr(client, 'ip') and client.ip == ip:
        return True
    return False

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
      params = device.get("params", {})
      # Проверяем, что params - это словарь
      if not isinstance(params, dict):
        params = {}
      return cls(
        device_id=device.get("id"),
        code=device.get("code", ""),
        name=device.get("name", ""),
        model=device.get("model", ""),
        vendor=device.get("vendor", ""),
        type_=device.get("type", ""),
        description=device.get("description", ""),
        params=params,
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
      params=device.params if isinstance(device.params, dict) else {},
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
      "board_info": self._board_info,
      "device_uid": self._board_info.get("device_uid"),
      "board_role": self._board_info.get("role"),
      "firmware_version": self._board_info.get("firmware_version"),
      "hardware_model": self._board_info.get("hardware_model"),
      "sync": self._sync_state.to_dict(),
    }

  # ---------- старт/стоп ----------
  def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
    loop = loop or asyncio.get_running_loop()
    if not self._task or self._task.done():
      self._stop.clear()
      self._task = loop.create_task(self._run_loop())
      self._config_monitor_task = loop.create_task(self._config_monitor_loop())

  async def stop(self):
    self._stop.set()
    if self._config_monitor_task:
      self._config_monitor_task.cancel()
      self._config_monitor_task = None
    if self._task:
      await asyncio.wait([self._task], timeout=2)
    self._ports_initialized = False  # Сбрасываем флаг при остановке

  # ---------- HTTP bootstrap ----------
  async def _fetch_values(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    if not self.ip:
      raise RuntimeError(f"Device {self.device_id}: IP is not set in params")
    previous_offline_reason = self._sync_state.offline_reason
    self._sync_state.sync_status = "loading"
    started = time.monotonic()
    try:
      snapshot = await DeviceProtocolAdapter(self.ip, self.http_timeout).fetch_snapshot(session)
    except Exception as error:
      self._sync_state.sync_status = "error"
      self._sync_state.last_error = str(error)
      raise
    self._board_info = snapshot.info
    self._sync_state.http_latency_ms = round((time.monotonic() - started) * 1000, 1)
    ports = snapshot.ports

    old_ports = list(self._ports)
    previous_uptime = diagnostics.uptime_from_ports(old_ports)
    current_uptime = diagnostics.uptime_from_ports(snapshot.ports)
    self._last_uptime = current_uptime
    if (previous_uptime is not None and current_uptime is not None
        and current_uptime < previous_uptime):
      diagnostics.record(
        "crash_detected",
        f"Обнаружен сброс счётчика времени работы: {previous_uptime:g} → {current_uptime:g}",
        device_id=self.device_id, device_name=self.name, level="error",
        reason=previous_offline_reason or "uptime_reset",
        details={"previous_uptime": previous_uptime, "current_uptime": current_uptime},
      )
      await diagnostics.collect_coredump(
        device_id=self.device_id, device_name=self.name, ip=self.ip,
        previous_uptime=previous_uptime, current_uptime=current_uptime,
        reason=previous_offline_reason or "uptime_reset",
      )
      await diagnostics.inspect_configuration_after_crash(
        device_id=self.device_id, device_name=self.name, ip=self.ip,
        previous_uptime=previous_uptime, current_uptime=current_uptime,
        reason=previous_offline_reason or "uptime_reset",
        allow_loss_recovery=True,
      )
    elif diagnostics.has_config_policy(self.device_id):
      await diagnostics.inspect_configuration_after_crash(
        device_id=self.device_id, device_name=self.name, ip=self.ip,
        previous_uptime=previous_uptime, current_uptime=current_uptime,
        reason="protected_configuration_check",
      )
    key = lambda item: (item.get("code"), item.get("direction"), item.get("kind"))
    old_keys = {key(item) for item in old_ports if item.get("code")}
    new_keys = {key(item) for item in ports if item.get("code")}
    self._sync_state.last_diff = {
      "added_count": len(new_keys - old_keys),
      "removed_count": len(old_keys - new_keys),
      "has_changes": bool(new_keys - old_keys or old_keys - new_keys),
    } if old_ports else None

    now = datetime.now().isoformat()
    for p in ports:
      p["last_update"] = now

    async with self._ports_lock:
      self._ports = ports
      self._ports_index = {}
      for port in ports:
        if port.get("code"):
          self._ports_index.setdefault(port["code"], []).append(port)
    self._sync_state.sync_status = "synced"
    self._sync_state.snapshot_at = now
    self._sync_state.last_error = None
    self._sync_state.offline_reason = None
    return ports

  async def _config_monitor_loop(self):
    """Periodically verify explicitly protected configuration while WS is alive."""
    try:
      while not self._stop.is_set():
        await asyncio.sleep(60)
        if not self._online or not diagnostics.has_config_policy(self.device_id) or self._last_uptime is None:
          continue
        await diagnostics.inspect_configuration_after_crash(
          device_id=self.device_id, device_name=self.name, ip=self.ip,
          previous_uptime=self._last_uptime, current_uptime=self._last_uptime,
          reason="protected_configuration_periodic_check",
        )
    except asyncio.CancelledError:
      return
    except Exception as error:
      logger.warning(f"Device {self.device_id} config monitor stopped: {error}")

  # ---------- WS (порт 81) ----------
  async def _open_ws(self, session: aiohttp.ClientSession) -> aiohttp.ClientWebSocketResponse:
    if not self.ip:
      raise RuntimeError(f"Device {self.device_id}: IP is not set in params")
    url = f"ws://{self.ip}:{self.ws_port}/"
    logger.info(f"Device {self.device_id} connecting to WebSocket: {url}")
    # Некоторые версии WS-сервера на плате закрывают соединение в ответ на
    # WebSocket ping-фреймы. Канал платы остаётся текстовым, поэтому держим
    # соединение без aiohttp heartbeat и переподключаемся по факту закрытия.
    return await session.ws_connect(url, autoping=True, heartbeat=None)

  async def _run_loop(self):
    while not self._stop.is_set():
      try:
        async with aiohttp.ClientSession() as session:
          # 1) bootstrap
          ports = await self._fetch_values(session)
          # Вызываем on_initial_ports только если порты еще не были инициализированы
          if not self._ports_initialized:
            self.on_initial_ports(self.device_id, ports)
            self._ports_initialized = True

          # 2) WS
          ws = await self._open_ws(session)
          self._current_ws = ws  # Сохраняем ссылку на WebSocket для отправки команд
          self._online = True
          self._sync_state.online = True
          self._sync_state.sync_status = "synced"
          self._sync_state.offline_reason = None
          self._sync_state.ws_connected_at = datetime.now().isoformat()
          if self.on_connect:
            self.on_connect(self.device_id)

          async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
              event = parse_ws_message(msg.data, self._ports_index)
              if not event:
                continue

              code = event["code"]
              now = datetime.now().isoformat()

              async with self._ports_lock:
                matching_ports = self._ports_index.get(code, [])
                if not matching_ports:
                  # Do not invent ports from WS traffic. /values is the
                  # authoritative contract for the device port inventory.
                  logger.warning(
                    f"Device {self.device_id}: ignoring WS code not present in /values: {code}"
                  )
                  continue
                for port in matching_ports:
                  # Keep the raw legacy field and expose the normalized value.
                  port["val"] = event["val"]
                  port["value"] = event.get("value")
                  port["value_type"] = event.get("value_type")
                  port["last_update"] = now

                self._sync_state.last_event_at = now
                self._sync_state.last_error = None

                if len(matching_ports) > 1:
                  event["ambiguous"] = True

              # проброс наверх
              self.on_value(self.device_id, event)
            elif msg.type in (
              aiohttp.WSMsgType.CLOSED,
              aiohttp.WSMsgType.CLOSE,
              aiohttp.WSMsgType.ERROR,
            ):
              logger.warning(
                f"Device {self.device_id} WebSocket frame closed the connection: {msg.type}"
              )
              break

      except Exception as e:
        self._online = False
        self._sync_state.online = False
        self._sync_state.sync_status = "error"
        self._sync_state.last_error = str(e)
        self._sync_state.offline_reason = "websocket_error"
        self._sync_state.reconnect_count += 1
        self._current_ws = None  # Очищаем ссылку на WebSocket
        if self.on_disconnect:
          self.on_disconnect(self.device_id)
        logger.error(f"Device {self.device_id} WebSocket error, reconnecting: {str(e)}")
        await asyncio.sleep(self.reconnect_delay)
      else:
        self._online = False
        self._sync_state.online = False
        self._sync_state.sync_status = "stale"
        self._sync_state.offline_reason = "websocket_closed"
        self._sync_state.reconnect_count += 1
        self._current_ws = None  # Очищаем ссылку на WebSocket
        if self.on_disconnect:
          self.on_disconnect(self.device_id)
        logger.warning(f"Device {self.device_id} WebSocket connection closed, reconnecting...")
        await asyncio.sleep(self.reconnect_delay)

  # ---------- публичные методы данных ----------
  async def get_ports_cached(self) -> List[Dict[str, Any]]:
    async with self._ports_lock:
      return list(self._ports)

  def has_known_port(self, code: str) -> bool:
    """Whether code belongs to the latest authoritative /values response."""
    return bool(code and code in self._ports_index)

  async def refresh_ports_http(self) -> List[Dict[str, Any]]:
    async with aiohttp.ClientSession() as session:
      ports = await self._fetch_values(session)
    # Обновляем кэш портов без вызова on_initial_ports
    async with self._ports_lock:
      self._ports = ports
      self._ports_index = {}
      for port in ports:
        if port.get("code"):
          self._ports_index.setdefault(port["code"], []).append(port)
    return ports

  async def refresh_ports_http_with_diff(self) -> Dict[str, Any]:
    """Refresh the physical port inventory and report configuration changes."""
    old_ports = await self.get_ports_cached()
    new_ports = await self.refresh_ports_http()

    def key(port: Dict[str, Any]):
      return (port.get("code"), port.get("direction"), port.get("kind"))

    # Поля, изменение которых реально влияет на интеграцию с HA / отображение.
    # Технические поля (mqtt, href, block_id, extra, group_href) исключены:
    # они часто пересобираются платой без смысловых изменений.
    meaningful_fields = (
      "title", "direction", "kind", "type_raw", "unit",
      "group_title", "value_type",
    )

    def diff_fields(before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
      return [f for f in meaningful_fields if before.get(f) != after.get(f)]

    old_by_key = {key(port): port for port in old_ports if port.get("code")}
    new_by_key = {key(port): port for port in new_ports if port.get("code")}
    added = [new_by_key[item] for item in new_by_key.keys() - old_by_key.keys()]
    removed = [old_by_key[item] for item in old_by_key.keys() - new_by_key.keys()]
    changed = []
    for item in new_by_key.keys() & old_by_key.keys():
      before, after = old_by_key[item], new_by_key[item]
      fields = diff_fields(before, after)
      if fields:
        changed.append({"before": before, "after": after, "changed_fields": fields})

    return {
      "ports": new_ports,
      "changes": {
        "added": added,
        "removed": removed,
        "changed": changed,
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "has_changes": bool(added or removed or changed),
      },
      "refreshed_at": datetime.now().isoformat(),
    }

  async def send_command(self, code: str, value) -> bool:
    """
    Отправляет команду на устройство в формате ESP: "code#value"
    """
    async with self._command_lock:
      try:
        # Плата использует 0/255 для digital, а UI работает с 0/1.
        # Приводим значение на границе интеграции, не меняя прошивку.
        port = (self._ports_index.get(code) or [None])[0]
        kind = port.get("kind") if port else None
        if kind == "digital":
          if isinstance(value, bool):
            value = 255 if value else 0
          elif str(value).strip().lower() in {"true", "on", "yes", "1", "255"}:
            value = 255
          elif str(value).strip().lower() in {"false", "off", "no", "0"}:
            value = 0

        command = f"{code}#{value}"
        # Коротко ждём восстановление WS, если разрыв произошёл прямо перед
        # кликом. Это устраняет ложные отказы на границе переподключения.
        for attempt in range(2):
          ws = getattr(self, "_current_ws", None)
          if self._online and ws is not None:
            try:
              await ws.send_str(command)
              logger.info(f"Device {self.device_id} command sent: {command}")
              return True
            except Exception as error:
              logger.warning(
                f"Device {self.device_id} command attempt {attempt + 1} failed: {error}"
              )
          if attempt == 0:
            await asyncio.sleep(0.75)
        return False
      except Exception as e:
        logger.error(f"Device {self.device_id} error sending command: {e}")
        return False

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

    # Загружаем порты из базы данных
    db_ports = await get_ports_from_db(device_id)

    if refresh:
      try:
        ports = await client.refresh_ports_http()
        # Объединяем с данными из БД
        ports = merge_ports_with_db_data(ports, db_ports)
      except Exception as e:
        # Если устройство недоступно, используем данные из БД
        ports = db_ports
    else:
      ports = await client.get_ports_cached()
      if not ports:
        try:
          ports = await client.refresh_ports_http()
          # Объединяем с данными из БД
          ports = merge_ports_with_db_data(ports, db_ports)
        except Exception:
          # оставим данные из БД, если девайс сейчас недоступен
          ports = db_ports
      else:
        # Объединяем с данными из БД
        ports = merge_ports_with_db_data(ports, db_ports)

    return {"device": client.meta, "ports": ports}

  @app.get("/api/myhome/device/{device_id}/sync-status", tags=['devices'])
  async def myhome_sync_status(device_id: int):
    client = resolver(device_id)
    if not client:
      return JSONResponse({"success": False, "error": "device not found"}, 404)
    with db_session() as db:
      db_device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
      physical_sync = dict((db_device.params or {}).get("physical_sync") or {}) if db_device else {}
    return {
      "success": True,
      "device_id": device_id,
      "sync": client.meta.get("sync", {}),
      "physical_sync": physical_sync,
    }

  @app.post("/api/myhome/device/{device_id}/command", tags=['devices'])
  async def myhome_device_command(device_id: int, payload: Dict[str, Any]):
    """Send one normalized command to the board WS and report the result."""
    client = resolver(device_id)
    if not client:
      return JSONResponse({"success": False, "error": "device not found"}, 404)

    code = str(payload.get("code") or "").strip()
    if not code:
      return JSONResponse({"success": False, "error": "code is required"}, 422)
    if "value" not in payload:
      return JSONResponse({"success": False, "error": "value is required"}, 422)
    if not client.has_known_port(code):
      return JSONResponse({"success": False, "error": f"unknown port: {code}"}, 422)

    command = DeviceCommand(
      device_id=device_id,
      code=code,
      value=payload.get("value"),
      source=str(payload.get("source") or "ui"),
    )
    result = await DeviceCommandDispatcher(resolver).dispatch(command)
    if not result.get("success"):
      return JSONResponse(result, 503 if result.get("error") == "transport_unavailable" else 422)
    return result

  @app.post("/api/myhome/device/{device_id}/ports/refresh", tags=['devices'])
  async def myhome_refresh_ports(device_id: int):
    """Re-read the physical port inventory and return a diff without changing HA."""
    client = resolver(device_id)
    if not client:
      return JSONResponse({"error": "device not found"}, 404)
    try:
      result = await client.refresh_ports_http_with_diff()
      db_ports = await get_ports_from_db(device_id)
      result["ports"] = merge_ports_with_db_data(result["ports"], db_ports)
      with db_session() as db:
        db_device = db.query(DbDevices).filter(DbDevices.id == device_id).first()
        if db_device:
          params = dict(db_device.params or {})
          sync_data = dict(params.get("physical_sync") or {})
          history = list(sync_data.get("history") or [])
          history.append({
            "refreshed_at": result.get("refreshed_at"),
            "changes": result.get("changes", {}),
          })
          sync_data["last_refreshed_at"] = result.get("refreshed_at")
          sync_data["last_changes"] = result.get("changes", {})
          sync_data["history"] = history[-20:]
          params["physical_sync"] = sync_data
          db_device.params = params
          db.commit()
      return {
        "success": True,
        "device": client.meta,
        **result,
      }
    except Exception as e:
      logger.error(f"Device {device_id} port refresh failed: {e}")
      return JSONResponse({"success": False, "error": str(e)}, 502)

  @app.get("/api/myhome/device/{device_id}/protocol-statistics", tags=['devices'])
  async def myhome_protocol_statistics(device_id: int):
    """Return statistics of the normalized physical values contract."""
    client = resolver(device_id)
    if not client:
      return JSONResponse({"error": "device not found"}, 404)
    ports = await client.get_ports_cached()
    if not ports:
      try:
        ports = await client.refresh_ports_http()
      except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, 502)
    return {
      "success": True,
      "device": client.meta,
      "statistics": values_statistics(ports),
    }

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


async def get_ports_from_db(device_id: int) -> List[Dict[str, Any]]:
  """
  Загружает порты из базы данных
  """
  try:
    from utils.configs import config

    with db_session() as db:
      db_ports = db.query(DbPorts).filter(DbPorts.device_id == device_id).all()

      # Извлекаем данные из объектов SQLAlchemy внутри контекста сессии
      port_data_list = []
      for port in db_ports:
        port_data = {
          'code': port.code,
          'name': port.name,
          'label': port.label,
          'description': port.description,
          'type': port.type,
          'unit': port.unit,
          'groups_name': port.groups_name,
          'block_id': (port.params or {}).get('block_id'),
          'value_type': (port.params or {}).get('value_type'),
          'params': port.params or {}
        }
        port_data_list.append(port_data)

      # Обрабатываем данные вне контекста сессии
      ports = []
      for port_data in port_data_list:
        # Проверяем статус публикации через AppConfig
        is_published = await config.is_port_published(device_id, port_data['code'])
        entity_id = await config.get_entity_id(device_id, port_data['code']) if is_published else ''

        port_info = {
          'code': port_data['code'],
          'name': port_data['name'],
          'label': port_data['label'],
          'description': port_data['description'],
          'type': port_data['type'],
          'unit': port_data['unit'],
          'groups_name': port_data['groups_name'],
          'params': port_data['params'],
          'ha_published': is_published,
          'entity_id': entity_id,
          'device_class': port_data['params'].get('device_class', '') if port_data['params'] else '',
          'unit_of_measurement': port_data['params'].get('unit_of_measurement', '') if port_data['params'] else '',
          'icon': port_data['params'].get('icon', '') if port_data['params'] else '',
          'state_class': port_data['params'].get('state_class', '') if port_data['params'] else '',
          'entity_category': port_data['params'].get('entity_category', '') if port_data['params'] else '',
          'enabled_by_default': port_data['params'].get('enabled_by_default', 'true') if port_data[
            'params'] else 'true',
          'force_update': port_data['params'].get('force_update', 'false') if port_data['params'] else 'false',
          'suggested_display_precision': port_data['params'].get('suggested_display_precision', '') if port_data[
            'params'] else '',
          'attributes': port_data['params'].get('attributes', {}) if port_data['params'] else {},
          'ha_published_at': port_data['params'].get('ha_published_at', '') if port_data['params'] else ''
        }
        ports.append(port_info)

      return ports

  except Exception as e:
    logger.error(f"Error loading ports from database: {e}")
    return []


def merge_ports_with_db_data(device_ports: List[Dict[str, Any]], db_ports: List[Dict[str, Any]]) -> List[
  Dict[str, Any]]:
  """
  Объединяет порты с устройства с данными из базы данных
  """
  try:
    # Создаем индекс портов из БД по коду
    db_ports_index = {
      (port.get('code'), (port.get('params') or {}).get('direction')): port
      for port in db_ports
    }

    # Объединяем данные
    merged_ports = []
    for device_port in device_ports:
      port_code = device_port.get('code')
      db_port = db_ports_index.get((port_code, device_port.get('direction')))
      if db_port is None:
        db_port = db_ports_index.get((port_code, None))
      if db_port is not None:
        # Объединяем данные устройства с данными из БД
        merged_port = {**device_port, **db_port}
        merged_ports.append(merged_port)
      else:
        # Порт есть на устройстве, но нет в БД
        merged_ports.append(device_port)

    # Добавляем порты из БД, которых нет на устройстве
    device_codes = {(port.get('code'), port.get('direction')) for port in device_ports}
    for db_port in db_ports:
      db_key = (db_port.get('code'), (db_port.get('params') or {}).get('direction'))
      if db_key not in device_codes:
        merged_ports.append(db_port)

    return merged_ports

  except Exception as e:
    logger.error(f"Error merging ports: {e}")
    return device_ports
