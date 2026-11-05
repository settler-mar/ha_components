"""API for universal MY_HOME module links."""

import asyncio
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from utils.module_links import ENDPOINT_SYSTEMS, HA_BINDING_MODES, ModuleLink, module_link_manager
from utils.socket_utils import connection_manager
from utils.command_dispatcher import DeviceCommandDispatcher
from utils.state_model import DeviceCommand


def _physical_port_item(port):
    return {
        "port_id": port.get("code"),
        "code": port.get("code"),
        "name": port.get("title") or port.get("name") or port.get("code"),
        "direction": port.get("direction"),
        "kind": port.get("kind"),
        "value_type": port.get("value_type") or port.get("type_raw"),
        "value": port.get("value", port.get("val")),
        "unit": port.get("unit"),
        "device_class": port.get("device_class"),
        "icon": port.get("icon"),
        "available": port.get("available", True),
    }


async def _physical_devices():
    from models.my_home import MyHomeClass
    result = []
    for device_id, client in MyHomeClass()._devices.items():
        ports = await client.get_ports_cached()
        result.append({
            "device_id": device_id,
            "name": getattr(client, "name", None) or f"ESP {device_id}",
            "ip": getattr(client, "ip", None),
            "online": bool(getattr(client, "_online", False)),
            "ports_count": len(ports or []),
        })
    return {"success": True, "devices": result}


async def _physical_ports(device_id):
    from models.my_home import MyHomeClass
    client = MyHomeClass().get_client(int(device_id))
    if not client:
        return {"success": False, "error": "device_not_found", "ports": []}
    ports = await client.get_ports_cached()
    return {"success": True, "device_id": device_id,
            "ports": [_physical_port_item(port) for port in (ports or [])]}


async def dispatch_link_value(link: ModuleLink, value_name: str, value: Any):
    """Send one producer value to its explicitly selected physical ESP port."""
    if link.mode != "physical":
        return {"success": True, "status": "not_physical"}
    spec = link.values.get(value_name)
    binding = (spec.physical_binding if spec else None) or {}
    if not spec or spec.direction != "producer_to_consumer":
        return {"success": True, "status": "feedback_value"}
    if not binding.get("device_id") or not binding.get("port_id"):
        return {"success": False, "status": "not_configured", "error": "physical_binding_required"}
    from models.my_home import MyHomeClass
    result = await DeviceCommandDispatcher(MyHomeClass().get_client).dispatch(DeviceCommand(
        device_id=int(binding["device_id"]),
        code=str(binding["port_id"]),
        value=value,
        source=f"module_link:{link.link_id}:{value_name}",
    ))
    return result


def ingest_physical_value(device_id: int, code: str, value: Any):
    """Accept feedback from the ESP event stream for physical bindings."""
    for link in module_link_manager.links.values():
        if link.mode != "physical":
            continue
        for value_name, spec in link.values.items():
            binding = spec.physical_binding or {}
            if str(binding.get("device_id")) != str(device_id) or str(binding.get("port_id")) != str(code):
                continue
            if spec.direction != "consumer_to_producer":
                continue
            link.update(value_name, value, quality="good")
            try:
                asyncio.create_task(_broadcast(link))
            except RuntimeError:
                pass
    module_link_manager.save()


async def ingest_ha_value(entity_id: str, value: Any):
    """Bridge a selected HA entity into the link contract and, in physical mode, ESP."""
    changed = False
    for link in module_link_manager.links.values():
        if link.mode not in {"physical", "virtual"}:
            continue
        for value_name, spec in link.values.items():
            binding = spec.ha_binding or {}
            if binding.get("mode") != "ha_entity" or binding.get("entity_id") != entity_id:
                continue
            if spec.direction != "producer_to_consumer":
                continue
            link.update(value_name, value, quality="good")
            dispatch_result = await dispatch_link_value(link, value_name, value)
            if not dispatch_result.get("success") and dispatch_result.get("status") != "not_physical":
                link.states[value_name].quality = "offline" if dispatch_result.get("error") in {"transport_unavailable", "command_timeout"} else "invalid"
                link.states[value_name].error = dispatch_result.get("error")
            changed = True
            await _broadcast(link)
    if changed:
        module_link_manager.save()


