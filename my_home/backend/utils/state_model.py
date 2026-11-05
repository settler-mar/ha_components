"""Shared state and command models used at the integration boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4


def _now() -> str:
    return datetime.now().isoformat()


@dataclass
class ParameterState:
    code: str
    value: Any = None
    raw_value: Any = None
    value_type: Optional[str] = None
    direction: Optional[str] = None
    kind: Optional[str] = None
    available: bool = True
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeviceState:
    device_id: int
    online: bool
    sync_status: str = "not_started"
    snapshot_at: Optional[str] = None
    last_event_at: Optional[str] = None
    last_error: Optional[str] = None
    offline_reason: Optional[str] = None
    reconnect_count: int = 0
    last_diff: Optional[Dict[str, Any]] = None
    http_latency_ms: Optional[float] = None
    ws_connected_at: Optional[str] = None
    last_command_at: Optional[str] = None
    command_count: int = 0
    command_failures: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeviceEvent:
    device_id: int
    code: str
    value: Any
    raw_value: Any = None
    value_type: Optional[str] = None
    source: str = "ws"
    occurred_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["val"] = result.pop("raw_value")
        return result


@dataclass
class DeviceCommand:
    device_id: int
    code: str
    value: Any
    source: str = "ui"
    command_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CommandResult:
    command_id: str
    status: str
    device_id: int
    code: str
    error: Optional[str] = None
    value: Any = None
    source: Optional[str] = None
    retry_count: int = 0
    confirmed_at: Optional[str] = None
    completed_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["success"] = self.status in {"accepted", "confirmed"}
        return result
