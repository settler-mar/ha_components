"""Explicit health/readiness view for boards and the HA bridge."""
from datetime import datetime
from fastapi import APIRouter
from db_models.devices import Devices
from utils.db_utils import db_session
from utils.command_dispatcher import DeviceCommandDispatcher
from utils.ha_manager import ha_manager


def add_health_routes(app: APIRouter, resolver):
    @app.get("/api/myhome/device/{device_id}/health", tags=["health"])
    async def device_health(device_id: int):
        client = resolver(device_id)
        if not client:
            return {"success": False, "error": "Device not found"}
        state = client._sync_state.to_dict()
        state.update({
            "device_id": device_id,
            "ip": client.ip,
            "ws_port": client.ws_port,
            "http": {"available": state["sync_status"] != "error", "latency_ms": state.get("http_latency_ms")},
            "ws": {"connected": state["online"], "connected_at": state.get("ws_connected_at"),
                   "reconnect_count": state.get("reconnect_count", 0)},
            "ha": ha_manager.get_status().get("ha_client_status"),
            "thresholds": {"http_warning_ms": 1000, "stale_after_seconds": 60},
            "checked_at": datetime.now().isoformat(),
        })
        return {"success": True, "health": state}

    @app.get("/api/myhome/commands/history", tags=["health"])
    async def command_history():
        return {"success": True, "commands": DeviceCommandDispatcher.history()}
