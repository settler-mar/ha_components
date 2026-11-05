"""Adapter for the current MY_HOME board HTTP and WebSocket protocol.

The firmware protocol is intentionally kept unchanged here.  This module
normalizes its limitations at the integration boundary and exposes one model
to the rest of the application.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import aiohttp


_SERVICE_CODES = {"console"}


def _slug(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text.startswith("/#"):
        text = text[2:]
    elif text.startswith("#"):
        text = text[1:]
    text = re.sub(r"[^a-z0-9а-яё]+", "_", text, flags=re.IGNORECASE).strip("_")
    return text or None


def _split_type(type_str: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not type_str or "." not in str(type_str):
        return None, None
    direction, kind = str(type_str).split(".", 1)
    return direction or None, kind or None


def _coerce_value(value: Any, kind: Optional[str]) -> Any:
    """Convert the firmware value to a useful Python value without losing raw data."""
    if kind == "digital":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        text = str(value).strip().lower()
        if text in {"0", "false", "off", "no", "disabled", "down", "offline"}:
            return False
        if text in {"1", "255", "true", "on", "yes", "enabled", "up", "online"}:
            return True
        return value

    if kind == "analog":
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip()
        try:
            number = float(text)
            return int(number) if number.is_integer() else number
        except (TypeError, ValueError):
            return value

    if kind in {"integer", "int"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    if kind in {"float", "number"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value

    return value


def _value_type(kind: Optional[str], value: Any) -> str:
    if kind == "digital":
        return "boolean"
    if kind == "analog":
        return "number"
    if kind in {"integer", "int"}:
        return "integer"
    if kind in {"float", "number"}:
        return "number"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "text"


def _iter_items(value: Any, meta: Optional[Dict[str, Any]] = None) -> Iterable[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Recursively walk current /values variants, including nested arrays."""
    meta = dict(meta or {})
    if isinstance(value, list):
        for item in value:
            yield from _iter_items(item, meta)
        return

    if not isinstance(value, dict):
        return

    if value.get("type") == "file_list":
        return

    current_meta = dict(meta)
    if value.get("title") is not None:
        current_meta["group_title"] = value.get("title")
    if value.get("href") is not None:
        current_meta["group_href"] = value.get("href")

    if "code" in value and "val" in value:
        yield value, current_meta
        return

    if isinstance(value.get("data"), list):
        for item in value["data"]:
            yield from _iter_items(item, current_meta)
        return

    # Some legacy modules return a one-item object/list wrapper.
    for child in value.values():
        if isinstance(child, (dict, list)):
            yield from _iter_items(child, current_meta)


def _get_block_id(item: Dict[str, Any], meta: Dict[str, Any]) -> Optional[str]:
    return (
        _slug(item.get("block_id"))
        or _slug(meta.get("group_href"))
        or _slug(meta.get("group_title"))
        or _slug(str(item.get("code", "")).split(".", 1)[0])
    )


def normalize_values(payload: Any) -> List[Dict[str, Any]]:
    """Normalize the board's current /values response into physical parameters."""
    normalized: List[Dict[str, Any]] = []
    seen: set[Tuple[str, Optional[str], Optional[str]]] = set()

    for item, meta in _iter_items(payload):
        type_raw = item.get("type")
        direction, kind = _split_type(type_raw)
        code = item.get("code")
        if not code or not direction:
            continue

        raw_value = item.get("val")
        value = _coerce_value(raw_value, kind)
        key = (str(code), direction, kind)
        if key in seen:
            continue
        seen.add(key)

        unit = item.get("unit") or item.get("units")
        block_id = _get_block_id(item, meta)
        record: Dict[str, Any] = {
            # Compatibility fields used by the existing frontend/database.
            "code": str(code),
            "title": item.get("title"),
            "direction": direction,
            "kind": kind,
            "type_raw": type_raw,
            "val": raw_value,
            "unit": unit,
            "mqtt": item.get("mqtt"),
            "href": item.get("href") or meta.get("group_href"),
            "group_title": meta.get("group_title"),
            "group_href": meta.get("group_href"),
            "raw": item,
            # Normalized integration fields.
            "value": value,
            "value_type": _value_type(kind, value),
            "block_id": block_id,
            "available": True,
            "ha_eligible": True,
        }

        extra_keys = set(item) - {
            "code", "title", "type", "val", "unit", "units", "mqtt", "href", "data"
        }
        if extra_keys:
            record["extra"] = {key: item[key] for key in extra_keys}

        normalized.append(record)

    return normalized


