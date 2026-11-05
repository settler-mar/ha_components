"""Single command path from UI/HA to a physical board parameter."""

from __future__ import annotations

from typing import Any, Callable, Optional
from datetime import datetime, timedelta
import asyncio

from utils.state_model import CommandResult, DeviceCommand


class DeviceCommandDispatcher:
    _recent = {}
    _history = []
    _lock = asyncio.Lock()
    def __init__(self, resolver: Callable[[int], Any]):
        self._resolver = resolver

    async def dispatch(self, command: DeviceCommand) -> dict:
        key = (command.device_id, command.code, repr(command.value), command.source)
        async with self._lock:
            previous = self._recent.get(key)
            if previous and datetime.now() - previous[0] < timedelta(seconds=1):
                return {**previous[1], "status": "duplicate", "success": True,
                        "duplicate_of": previous[1].get("command_id")}
        client = self._resolver(command.device_id)
        if not client:
            result = CommandResult(
                command_id=command.command_id,
                status="failed",
                device_id=command.device_id,
                code=command.code,
                error="device_not_found",
            ).to_dict()
            return result

        if not client.has_known_port(command.code):
            return CommandResult(
                command_id=command.command_id,
                status="failed",
                device_id=command.device_id,
                code=command.code,
                error="unknown_parameter",
            ).to_dict()

        port = (client._ports_index.get(command.code) or [None])[0]
        if port and port.get("direction") == "in":
            return CommandResult(
                command_id=command.command_id,
                status="failed",
                device_id=command.device_id,
                code=command.code,
                error="parameter_is_read_only",
            ).to_dict()

        try:
            port_value = (port or {}).get("value_type") or (port or {}).get("type_raw")
            if port_value in {"int", "integer", "float", "number"} and not isinstance(command.value, (int, float)):
                command.value = float(command.value) if "." in str(command.value) else int(command.value)
            params = (port or {}).get("params") or {}
            if isinstance(command.value, (int, float)):
                if params.get("min") is not None and command.value < params["min"]:
                    raise ValueError("value_below_minimum")
                if params.get("max") is not None and command.value > params["max"]:
                    raise ValueError("value_above_maximum")
        except (TypeError, ValueError) as error:
            return CommandResult(command_id=command.command_id, status="failed", device_id=command.device_id,
                                 code=command.code, error=str(error)).to_dict()

        client._sync_state.command_count += 1
        client._sync_state.last_command_at = datetime.now().isoformat()
        try:
            sent = await asyncio.wait_for(client.send_command(command.code, command.value), timeout=3.0)
        except asyncio.TimeoutError:
            client._sync_state.command_failures += 1
            return CommandResult(command_id=command.command_id, status="timeout", device_id=command.device_id,
                                 code=command.code, error="command_timeout", source=command.source).to_dict()
        if not sent:
            client._sync_state.command_failures += 1
            return CommandResult(
                command_id=command.command_id,
                status="failed",
                device_id=command.device_id,
                code=command.code,
                error="transport_unavailable",
            ).to_dict()

        result = CommandResult(
            command_id=command.command_id,
            status="confirmed" if self._value_matches(client, command.code, command.value) else "accepted",
            device_id=command.device_id,
            code=command.code,
            value=command.value,
            source=command.source,
            confirmed_at=datetime.now().isoformat() if self._value_matches(client, command.code, command.value) else None,
        ).to_dict()
        async with self._lock:
            self._recent[key] = (datetime.now(), result)
            self._history.append(result)
            del self._history[:-100]
        return result

    @staticmethod
    def _value_matches(client, code, value):
        port = (client._ports_index.get(code) or [None])[0]
        current = None if not port else port.get("value", port.get("val"))
        if isinstance(value, bool):
            return current in (value, 255 if value else 0, 1 if value else 0)
        return str(current) == str(value)

    @classmethod
    def history(cls):
        return list(reversed(cls._history))