def _ha_registry_port(entity, state=None):
    """Return only the fields needed by the link picker; never expose HA credentials."""
    state = state or {}
    entity_id = entity.get("entity_id") or state.get("entity_id")
    attributes = state.get("attributes") or {}
    return {
        "port_id": entity_id,
        "entity_id": entity_id,
        "name": entity.get("name") or entity.get("original_name") or attributes.get("friendly_name") or entity_id,
        "domain": (entity_id or "").split(".", 1)[0],
        "state": state.get("state"),
        "unit_of_measurement": attributes.get("unit_of_measurement"),
        "device_class": attributes.get("device_class"),
        "icon": attributes.get("icon"),
    }


async def _load_ha_link_devices():
    from utils.ha_manager import ha_manager

    client = ha_manager.ha_client
    if not client or not client.connected or not client.authenticated:
        return {"success": False, "error": "ha_unavailable", "devices": []}
    devices_result = await client.send_command({"type": "config/device_registry/list"})
    entities_result = await client.send_command({"type": "config/entity_registry/list"})
    states_result = await client.get_states()
    if not devices_result.get("success") or not entities_result.get("success") or not states_result.get("success"):
        return {"success": False, "error": "ha_registry_unavailable", "devices": []}

    states = {item.get("entity_id"): item for item in states_result.get("result", [])}
    by_device = {}
    for entity in entities_result.get("result", []):
        device_id = entity.get("device_id") or "__unassigned__"
        by_device.setdefault(device_id, []).append(_ha_registry_port(entity, states.get(entity.get("entity_id"))))

    devices = []
    for device in devices_result.get("result", []):
        device_id = device.get("id")
        devices.append({
            "device_id": device_id,
            "name": device.get("name_by_user") or device.get("name") or device_id,
            "manufacturer": device.get("manufacturer"),
            "model": device.get("model"),
            "ports": sorted(by_device.pop(device_id, []), key=lambda item: item["name"] or ""),
        })
    if by_device.get("__unassigned__"):
        devices.append({
            "device_id": "__unassigned__",
            "name": "Сущности без устройства",
            "manufacturer": None,
            "model": None,
            "ports": sorted(by_device["__unassigned__"], key=lambda item: item["name"] or ""),
        })
    return {"success": True, "devices": sorted(devices, key=lambda item: item["name"] or "")}


async def _broadcast(link: ModuleLink, action: str = "state_update") -> None:
    try:
        from models.virtual_ports_routes import update_module_link_display_ports
        update_module_link_display_ports(link)
    except Exception:
        # Display publication must never make the module link fail.
        pass
    await connection_manager.broadcast({
        "type": "module_link",
        "action": action,
        "link_id": link.link_id,
        "data": link.to_dict(),
    })


def _default_profile() -> ModuleLink:
    ha = {"system": "home_assistant", "module": "floor_heating"}
    esp = {"system": "esp", "module": "boiler_ctrl"}

    def request_value(name, value_type, *, initial=None, on_stale=None, unit=None, minimum=None, maximum=None):
        return {
            "name": name, "direction": "producer_to_consumer", "value_type": value_type,
            "unit": unit, "minimum": minimum, "maximum": maximum, "initial": initial,
            "on_stale": on_stale, "timeout_s": 120, "source": ha, "target": esp,
            "ha_binding": {"mode": "none"},
        }

    def feedback_value(name, value_type, **kwargs):
        value = request_value(name, value_type, **kwargs)
        value["direction"] = "consumer_to_producer"
        value["source"] = esp
        value["target"] = ha
        return value

    return ModuleLink(
        link_id="floor-to-boiler",
        producer="floor_heating",
        consumer="boiler_ctrl",
        values={
            "ok": request_value("ok", "boolean", initial=False, on_stale=False),
            "boiler_enable": request_value("boiler_enable", "boolean", initial=False, on_stale=False),
            "boiler_temperature": request_value("boiler_temperature", "number", unit="°C", minimum=25, maximum=50, initial=25, on_stale=None),
            "demand_percent": request_value("demand_percent", "number", unit="%", minimum=0, maximum=100, initial=0, on_stale=0),
            "turbo": request_value("turbo", "boolean", initial=False, on_stale=False),
            "quality": request_value("quality", "string", initial="unknown", on_stale="unknown"),
            "ready": feedback_value("ready", "boolean", initial=False, on_stale=False),
            "supply": feedback_value("supply", "number", unit="°C", minimum=0, maximum=100, initial=None, on_stale=None),
        },
    )