def values_statistics(ports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a compact statistics report for the observed physical contract."""
    by_block: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    by_value_type: Dict[str, int] = {}
    missing_titles = 0
    missing_units = 0
    extra_keys: Dict[str, int] = {}

    for port in ports:
        block = port.get("block_id") or "unknown"
        raw_type = port.get("type_raw") or "unknown"
        value_type = port.get("value_type") or "unknown"
        by_block[block] = by_block.get(block, 0) + 1
        by_type[raw_type] = by_type.get(raw_type, 0) + 1
        by_value_type[value_type] = by_value_type.get(value_type, 0) + 1
        if not port.get("title"):
            missing_titles += 1
        if not port.get("unit"):
            missing_units += 1
        for key in (port.get("extra") or {}):
            extra_keys[key] = extra_keys.get(key, 0) + 1

    return {
        "total": len(ports),
        "blocks": dict(sorted(by_block.items())),
        "types": dict(sorted(by_type.items())),
        "value_types": dict(sorted(by_value_type.items())),
        "missing_titles": missing_titles,
        "missing_units": missing_units,
        "extra_keys": dict(sorted(extra_keys.items())),
    }


def parse_ws_message(message: Any, known_ports: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """Parse legacy ``code#value`` WS messages and filter board console output."""
    if not isinstance(message, str) or "#" not in message:
        return None
    code, raw_value = message.split("#", 1)
    code = code.strip()
    raw_value = raw_value.strip()
    if not code or code in _SERVICE_CODES or code.startswith("console."):
        return None

    matches = known_ports.get(code, [])
    if not matches:
        return None

    port = matches[0]
    value = _coerce_value(raw_value, port.get("kind"))
    return {
        "code": code,
        "val": raw_value,
        "value": value,
        "value_type": port.get("value_type") or _value_type(port.get("kind"), value),
        "direction": port.get("direction"),
        "kind": port.get("kind"),
        "raw": message,
        "ambiguous": len(matches) > 1,
    }


def normalize_device_info(info: Any) -> Dict[str, Any]:
    info = info if isinstance(info, dict) else {}
    name = str(info.get("name") or "")
    role = None
    name_upper = name.upper()
    if "MASTER" in name_upper:
        role = "master"
    elif "SLAVE" in name_upper:
        role = "slave"
    uid = info.get("mac") or info.get("chip_id")
    return {
        "device_uid": str(uid) if uid is not None else None,
        "name": name,
        "role": role,
        "firmware_version": info.get("version"),
        "hardware_model": info.get("fr_name") or info.get("config_name"),
        "chip_id": info.get("chip_id"),
        "mac": info.get("mac"),
        "config_name": info.get("config_name"),
        "raw": info,
    }


@dataclass
class DeviceSnapshot:
    info: Dict[str, Any]
    ports: List[Dict[str, Any]]


class DeviceProtocolAdapter:
    """Single HTTP/WS boundary used by ``MyHomeDeviceClient``."""

    def __init__(self, ip: str, http_timeout: float = 5.0):
        self.ip = ip
        self.http_timeout = http_timeout

    async def fetch_info(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        async with session.get(f"http://{self.ip}/info", timeout=self.http_timeout) as response:
            response.raise_for_status()
            return normalize_device_info(json.loads(await response.text()))

    async def fetch_snapshot(self, session: aiohttp.ClientSession) -> DeviceSnapshot:
        async with session.get(f"http://{self.ip}/values", timeout=self.http_timeout) as response:
            response.raise_for_status()
            payload = json.loads(await response.text())

        try:
            info = await self.fetch_info(session)
        except Exception:
            # /values remains authoritative for runtime data if /info is unavailable.
            info = normalize_device_info({})
        return DeviceSnapshot(info=info, ports=normalize_values(payload))
