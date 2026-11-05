"""Logical device mappings for the physical board representation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from db_models.devices import Devices
from utils.db_utils import db_session
from utils.logger import api_logger as logger


def _device_params(device: Devices) -> Dict[str, Any]:
    return dict(device.params) if isinstance(device.params, dict) else {}


def _physical_key(item: Dict[str, Any]) -> str:
    return "|".join(str(item.get(key) or "") for key in ("code", "direction", "kind"))


def _get_physical_ports(client: Any) -> List[Dict[str, Any]]:
    return list(getattr(client, "_ports", []) or [])


def _sanitize_mapping(item: Dict[str, Any], physical_by_key: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    result = {
        "id": str(item.get("id") or uuid4()),
        "name": str(item.get("name") or "Новое устройство").strip(),
        "description": str(item.get("description") or "").strip(),
        "device_type": str(item.get("device_type") or "generic"),
        "enabled": bool(item.get("enabled", True)),
        "parameters": [],
    }
    for parameter in item.get("parameters") or []:
        if not isinstance(parameter, dict):
            continue
        code = str(parameter.get("code") or "").strip()
        if not code:
            continue
        candidate = dict(parameter)
        candidate["code"] = code
        physical = physical_by_key.get(_physical_key(candidate))
        if physical is None:
            # Direction/kind can be omitted by old saved mappings.
            matches = [port for key, port in physical_by_key.items() if port.get("code") == code]
            physical = matches[0] if len(matches) == 1 else None
        if physical is None:
            raise ValueError(f"Параметр не найден на плате: {code}")
        result["parameters"].append({
            "key": str(candidate.get("key") or physical.get("code")),
            "code": physical.get("code"),
            "direction": physical.get("direction"),
            "kind": physical.get("kind"),
            "title": physical.get("title") or physical.get("code"),
            "value_type": physical.get("value_type"),
            "unit": physical.get("unit"),
            "block_id": physical.get("block_id"),
        })
    return result


def _validate_mappings(mappings: List[Dict[str, Any]]) -> None:
    used: Dict[str, str] = {}
    for logical in mappings:
        if not logical.get("name"):
            raise ValueError("Логическое устройство должно иметь имя")
        for parameter in logical.get("parameters", []):
            key = _physical_key(parameter)
            if key in used:
                raise ValueError(
                    f"Физический параметр {parameter.get('code')} уже используется в «{used[key]}»"
                )
            used[key] = logical["name"]


def add_logical_device_routes(app: APIRouter, *, resolver):
    @app.get("/api/myhome/device/{device_id}/logical-devices", tags=["devices"])
    async def get_logical_devices(device_id: int):
        client = resolver(device_id)
        if not client:
            return JSONResponse({"error": "Device not found"}, 404)
        with db_session() as db:
            device = db.query(Devices).filter(Devices.id == device_id).first()
            if not device:
                return JSONResponse({"error": "Device not found"}, 404)
            params = _device_params(device)
            mappings = params.get("logical_devices", [])
        physical = _get_physical_ports(client)
        return {
            "success": True,
            "view": "logical",
            "logical_devices": mappings if isinstance(mappings, list) else [],
            "physical_ports": physical,
        }

    @app.put("/api/myhome/device/{device_id}/logical-devices", tags=["devices"])
    async def save_logical_devices(device_id: int, payload: Dict[str, Any]):
        client = resolver(device_id)
        if not client:
            return JSONResponse({"error": "Device not found"}, 404)
        physical = _get_physical_ports(client)
        if not physical:
            try:
                physical = await client.refresh_ports_http()
            except Exception as error:
                return JSONResponse({"error": f"Не удалось получить физические параметры: {error}"}, 502)
        physical_by_key = {_physical_key(port): port for port in physical}
        try:
            mappings = [
                _sanitize_mapping(item, physical_by_key)
                for item in (payload.get("logical_devices") or [])
                if isinstance(item, dict)
            ]
            _validate_mappings(mappings)
        except ValueError as error:
            return JSONResponse({"success": False, "error": str(error)}, 422)

        with db_session() as db:
            device = db.query(Devices).filter(Devices.id == device_id).first()
            if not device:
                return JSONResponse({"error": "Device not found"}, 404)
            params = _device_params(device)
            params["logical_devices"] = mappings
            params["logical_devices_updated_at"] = datetime.now().isoformat()
            device.params = params
            db.commit()

        return {
            "success": True,
            "view": "logical",
            "logical_devices": mappings,
            "physical_ports": physical,
        }

    @app.delete("/api/myhome/device/{device_id}/logical-devices/{logical_id}", tags=["devices"])
    async def delete_logical_device(device_id: int, logical_id: str):
        with db_session() as db:
            device = db.query(Devices).filter(Devices.id == device_id).first()
            if not device:
                return JSONResponse({"error": "Device not found"}, 404)
            params = _device_params(device)
            mappings = params.get("logical_devices", [])
            updated = [item for item in mappings if str(item.get("id")) != logical_id]
            if len(updated) == len(mappings):
                return JSONResponse({"error": "Logical device not found"}, 404)
            params["logical_devices"] = updated
            params["logical_devices_updated_at"] = datetime.now().isoformat()
            device.params = params
            db.commit()
        return {"success": True, "logical_devices": updated}
