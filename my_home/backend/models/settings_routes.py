"""Small unified settings boundary with typed metadata and audit history."""
from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from db_models.devices import Devices
from utils.db_utils import db_session


def add_settings_routes(app: APIRouter):
    @app.get("/api/myhome/settings/schema", tags=["settings"])
    async def settings_schema():
        return {"success": True, "schema": {
            "connection": {"type": "object", "description": "WS/HTTP connection", "restart_required": False},
            "board": {"type": "object", "description": "Physical board settings", "restart_required": False},
            "logical": {"type": "object", "description": "Logical HA mapping", "restart_required": False},
            "module": {"type": "object", "description": "Add-on settings", "restart_required": False},
        }}

    @app.get("/api/myhome/device/{device_id}/settings", tags=["settings"])
    async def get_device_settings(device_id: int):
        with db_session() as db:
            device = db.query(Devices).filter(Devices.id == device_id).first()
            if not device:
                raise HTTPException(404, "Device not found")
            params = dict(device.params or {})
            return {"success": True, "settings": {"connection": {"ip": params.get("ip"), "ws_port": params.get("ws_port", 81)},
                    "board": params.get("board_settings", {}), "logical": params.get("logical_settings", {}),
                    "module": params.get("module_settings", {})}, "history": params.get("settings_history", [])[-50:]}

    @app.put("/api/myhome/device/{device_id}/settings", tags=["settings"])
    async def save_device_settings(device_id: int, payload: Dict[str, Any]):
        with db_session() as db:
            device = db.query(Devices).filter(Devices.id == device_id).first()
            if not device:
                raise HTTPException(404, "Device not found")
            params = dict(device.params or {})
            current = {"connection": {"ip": params.get("ip"), "ws_port": params.get("ws_port", 81)},
                       "board": params.get("board_settings", {}), "logical": params.get("logical_settings", {}),
                       "module": params.get("module_settings", {})}
            incoming = payload.get("settings") or {}
            changed = []
            for section in current:
                if section in incoming and incoming[section] != current[section]:
                    changed.append(section)
            connection = dict(current["connection"]); connection.update(incoming.get("connection") or {})
            if connection.get("ip") is not None: params["ip"] = connection["ip"]
            params["ws_port"] = int(connection.get("ws_port") or 81)
            for section, key in (("board", "board_settings"), ("logical", "logical_settings"), ("module", "module_settings")):
                if section in incoming: params[key] = incoming[section]
            history = list(params.get("settings_history") or [])
            history.append({"at": datetime.now().isoformat(), "source": payload.get("source", "ui"), "changed": changed})
            params["settings_history"] = history[-50:]
            device.params = params
            db.commit()
            return {"success": True, "changed": changed, "applied": True, "restart_required": False,
                    "saved_at": history[-1]["at"]}
