"""Universal, fail-closed module link contracts.

The link layer is deliberately independent from boards, MQTT and Home Assistant.
Heating is only the first profile using it.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from utils.configs import get_data_dir


MODES = {"disabled", "physical", "virtual"}
QUALITIES = {"unknown", "good", "degraded", "stale", "timeout", "invalid", "offline"}
HA_BINDING_MODES = {"none", "virtual_port", "ha_entity"}
ENDPOINT_SYSTEMS = {"home_assistant", "esp", "my_home", "other"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


@dataclass
class LinkValueSpec:
    name: str
    direction: str
    value_type: str
    unit: Optional[str] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    initial: Any = None
    on_stale: Any = None
    timeout_s: int = 120
    error_behavior: str = "reject"
    source: Dict[str, Any] = field(default_factory=dict)
    target: Dict[str, Any] = field(default_factory=dict)
    ha_binding: Dict[str, Any] = field(default_factory=lambda: {"mode": "none"})
    physical_binding: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LinkValueState:
    value: Any = None
    quality: str = "unknown"
    updated_at: Optional[str] = None
    age_s: Optional[float] = None
    error: Optional[str] = None


@dataclass
class ModuleLink:
    link_id: str
    producer: str
    consumer: str
    contract_version: int = 1
    mode: str = "disabled"
    enabled: bool = True
    values: Dict[str, LinkValueSpec] = field(default_factory=dict)
    states: Dict[str, LinkValueState] = field(default_factory=dict)
    virtual: Dict[str, Any] = field(default_factory=lambda: {
        "active": False,
        "ready": False,
        "supply": None,
        "last_update": None,
        "timeout_s": 120,
    })
    last_error: Optional[str] = None

    def __post_init__(self) -> None:
        for name, spec in self.values.items():
            if isinstance(spec, dict):
                self.values[name] = LinkValueSpec(**spec)
            if not self.values[name].source:
                self.values[name].source = {"system": "", "module": self.producer}
            if not self.values[name].target:
                self.values[name].target = {"system": "", "module": self.consumer}
            if not self.values[name].ha_binding:
                self.values[name].ha_binding = {"mode": "none"}
        for name, state in list(self.states.items()):
            if isinstance(state, dict):
                self.states[name] = LinkValueState(**state)
        for name, spec in self.values.items():
            self.states.setdefault(name, LinkValueState(value=spec.initial))

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError("invalid_mode")
        self.mode = mode
        self.virtual["active"] = mode == "virtual"
        if mode != "virtual":
            self.virtual["ready"] = False
            self.virtual["supply"] = None
            self.virtual["last_update"] = None

    def update(self, name: str, value: Any, *, quality: str = "good", error: Optional[str] = None) -> None:
        if name not in self.values:
            raise KeyError("unknown_value")
        if quality not in QUALITIES:
            raise ValueError("invalid_quality")
        spec = self.values[name]
        if not self._valid_type(spec.value_type, value):
            self.states[name] = LinkValueState(value=spec.on_stale, quality="invalid", error="invalid_type")
            return
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if spec.minimum is not None and value < spec.minimum or spec.maximum is not None and value > spec.maximum:
                self.states[name] = LinkValueState(value=spec.on_stale, quality="invalid", error="out_of_range")
                return
        now = _now()
        self.states[name] = LinkValueState(value=value, quality=quality, updated_at=_iso(now), age_s=0, error=error)
        if self.mode == "virtual":
            self._update_virtual(name, value, now)

    def tick(self) -> None:
        now = _now()
        for name, spec in self.values.items():
            state = self.states.setdefault(name, LinkValueState(value=spec.initial))
            if not state.updated_at:
                continue
            try:
                updated = datetime.fromisoformat(state.updated_at)
                state.age_s = max(0, (now - updated).total_seconds())
            except ValueError:
                state.quality = "invalid"
                state.error = "invalid_timestamp"
                continue
            if state.age_s > spec.timeout_s:
                state.quality = "timeout"
                state.value = spec.on_stale
                state.error = "value_timeout"
            elif state.age_s > spec.timeout_s / 2 and state.quality == "good":
                state.quality = "stale"

        if self.mode == "virtual" and self.virtual.get("last_update"):
            try:
                virtual_updated = datetime.fromisoformat(self.virtual["last_update"])
                virtual_age = max(0, (now - virtual_updated).total_seconds())
                self.virtual["age_s"] = virtual_age
                if virtual_age > self.virtual.get("timeout_s", 120):
                    self.virtual["ready"] = False
                    self.virtual["supply"] = None
                    for feedback_name in ("ready", "supply"):
                        if feedback_name in self.states:
                            feedback = self.states[feedback_name]
                            feedback.value = self.values[feedback_name].on_stale
                            feedback.quality = "timeout"
                            feedback.error = "virtual_timeout"
            except (TypeError, ValueError):
                self.virtual["age_s"] = None
                self.virtual["ready"] = False
                self.virtual["supply"] = None

    def to_dict(self) -> Dict[str, Any]:
        self.tick()
        return {
            "link_id": self.link_id,
            "producer": self.producer,
            "consumer": self.consumer,
            "contract_version": self.contract_version,
            "mode": self.mode,
            "enabled": self.enabled,
            "values": {key: asdict(value) for key, value in self.values.items()},
            "states": {key: asdict(value) for key, value in self.states.items()},
            "virtual": self.virtual,
            "last_error": self.last_error,
            "physical_outputs_protected": True,
        }

    @staticmethod
    def _valid_type(value_type: str, value: Any) -> bool:
        return {
            "boolean": isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "string": isinstance(value, str),
            "json": isinstance(value, (dict, list)),
        }.get(value_type, False)

    def _update_virtual(self, name: str, value: Any, now: datetime) -> None:
        # This state machine has no board/device resolver by design.
        if name in {"boiler_enable", "enable", "request_enable"}:
            self.virtual["ready"] = bool(value)
            self._update_virtual_feedback("ready", bool(value), now)
        if name in {"boiler_temperature", "requested_supply", "supply_request", "supply"}:
            self.virtual["supply"] = value
            self._update_virtual_feedback("supply", value, now)
        if name in {"boiler_enable", "enable", "request_enable", "boiler_temperature", "requested_supply", "supply_request", "supply"}:
            self.virtual["last_update"] = _iso(now)

    def _update_virtual_feedback(self, name: str, value: Any, now: datetime) -> None:
        """Expose the virtual boiler response through the normal link states."""
        if name not in self.values:
            return
        self.states[name] = LinkValueState(
            value=value,
            quality="good",
            updated_at=_iso(now),
            age_s=0,
            error=None,
        )


class ModuleLinkManager:
    def __init__(self) -> None:
        self.path = os.path.join(get_data_dir(), "module_links.json")
        self.links: Dict[str, ModuleLink] = {}
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            raw = {"version": 1, "links": []}
        for item in raw.get("links", []):
            # Runtime-only safety flags are exposed by to_dict() but are not
            # constructor fields and must not be persisted as input state.
            item = {key: value for key, value in item.items() if key != "physical_outputs_protected"}
            link = ModuleLink(**item)
            # Runtime safety: every restart starts disconnected.
            link.set_mode("disabled")
            self.links[link.link_id] = link

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"version": 1, "links": [link.to_dict() for link in self.links.values()]}, handle, ensure_ascii=False, indent=2)

    def get(self, link_id: str) -> Optional[ModuleLink]:
        return self.links.get(link_id)

    def upsert(self, payload: Dict[str, Any]) -> ModuleLink:
        link_id = str(payload.get("link_id") or "").strip()
        if not link_id:
            raise ValueError("link_id_required")
        old = self.links.get(link_id)
        link = ModuleLink(**payload) if old is None else old
        if old is not None:
            for field_name in ("producer", "consumer", "contract_version", "enabled", "values", "virtual"):
                if field_name in payload:
                    setattr(link, field_name, payload[field_name])
            link.__post_init__()
        link.set_mode("disabled")
        self.links[link_id] = link
        self.save()
        return link

    def set_mode(self, link_id: str, mode: str) -> ModuleLink:
        link = self.links[link_id]
        link.set_mode(mode)
        self.save()
        return link


module_link_manager = ModuleLinkManager()
