"""Manual publication of logical device mappings to Home Assistant."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from db_models.devices import Devices
from utils.db_utils import db_session
from utils.ha_manager import ha_manager


def _slug(value: Any) -> str:
    text = re.sub(r"[^a-z0-9_]+", "_", str(value).lower())
    return text.strip("_") or "item"


def _domain_for(logical: Dict[str, Any], parameter: Dict[str, Any], profile: str | None) -> str:
    selected = profile or logical.get("ha_profile") or logical.get("device_type")
    if selected in {"switch", "sensor", "binary_sensor", "number", "select", "text", "light", "climate"}:
        return selected
    return "switch" if parameter.get("direction") == "out" and parameter.get("kind") == "digital" else "sensor"


def _port_value(port: Dict[str, Any]) -> str:
    value = port.get("value", port.get("val"))
    if isinstance(value, bool):
        return "on" if value else "off"
    return "unknown" if value is None or value == "" else str(value)


def _find_port(ports: List[Dict[str, Any]], parameter: Dict[str, Any]) -> Dict[str, Any] | None:
    code = str(parameter.get("code") or "")
    matches = [port for port in ports if port.get("code") == code]
    if parameter.get("direction"):
        matches = [port for port in matches if port.get("direction") == parameter.get("direction")] or matches
    if parameter.get("kind"):
        matches = [port for port in matches if port.get("kind") == parameter.get("kind")] or matches
    return matches[0] if matches else None


def _entity_id(device_id: int, logical_id: str, parameter: Dict[str, Any], domain: str) -> str:
    return f"{domain}.myhome_d{device_id}_{_slug(logical_id)}_{_slug(parameter.get('key') or parameter.get('code'))}"


def add_logical_ha_routes(app: APIRouter, *, resolver):
    @app.post("/api/myhome/device/{device_id}/logical-devices/publish", tags=["home-assistant"])
    async def publish_logical_devices(device_id: int, payload: Dict[str, Any]):
        client = resolver(device_id)
        if not client:
            return JSONResponse({"success": False, "error": "Device not found"}, 404)

        logical_ids = {str(item) for item in (payload.get("logical_ids") or [])}
        profile = payload.get("profile")
        physical = await client.get_ports_cached()
        if not physical:
            try:
                physical = await client.refresh_ports_http()
            except Exception as error:
                return JSONResponse({"success": False, "error": str(error)}, 502)

        with db_session() as db:
            device = db.query(Devices).filter(Devices.id == device_id).first()
            if not device:
                return JSONResponse({"success": False, "error": "Device not found"}, 404)
            params = dict(device.params or {})
            mappings = params.get("logical_devices") if isinstance(params.get("logical_devices"), list) else []

        selected = [item for item in mappings if not logical_ids or str(item.get("id")) in logical_ids]
        if not selected:
            return JSONResponse({"success": False, "error": "Нет логических устройств для публикации"}, 422)

        results: List[Dict[str, Any]] = []
        errors: List[str] = []
        for logical in selected:
            logical_id = str(logical.get("id"))
            published_entities = []
            registry = await ha_manager.ha_client.ensure_device_registry(
                stable_id=f"device_{device_id}_logical_{logical_id}",
                name=str(logical.get("name") or logical_id),
                manufacturer=str(client.vendor or "MY_HOME"),
                model=f"{client.model or 'MY_HOME'} logical device",
                sw_version=client.meta.get("firmware_version"),
            )
            for parameter in logical.get("parameters") or []:
                port = _find_port(physical, parameter)
                if not port:
                    errors.append(f"{logical.get('name')}: параметр {parameter.get('code')} не найден")
                    continue
                domain = _domain_for(logical, parameter, profile)
                parameter_key = parameter.get("key") or parameter.get("code")
                previous_entity = next((item.get("entity_id") for item in (logical.get("ha_entities") or [])
                                        if item.get("parameter_key") == parameter_key), None)
                entity_id = previous_entity or _entity_id(device_id, logical_id, parameter, domain)
                attributes = {
                    "friendly_name": f"{logical.get('name') or logical_id} — {parameter.get('title') or parameter.get('code')}",
                    "myhome_device_id": device_id,
                    "myhome_logical_device_id": logical_id,
                    "myhome_physical_code": parameter.get("code"),
                    "myhome_source": "logical_mapping",
                }
                if registry.get("device_id"):
                    attributes["device_id"] = registry["device_id"]
                if parameter.get("unit"):
                    attributes["unit_of_measurement"] = parameter["unit"]
                result = await ha_manager.ha_client._create_entity_via_rest(
                    entity_id, _port_value(port), attributes
                )
                if result.get("success"):
                    published_entities.append({
                        "entity_id": entity_id,
                        "parameter_key": parameter_key,
                        "physical_code": parameter.get("code"),
                        "domain": domain,
                    })
                else:
                    errors.append(f"{entity_id}: {result.get('error', 'ошибка HA')}")

            logical["ha_entities"] = published_entities
            logical["ha_published_at"] = datetime.now().isoformat()
            results.append({
                "logical_id": logical_id,
                "name": logical.get("name"),
                "entities": published_entities,
                "ha_device_id": registry.get("device_id"),
                "ha_device_registry": registry,
            })

        with db_session() as db:
            device = db.query(Devices).filter(Devices.id == device_id).first()
            params = dict(device.params or {})
            params["logical_devices"] = mappings
            device.params = params
            db.commit()

        return {
            "success": not errors,
            "published": results,
            "errors": errors,
            "manual": True,
        }

    @app.delete("/api/myhome/device/{device_id}/logical-devices/{logical_id}/publish", tags=["home-assistant"])
    async def unpublish_logical_device(device_id: int, logical_id: str):
        with db_session() as db:
            device = db.query(Devices).filter(Devices.id == device_id).first()
            if not device:
                return JSONResponse({"success": False, "error": "Device not found"}, 404)
            params = dict(device.params or {})
            mappings = params.get("logical_devices") if isinstance(params.get("logical_devices"), list) else []
            logical = next((item for item in mappings if str(item.get("id")) == logical_id), None)
            if not logical:
                return JSONResponse({"success": False, "error": "Logical device not found"}, 404)
            entities = list(logical.get("ha_entities") or [])

        results = []
        errors = []
        for item in entities:
            result = await ha_manager.ha_client.delete_port(item.get("entity_id"))
            if result.get("success"):
                results.append(item.get("entity_id"))
            else:
                errors.append(f"{item.get('entity_id')}: {result.get('error', 'ошибка HA')}")

        with db_session() as db:
            device = db.query(Devices).filter(Devices.id == device_id).first()
            params = dict(device.params or {})
            mappings = params.get("logical_devices") if isinstance(params.get("logical_devices"), list) else []
            for item in mappings:
                if str(item.get("id")) == logical_id:
                    item["ha_entities"] = []
                    item["ha_unpublished_at"] = datetime.now().isoformat()
            params["logical_devices"] = mappings
            device.params = params
            db.commit()

        return {"success": not errors, "deleted": results, "errors": errors, "manual": True}