def add_module_link_routes(app: APIRouter):
    profile = _default_profile()
    existing = module_link_manager.get(profile.link_id)
    if existing is None:
        module_link_manager.links[profile.link_id] = profile
        module_link_manager.save()
    else:
        changed = False
        for value_name, default_spec in profile.values.items():
            current_spec = existing.values.get(value_name)
            if current_spec is None:
                existing.values[value_name] = default_spec
                changed = True
                continue
            if not current_spec.source or not current_spec.source.get("system"):
                current_spec.source = default_spec.source
                changed = True
            if not current_spec.target or not current_spec.target.get("system"):
                current_spec.target = default_spec.target
                changed = True
            if not current_spec.ha_binding:
                current_spec.ha_binding = {"mode": "none"}
                changed = True
        if changed:
            existing.__post_init__()
            module_link_manager.save()

    @app.get("/api/module-links", tags=["module-links"])
    async def list_module_links():
        return {"success": True, "links": [link.to_dict() for link in module_link_manager.links.values()]}

    @app.get("/api/module-links/{link_id}", tags=["module-links"])
    async def get_module_link(link_id: str):
        link = module_link_manager.get(link_id)
        if not link:
            raise HTTPException(404, "module_link_not_found")
        return {"success": True, "link": link.to_dict()}

    @app.get("/api/module-links/ha/devices", tags=["module-links"])
    async def list_module_link_ha_devices():
        return await _load_ha_link_devices()

    @app.get("/api/module-links/ha/devices/{device_id}/ports", tags=["module-links"])
    async def list_module_link_ha_ports(device_id: str):
        data = await _load_ha_link_devices()
        if not data.get("success"):
            return data
        device = next((item for item in data["devices"] if str(item["device_id"]) == str(device_id)), None)
        return {"success": True, "device": device_id, "ports": device.get("ports", []) if device else []}

    @app.get("/api/module-links/virtual/devices", tags=["module-links"])
    async def list_module_link_virtual_devices():
        from models.virtual_devices_routes import _migrate_standalone_ports, _load
        _migrate_standalone_ports()
        devices = _load().get("devices", [])
        ports = {}
        from models.virtual_ports_routes import load_virtual_ports
        for port in load_virtual_ports().get("ports", []):
            device_id = port.get("virtual_device_id") or "__unassigned__"
            item = deepcopy(port)
            item["port_id"] = item.get("id")
            item["name"] = item.get("name") or item.get("entity_id") or item.get("id")
            ports.setdefault(device_id, []).append(item)
        result = []
        for device in devices:
            result.append({"device_id": device.get("id"), "name": device.get("name") or device.get("id"),
                           "description": device.get("description"), "ports": ports.pop(device.get("id"), [])})
        if ports.get("__unassigned__"):
            result.append({"device_id": "__unassigned__", "name": "Порты без устройства",
                           "description": None, "ports": ports["__unassigned__"]})
        return {"success": True, "devices": sorted(result, key=lambda item: item["name"] or "")}

    @app.get("/api/module-links/virtual/devices/{device_id}/ports", tags=["module-links"])
    async def list_module_link_virtual_ports(device_id: str):
        data = await list_module_link_virtual_devices()
        device = next((item for item in data["devices"] if str(item["device_id"]) == str(device_id)), None)
        return {"success": True, "device": device_id, "ports": device.get("ports", []) if device else []}

    @app.get("/api/module-links/physical/devices", tags=["module-links"])
    async def list_module_link_physical_devices():
        return await _physical_devices()

    @app.get("/api/module-links/physical/devices/{device_id}/ports", tags=["module-links"])
    async def list_module_link_physical_ports(device_id: str):
        return await _physical_ports(device_id)

    @app.put("/api/module-links/{link_id}", tags=["module-links"])
    async def update_module_link(link_id: str, payload: Dict[str, Any]):
        payload = {**payload, "link_id": link_id}
        try:
            link = module_link_manager.upsert(payload)
        except (TypeError, ValueError) as error:
            raise HTTPException(422, str(error))
        await _broadcast(link, "updated")
        return {"success": True, "link": link.to_dict()}

    @app.post("/api/module-links", tags=["module-links"])
    async def create_module_link(payload: Dict[str, Any]):
        link_id = str(payload.get("link_id") or "").strip()
        if not link_id:
            raise HTTPException(422, "link_id_required")
        if link_id in module_link_manager.links:
            raise HTTPException(409, "module_link_exists")
        try:
            link = module_link_manager.upsert(payload)
        except (TypeError, ValueError) as error:
            raise HTTPException(422, str(error))
        await _broadcast(link, "updated")
        return {"success": True, "link": link.to_dict()}

    @app.delete("/api/module-links/{link_id}", tags=["module-links"])
    async def delete_module_link(link_id: str):
        if link_id not in module_link_manager.links:
            raise HTTPException(404, "module_link_not_found")
        del module_link_manager.links[link_id]
        module_link_manager.save()
        await connection_manager.broadcast({
            "type": "module_link",
            "action": "deleted",
            "link_id": link_id,
        })
        return {"success": True}

    @app.post("/api/module-links/{link_id}/mode", tags=["module-links"])
    async def set_module_link_mode(link_id: str, payload: Dict[str, Any]):
        if link_id not in module_link_manager.links:
            raise HTTPException(404, "module_link_not_found")
        try:
            link = module_link_manager.set_mode(link_id, str(payload.get("mode")))
        except (KeyError, ValueError) as error:
            raise HTTPException(422, str(error))
        await _broadcast(link, "mode_changed")
        return {"success": True, "link": link.to_dict()}

    @app.post("/api/module-links/{link_id}/values/{value_name}", tags=["module-links"])
    async def update_module_link_value(link_id: str, value_name: str, payload: Dict[str, Any]):
        link = module_link_manager.get(link_id)
        if not link:
            raise HTTPException(404, "module_link_not_found")
        if link.mode == "disabled":
            raise HTTPException(409, "module_link_disabled")
        try:
            link.update(value_name, payload.get("value"), quality=str(payload.get("quality", "good")), error=payload.get("error"))
            dispatch_result = await dispatch_link_value(link, value_name, payload.get("value"))
            if not dispatch_result.get("success") and dispatch_result.get("status") != "not_physical":
                link.states[value_name].quality = "offline" if dispatch_result.get("error") in {"transport_unavailable", "command_timeout"} else "invalid"
                link.states[value_name].error = dispatch_result.get("error")
            module_link_manager.save()
        except (KeyError, ValueError) as error:
            raise HTTPException(422, str(error))
        await _broadcast(link)
        return {"success": True, "link": link.to_dict()}

    @app.put("/api/module-links/{link_id}/values/{value_name}/physical-binding", tags=["module-links"])
    async def update_module_link_physical_binding(link_id: str, value_name: str, payload: Dict[str, Any]):
        link = module_link_manager.get(link_id)
        if not link:
            raise HTTPException(404, "module_link_not_found")
        spec = link.values.get(value_name)
        if not spec:
            raise HTTPException(404, "unknown_value")
        binding = dict(payload.get("physical_binding") or {})
        if binding and (not str(binding.get("device_id") or "").strip() or not str(binding.get("port_id") or "").strip()):
            raise HTTPException(422, "physical_device_and_port_required")
        if binding:
            binding["device_id"] = int(binding["device_id"])
            binding["port_id"] = str(binding["port_id"])
        spec.physical_binding = binding
        module_link_manager.save()
        await _broadcast(link, "updated")
        return {"success": True, "link": link.to_dict()}

    @app.put("/api/module-links/{link_id}/values/{value_name}/binding", tags=["module-links"])
    async def update_module_link_binding(link_id: str, value_name: str, payload: Dict[str, Any]):
        link = module_link_manager.get(link_id)
        if not link:
            raise HTTPException(404, "module_link_not_found")
        spec = link.values.get(value_name)
        if not spec:
            raise HTTPException(404, "unknown_value")
        binding = dict(payload.get("ha_binding") or {})
        binding_mode = str(binding.get("mode") or "none")
        if binding_mode not in HA_BINDING_MODES:
            raise HTTPException(422, "invalid_ha_binding_mode")
        for endpoint_name in ("source", "target"):
            endpoint = payload.get(endpoint_name)
            if endpoint is None:
                continue
            endpoint = dict(endpoint)
            if str(endpoint.get("system") or "") not in ENDPOINT_SYSTEMS or not str(endpoint.get("module") or "").strip():
                raise HTTPException(422, f"invalid_{endpoint_name}_endpoint")
            setattr(spec, endpoint_name, endpoint)
        if binding_mode == "ha_entity":
            entity_id = str(binding.get("port_id") or binding.get("entity_id") or "").strip()
            if not entity_id or not str(binding.get("device_id") or "").strip():
                raise HTTPException(422, "ha_device_and_port_required")
            binding["device_id"] = str(binding["device_id"])
            binding["port_id"] = entity_id
            binding["entity_id"] = entity_id
        if binding_mode == "virtual_port":
            if not str(binding.get("device_id") or "").strip() or not str(binding.get("port_id") or binding.get("virtual_port_id") or "").strip():
                raise HTTPException(422, "virtual_device_and_port_required")
            binding["device_id"] = str(binding["device_id"])
            binding["port_id"] = str(binding.get("port_id") or binding["virtual_port_id"])
            binding["virtual_port_id"] = binding["port_id"]
        spec.ha_binding = binding
        module_link_manager.save()
        await _broadcast(link, "updated")
        return {"success": True, "link": link.to_dict()}

    @app.post("/api/module-links/{link_id}/display-ports", tags=["module-links"])
    async def create_module_link_display_port(link_id: str, payload: Dict[str, Any]):
        """Create a read-only virtual port for board/HA presentation."""
        link = module_link_manager.get(link_id)
        value_name = str(payload.get("value_name") or "")
        if not link:
            raise HTTPException(404, "module_link_not_found")
        if value_name not in link.values:
            raise HTTPException(422, "unknown_value")
        from models.virtual_ports_routes import (
            _generate_entity_id,
            load_virtual_ports,
            save_virtual_ports,
            sync_virtual_port_to_ha,
        )
        from uuid import uuid4
        data = load_virtual_ports()
        port_id = str(uuid4())
        name = str(payload.get("name") or f"{link.link_id} · {value_name}")
        port = {
            "id": port_id,
            "name": name,
            "entity_id": _generate_entity_id("sensor", f"module_link_{link_id}_{value_name}"),
            "type": "sensor",
            "description": "Read-only MY_HOME Link display port",
            "unit": link.values[value_name].unit,
            "unit_of_measurement": link.values[value_name].unit,
            "device_class": payload.get("device_class"),
            "icon": payload.get("icon", "mdi:link-variant"),
            "value": link.states.get(value_name).value if link.states.get(value_name) else link.values[value_name].initial,
            "initial_value": link.values[value_name].initial,
            "attributes": {"module_link_id": link_id, "module_link_value": value_name, "read_only": True, "physical_outputs_protected": True},
            "entity_category": "diagnostic",
            "source": "module_link_display",
            "binding": {"module_link_id": link_id, "value_name": value_name},
            "read_only": True,
            "physical_binding_allowed": False,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        data.setdefault("ports", []).append(port)
        save_virtual_ports(data)
        try:
            asyncio.create_task(sync_virtual_port_to_ha(port))
        except Exception:
            pass
        return {"success": True, "port": port}
