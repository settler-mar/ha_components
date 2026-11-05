"""Virtual HA devices and ports with optional bindings to physical board parameters."""
from datetime import datetime
from copy import deepcopy
from typing import Any, Dict
from uuid import uuid4
import json
import os

from fastapi import APIRouter, HTTPException, Query
from utils.configs import get_data_dir
from utils.logger import api_logger as logger
from models.virtual_ports_routes import (
    load_virtual_ports, save_virtual_ports, sync_virtual_port_to_ha,
    delete_virtual_port_from_ha, _generate_entity_id,
)


def _path():
    return os.path.join(get_data_dir(), "virtual_devices.json")


def _load():
    try:
        with open(_path(), "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {"devices": []}
    except (FileNotFoundError, json.JSONDecodeError):
        return {"version": 1, "devices": []}


def _save(data):
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    with open(_path(), "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def _history(data, action, device_id, details=None):
    entries = list(data.get("history") or [])
    entries.append({"at": _now(), "action": action, "physical_device_id": device_id, "details": details or {}})
    data["history"] = entries[-100:]


def _now():
    return datetime.now().isoformat()


def propagate_bound_value(device_id: int, code: str, value: Any):
    """Update matching virtual ports and publish their state; never mutates mappings."""
    pdata = load_virtual_ports(); changed = False
    for port in pdata.get("ports", []):
        binding = port.get("binding") or {}
        if str(binding.get("device_id")) != str(device_id) or binding.get("physical_code") != code:
            continue
        port["value"] = value; port["last_source_update"] = _now(); port["last_seen"] = _now(); port["online"] = True; port["offline_reason"] = None; port["updated_at"] = _now(); changed = True
        try:
            from utils.ha_manager import ha_manager
            if ha_manager.ha_client and ha_manager.ha_client.connected:
                import asyncio
                asyncio.create_task(ha_manager.ha_client.set_state(port.get("entity_id"), str(value),
                    attributes={"virtual_binding": f"{device_id}:{code}", "friendly_name": port.get("name")}))
        except Exception as error:
            logger.debug("Virtual port state publish failed: %s", error)
    if changed: save_virtual_ports(pdata)


def mark_bound_ports_offline(device_id: int, reason="physical_device_offline"):
    pdata = load_virtual_ports(); changed = False
    for port in pdata.get("ports", []):
        binding = port.get("binding") or {}
        if str(binding.get("device_id")) == str(device_id):
            port["online"] = False; port["offline_reason"] = reason; port["updated_at"] = _now(); changed = True
    if changed: save_virtual_ports(pdata)


def _new_port(payload, device_id):
    port_id = str(payload.get("id") or uuid4())
    port_type = payload.get("type", "sensor")
    name = payload.get("name") or "Новый порт"
    return {**payload, "id": port_id, "virtual_device_id": device_id,
            "entity_id": payload.get("entity_id") or _generate_entity_id(port_type, f"{device_id}_{port_id[:8]}"),
            "source": payload.get("source", "manual"), "binding": payload.get("binding"),
            "online": payload.get("online", True), "last_seen": payload.get("last_seen"),
            "created_at": payload.get("created_at") or _now(), "updated_at": _now()}


def _physical_index():
    from models.my_home import MyHomeClass
    result = {}
    for device_id, client in MyHomeClass()._devices.items():
        for port in getattr(client, "_ports", []) or []:
            result[(str(device_id), str(port.get("code")))] = port
    return result


def _binding_status(port, physical):
    binding = port.get("binding") or {}
    if not binding.get("device_id") or not binding.get("physical_code"):
        return "unbound"
    key = (str(binding["device_id"]), str(binding["physical_code"]))
    if binding["physical_code"] == "__device_online__":
        from models.my_home import MyHomeClass
        return "bound" if MyHomeClass().get_client(binding["device_id"]) else "not_found"
    if key not in physical:
        return "not_found"
    expected = binding.get("signature")
    if expected and expected != {field: physical[key].get(field) for field in ("direction", "kind", "value_type")}:
        return "changed"
    return "bound"


def _port_availability(port, physical):
    binding = port.get("binding") or {}
    if binding.get("physical_code") == "__device_online__":
        from models.my_home import MyHomeClass
        client = MyHomeClass().get_client(binding.get("device_id"))
        online = bool(client and client._online)
        return {"online": online, "state": "online" if online else "offline",
                "last_seen": port.get("last_seen"), "reason": port.get("offline_reason")}
    source = physical.get((str(binding.get("device_id")), str(binding.get("physical_code"))))
    if not binding.get("device_id") or not binding.get("physical_code"):
        return {"online": True, "state": "virtual", "last_seen": port.get("last_seen")}
    if not source:
        return {"online": False, "state": "unavailable", "last_seen": port.get("last_seen"), "reason": "physical_parameter_not_found"}
    return {"online": bool(port.get("online", True)), "state": "online" if port.get("online", True) else "offline",
            "last_seen": port.get("last_seen"), "reason": port.get("offline_reason")}


def _migrate_standalone_ports():
    """Put legacy standalone ports into one explicit virtual device once."""
    pdata = load_virtual_ports()
    legacy = [item for item in pdata.get("ports", []) if not item.get("virtual_device_id")]
    if not legacy:
        return None
    data = _load()
    device = next((item for item in data["devices"] if item.get("id") == "imported_virtual_ports"), None)
    if not device:
        device = {"id": "imported_virtual_ports", "name": "Импортированные виртуальные порты",
                  "description": "Автоматически перенесены из старого раздела виртуальных портов",
                  "type": "generic", "tags": ["legacy", "import"], "created_at": _now(), "updated_at": _now()}
        data["devices"].append(device); _save(data)
    for port in legacy:
        port["virtual_device_id"] = device["id"]
        port.setdefault("source", "manual")
        port["updated_at"] = _now()
    save_virtual_ports(pdata)
    return device["id"]


def _device_physical(device_id):
    from models.my_home import MyHomeClass
    client = MyHomeClass().get_client(device_id)
    return client, list(getattr(client, "_ports", []) or []) if client else []


def _decorate_virtual_port(port, physical):
    """Add source and current-value metadata without making a device-level binding."""
    result = deepcopy(port)
    binding = result.get("binding") or {}
    source_device_id = binding.get("device_id")
    source_code = binding.get("physical_code")
    source = physical.get((str(source_device_id), str(source_code)))
    result["source_device_id"] = source_device_id
    result["source_port_code"] = source_code
    result["source_device_name"] = None
    if source_device_id is not None:
        from models.my_home import MyHomeClass
        client = MyHomeClass().get_client(source_device_id)
        result["source_device_name"] = getattr(client, "name", None) if client else None
    if source is not None:
        for field in ("current_value", "value", "val"):
            if field in source and source.get(field) is not None:
                result["current_value"] = source.get(field)
                break
        else:
            result["current_value"] = None
        result["unit_of_measurement"] = result.get("unit_of_measurement") or source.get("unit")
    elif source_code == "__device_online__":
        result["current_value"] = result["availability"].get("state")
    else:
        for field in ("value", "val"):
            if field in result and result.get(field) is not None:
                result["current_value"] = result.get(field)
                break
        else:
            result.setdefault("current_value", result.get("value"))
    result["published_to_ha"] = bool(result.get("published", False))
    result["binding_status"] = _binding_status(result, physical)
    result["availability"] = _port_availability(result, physical)
    return result


def _make_virtual_draft(device_id, payload):
    client, physical = _device_physical(device_id)
    if not client:
        raise HTTPException(404, "Device not found")
    source_type = payload.get("source_type", "port")
    selected = set(str(item) for item in (payload.get("selected_codes") or []))
    include_connection_status = "virtual.connection_status" in selected
    selected.discard("virtual.connection_status")
    selected = {code for code in selected if not code.startswith("virtual.")}
    if source_type == "board":
        selected_ports = physical
    elif source_type == "group":
        group = payload.get("group_title")
        selected_ports = [item for item in physical if item.get("group_title") == group]
    else:
        selected_ports = [item for item in physical if not selected or str(item.get("code")) in selected]
    selected_ports = [item for item in selected_ports if item.get("code")]
    target_id = payload.get("target_virtual_device_id")
    target = next((item for item in _load().get("devices", []) if item.get("id") == target_id), None) if target_id else None
    if target is None and payload.get("name"):
        requested_name = str(payload.get("name")).strip().casefold()
        target = next((item for item in _load().get("devices", [])
                       if str(item.get("name") or "").strip().casefold() == requested_name), None)
        target_id = target.get("id") if target else None
    ports = []
    for physical_port in selected_ports:
        is_output = physical_port.get("direction") == "out"
        ports.append({"name": physical_port.get("title") or physical_port.get("code"),
                      "type": "switch" if is_output and physical_port.get("kind") == "digital" else "sensor",
                      "physical_code": physical_port.get("code"), "device_id": device_id,
                      "unit_of_measurement": physical_port.get("unit"), "title": physical_port.get("title"),
                      "description": physical_port.get("description") or "",
                      "device_class": physical_port.get("device_class"), "icon": physical_port.get("icon"),
                      "signature": {field: physical_port.get(field) for field in ("direction", "kind", "value_type")},
                      "binding_status": "bound"})
    if include_connection_status:
        ports.insert(0, {"name": "Статус подключения", "type": "sensor",
                         "physical_code": "__device_online__", "device_id": device_id,
                         "unit_of_measurement": None, "title": "Статус подключения",
                         "value": "online" if client._online else "offline",
                         "signature": {}, "binding_status": "bound"})
    return {"version": 1, "source": {"device_id": device_id, "device_name": client.name,
            "type": source_type, "group_title": payload.get("group_title")},
            "target": {"id": target_id, "name": target.get("name") if target else payload.get("name") or f"{client.name} — виртуальное устройство",
                       "tags": payload.get("tags") or (target.get("tags") if target else [])},
            "ports": ports, "created_at": _now()}


def add_virtual_devices_routes(app: APIRouter):
    @app.get("/api/myhome/device/{device_id}/ha/virtual-overview", tags=["home-assistant"])
    async def physical_virtual_overview(device_id: int):
        client, physical = _device_physical(device_id)
        if not client: raise HTTPException(404, "Device not found")
        pdata = load_virtual_ports().get("ports", []); physical_map = _physical_index()
        usage = {}
        for port in pdata:
            binding = port.get("binding") or {}
            if str(binding.get("device_id")) == str(device_id) and binding.get("physical_code"):
                usage.setdefault(binding["physical_code"], []).append({"virtual_device_id": port.get("virtual_device_id"), "virtual_port_id": port.get("id"), "name": port.get("name"), "entity_id": port.get("entity_id"), "status": _binding_status(port, physical_map), "published_to_ha": bool(port.get("published", False)), "current_value": port.get("value")})
        items = []
        for item in physical:
            items.append({**item, "online": bool(client._online), "virtual_usage": usage.get(item.get("code"), []), "virtual_status": "used" if item.get("code") in usage else "unused"})
        data = _load()
        return {"success": True, "device_id": device_id, "device_name": client.name, "physical_ports": items,
                "virtual_devices": data.get("devices", []), "history": data.get("history", [])[-20:]}

    @app.post("/api/myhome/device/{device_id}/ha/virtual-draft", tags=["home-assistant"])
    async def create_virtual_draft(device_id: int, payload: Dict[str, Any]):
        return {"success": True, "draft": _make_virtual_draft(device_id, payload)}

    @app.post("/api/myhome/device/{device_id}/ha/virtual-draft/preview", tags=["home-assistant"])
    async def preview_virtual_draft(device_id: int, payload: Dict[str, Any]):
        draft = payload.get("draft") or _make_virtual_draft(device_id, payload)
        target_id = (draft.get("target") or {}).get("id")
        existing = next((item for item in _load().get("devices", []) if item.get("id") == target_id), None) if target_id else None
        existing_ports = [item for item in load_virtual_ports().get("ports", []) if item.get("virtual_device_id") == target_id] if target_id else []
        existing_bindings = {(str((item.get("binding") or {}).get("device_id")), (item.get("binding") or {}).get("physical_code")) for item in existing_ports}
        requested_bindings = {(str(item.get("device_id") or device_id), item.get("physical_code")) for item in draft.get("ports", [])}
        return {"success": True, "draft": draft, "diff": {"device": "update" if existing else "create",
                "ports_to_add": sorted({code for _, code in (requested_bindings - existing_bindings)}),
                "ports_existing": sorted({code for _, code in (requested_bindings & existing_bindings)}),
                "ports_to_remove": []}, "requires_confirmation": True}

    @app.post("/api/myhome/device/{device_id}/ha/virtual-draft/apply", tags=["home-assistant"])
    async def apply_virtual_draft(device_id: int, payload: Dict[str, Any]):
        if payload.get("confirmed") is not True: raise HTTPException(409, "Explicit confirmation is required")
        draft = payload.get("draft") or _make_virtual_draft(device_id, payload)
        data = _load(); target = draft.get("target") or {}; target_id = target.get("id") or str(uuid4())
        device = next((item for item in data["devices"] if item.get("id") == target_id), None)
        if not device:
            device = {"id": target_id, "name": target.get("name") or "Виртуальное устройство", "description": "",
                      "type": "generic", "tags": sorted(set(target.get("tags") or [])), "created_at": _now(), "updated_at": _now()}
            data["devices"].append(device)
        else:
            device["name"] = target.get("name") or device.get("name"); device["tags"] = sorted(set(target.get("tags") or device.get("tags") or [])); device["updated_at"] = _now()
        pdata = load_virtual_ports(); created = []; seen_bindings = set()
        for spec in draft.get("ports", []):
            source_device_id = spec.get("device_id", device_id)
            binding_key = (str(source_device_id), str(spec.get("physical_code")))
            if binding_key in seen_bindings:
                continue
            seen_bindings.add(binding_key)
            existing = next((item for item in pdata.get("ports", [])
                             if item.get("virtual_device_id") == target_id
                             and str((item.get("binding") or {}).get("device_id")) == binding_key[0]
                             and (item.get("binding") or {}).get("physical_code") == spec.get("physical_code")), None)
            if existing:
                existing.update({key: spec.get(key) for key in ("name", "type", "unit_of_measurement", "description", "device_class", "icon") if spec.get(key) is not None})
                existing["binding"] = {"device_id": source_device_id, "physical_code": spec["physical_code"], "signature": spec.get("signature")}; existing["updated_at"] = _now(); created.append(existing["id"]); continue
            port = _new_port({"name": spec.get("name"), "type": spec.get("type", "sensor"), "unit_of_measurement": spec.get("unit_of_measurement"), "value": spec.get("value"), "description": spec.get("description") or "", "device_class": spec.get("device_class"), "icon": spec.get("icon"), "source": "physical", "binding": {"device_id": source_device_id, "physical_code": spec.get("physical_code"), "signature": spec.get("signature")}}, target_id)
            pdata.setdefault("ports", []).append(port); created.append(port["id"])
        _history(data, "apply_virtual_draft", device_id, {"virtual_device_id": target_id, "ports": created})
        _save(data); save_virtual_ports(pdata)
        return {"success": True, "virtual_device_id": target_id, "ports": created, "applied": True, "manual": True}

    @app.post("/api/myhome/device/{device_id}/ha/virtual-draft/publish", tags=["home-assistant"])
    async def publish_virtual_draft(device_id: int, payload: Dict[str, Any]):
        if payload.get("confirmed") is not True: raise HTTPException(409, "Explicit confirmation is required")
        applied = await apply_virtual_draft(device_id, {"confirmed": True, "draft": payload.get("draft")})
        virtual_id = applied["virtual_device_id"]
        device_result = next((item for item in _load().get("devices", []) if item.get("id") == virtual_id), None)
        ports = [item for item in load_virtual_ports().get("ports", []) if item.get("virtual_device_id") == virtual_id]
        published = [port["id"] for port in ports if await sync_virtual_port_to_ha(port)]
        data = _load(); _history(data, "publish_virtual_draft", device_id, {"virtual_device_id": virtual_id, "published": published}); _save(data)
        return {"success": len(published) == len(ports), "virtual_device_id": virtual_id, "published": published, "manual": True}

    @app.get("/api/virtual-devices", tags=["virtual-devices"])
    async def list_virtual_devices(tag: str | None = Query(default=None)):
        _migrate_standalone_ports()
        devices = _load().get("devices", [])
        if tag:
            devices = [item for item in devices if tag in (item.get("tags") or [])]
        ports = load_virtual_ports().get("ports", [])
        physical = _physical_index()
        by_device = {}
        for port in ports:
            if port.get("virtual_device_id"):
                item = _decorate_virtual_port(port, physical)
                by_device.setdefault(port["virtual_device_id"], []).append(item)
        result = []
        for device in devices:
            item = deepcopy(device)
            item["ports"] = by_device.get(device["id"], [])
            result.append(item)
        return {"success": True, "devices": result, "tags": sorted({tag for item in result for tag in item.get("tags", [])})}

    @app.get("/api/virtual-devices/physical-parameters", tags=["virtual-devices"])
    async def physical_parameters():
        from models.my_home import MyHomeClass
        result = []
        for device_id, client in MyHomeClass()._devices.items():
            for port in await client.get_ports_cached():
                result.append({"device_id": device_id, "device_name": client.name, **port})
        return {"success": True, "parameters": result}

    @app.get("/api/virtual-devices/{device_id}", tags=["virtual-devices"])
    async def get_virtual_device(device_id: str):
        _migrate_standalone_ports()
        device = next((item for item in _load().get("devices", []) if item.get("id") == device_id), None)
        if not device:
            raise HTTPException(404, "Virtual device not found")
        physical = _physical_index()
        ports = []
        for item in load_virtual_ports().get("ports", []):
            if item.get("virtual_device_id") == device_id:
                ports.append(_decorate_virtual_port(item, physical))
        return {"success": True, "device": {**device, "ports": ports}}

    @app.post("/api/virtual-devices", tags=["virtual-devices"])
    async def create_virtual_device(payload: Dict[str, Any]):
        data = _load()
        device_id = str(payload.get("id") or uuid4())
        if any(item.get("id") == device_id for item in data["devices"]):
            raise HTTPException(409, "Virtual device already exists")
        requested_name = str(payload.get("name") or "Новое устройство").strip().casefold()
        if any(str(item.get("name") or "").strip().casefold() == requested_name for item in data["devices"]):
            raise HTTPException(409, "Virtual device name already exists; use it to extend the existing device")
        device = {"id": device_id, "name": payload.get("name") or "Новое устройство",
                  "description": payload.get("description", ""), "type": payload.get("type", "generic"),
                  "tags": sorted(set(payload.get("tags") or [])), "created_at": _now(), "updated_at": _now()}
        data["devices"].append(device); _save(data)
        return {"success": True, "device": {**device, "ports": []}}

    @app.put("/api/virtual-devices/{device_id}", tags=["virtual-devices"])
    async def update_virtual_device(device_id: str, payload: Dict[str, Any]):
        data = _load(); device = next((item for item in data["devices"] if item.get("id") == device_id), None)
        if not device: raise HTTPException(404, "Virtual device not found")
        for key in ("name", "description", "type"):
            if key in payload: device[key] = payload[key]
        if "tags" in payload: device["tags"] = sorted(set(payload.get("tags") or []))
        device["updated_at"] = _now(); _save(data)
        return {"success": True, "device": device}

    @app.post("/api/virtual-devices/{device_id}/copy", tags=["virtual-devices"])
    async def copy_virtual_device(device_id: str, payload: Dict[str, Any] | None = None):
        data = _load(); source = next((item for item in data["devices"] if item.get("id") == device_id), None)
        if not source: raise HTTPException(404, "Virtual device not found")
        new_id = str(uuid4()); copy = deepcopy(source); copy.update({"id": new_id,
            "name": (payload or {}).get("name") or f"{source['name']} — копия", "created_at": _now(), "updated_at": _now()})
        data["devices"].append(copy); _save(data)
        pdata = load_virtual_ports(); copied = []
        for port in pdata.get("ports", []):
            if port.get("virtual_device_id") != device_id: continue
            item = deepcopy(port); item["id"] = str(uuid4()); item["virtual_device_id"] = new_id
            item["entity_id"] = _generate_entity_id(item.get("type", "sensor"), f"{new_id}_{item['id'][:8]}")
            item["updated_at"] = _now(); pdata["ports"].append(item); copied.append(item)
        save_virtual_ports(pdata)
        return {"success": True, "device": {**copy, "ports": copied}}

    @app.delete("/api/virtual-devices/{device_id}", tags=["virtual-devices"])
    async def delete_virtual_device(device_id: str):
        data = _load(); device = next((item for item in data["devices"] if item.get("id") == device_id), None)
        if not device: raise HTTPException(404, "Virtual device not found")
        data["devices"] = [item for item in data["devices"] if item.get("id") != device_id]; _save(data)
        pdata = load_virtual_ports(); removed = [item for item in pdata.get("ports", []) if item.get("virtual_device_id") == device_id]
        pdata["ports"] = [item for item in pdata.get("ports", []) if item.get("virtual_device_id") != device_id]; save_virtual_ports(pdata)
        return {"success": True, "removed_ports": len(removed)}

    @app.post("/api/virtual-devices/{device_id}/ports", tags=["virtual-devices"])
    async def create_device_port(device_id: str, payload: Dict[str, Any]):
        data = _load()
        if not any(item.get("id") == device_id for item in data["devices"]): raise HTTPException(404, "Virtual device not found")
        pdata = load_virtual_ports(); port = _new_port(payload, device_id); pdata.setdefault("ports", []).append(port); save_virtual_ports(pdata)
        return {"success": True, "port": port}

    @app.post("/api/virtual-devices/{device_id}/ports/{port_id}/copy", tags=["virtual-devices"])
    async def copy_device_port(device_id: str, port_id: str):
        pdata = load_virtual_ports(); source = next((item for item in pdata.get("ports", []) if item.get("id") == port_id and item.get("virtual_device_id") == device_id), None)
        if not source: raise HTTPException(404, "Virtual port not found")
        item = deepcopy(source); item["id"] = str(uuid4()); item["name"] = f"{source.get('name', 'Порт')} — копия"; item["entity_id"] = _generate_entity_id(item.get("type", "sensor"), f"{device_id}_{item['id'][:8]}"); item["updated_at"] = _now(); pdata["ports"].append(item); save_virtual_ports(pdata)
        return {"success": True, "port": item}

    @app.put("/api/virtual-devices/{device_id}/ports/{port_id}/move", tags=["virtual-devices"])
    async def move_device_port(device_id: str, port_id: str, payload: Dict[str, Any]):
        target_id = str(payload.get("target_virtual_device_id") or "")
        if not target_id or target_id == str(device_id):
            raise HTTPException(400, "A different target virtual device is required")
        data = _load()
        if not any(item.get("id") == target_id for item in data["devices"]):
            raise HTTPException(404, "Target virtual device not found")
        pdata = load_virtual_ports()
        port = next((item for item in pdata.get("ports", [])
                     if item.get("id") == port_id and str(item.get("virtual_device_id")) == str(device_id)), None)
        if not port:
            raise HTTPException(404, "Virtual port not found")
        physical_code = (port.get("binding") or {}).get("physical_code")
        duplicate = next((item for item in pdata.get("ports", [])
                          if str(item.get("virtual_device_id")) == target_id
                          and (item.get("binding") or {}).get("physical_code") == physical_code), None)
        if duplicate:
            raise HTTPException(409, "This physical parameter already exists in the target virtual device")
        port["virtual_device_id"] = target_id
        port["published"] = False
        port["updated_at"] = _now()
        save_virtual_ports(pdata)
        return {"success": True, "port": port, "requires_publish": True}

    @app.post("/api/virtual-devices/{device_id}/publish", tags=["virtual-devices"])
    async def publish_virtual_device(device_id: str):
        result = await get_virtual_device(device_id); published = []
        for port in result["device"].get("ports", []):
            if await sync_virtual_port_to_ha(port): published.append(port["id"])
        return {"success": len(published) == len(result["device"].get("ports", [])), "published": published, "manual": True}


    @app.put("/api/virtual-devices/{device_id}/ports/{port_id}", tags=["virtual-devices"])
    async def update_device_port(device_id: str, port_id: str, payload: Dict[str, Any]):
        pdata = load_virtual_ports(); port = next((item for item in pdata.get("ports", []) if item.get("id") == port_id and item.get("virtual_device_id") == device_id), None)
        if not port: raise HTTPException(404, "Virtual port not found")
        for key, value in payload.items():
            if key not in {"id", "virtual_device_id", "created_at"}: port[key] = value
        port["updated_at"] = _now(); save_virtual_ports(pdata)
        return {"success": True, "port": port}

    @app.delete("/api/virtual-devices/{device_id}/ports/{port_id}", tags=["virtual-devices"])
    async def delete_device_port(device_id: str, port_id: str):
        pdata = load_virtual_ports(); port = next((item for item in pdata.get("ports", []) if item.get("id") == port_id and item.get("virtual_device_id") == device_id), None)
        if not port: raise HTTPException(404, "Virtual port not found")
        pdata["ports"] = [item for item in pdata.get("ports", []) if item.get("id") != port_id]; save_virtual_ports(pdata)
        if port.get("entity_id"): await delete_virtual_port_from_ha(port["entity_id"])
        return {"success": True}
