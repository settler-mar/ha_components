"""Persistent diagnostics event journal and crash-dump collection."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import aiohttp

from utils.configs import get_data_dir


class DiagnosticsManager:
    """Keep a small, durable timeline of connection and crash-related events."""

    MAX_EVENTS = 10000
    MAX_DUMP_BYTES = 50 * 1024 * 1024
    CONFIG_REQUEST_TIMEOUT = 10
    _LOSS_RATIO = 0.6
    _UPTIME_RE = re.compile(r"(?:^|[._ -])(uptime|up[_ -]?time|millis|runtime|run[_ -]?time)(?:$|[._ -])", re.I)

    def __init__(self) -> None:
        root = Path(get_data_dir()) / "diagnostics"
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self.events_file = root / "events.jsonl"
        self.dumps_root = root / "coredumps"
        self.dumps_root.mkdir(parents=True, exist_ok=True)
        self.policy_file = root / "config_policy.json"
        self._lock = threading.RLock()
        self._recovery_keys = set()

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def record(self, event_type: str, message: str, *, device_id: Optional[int] = None,
               device_name: Optional[str] = None, level: str = "info",
               reason: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        event = {
            "timestamp": self._now(),
            "type": event_type,
            "level": level,
            "message": message,
        }
        if device_id is not None:
            event["device_id"] = device_id
        if device_name:
            event["device_name"] = device_name
        if reason:
            event["reason"] = reason
        if details:
            event["details"] = details
        with self._lock:
            with self.events_file.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def events(self, limit: int = 500, event_type: Optional[str] = None) -> list[Dict[str, Any]]:
        limit = max(1, min(int(limit), self.MAX_EVENTS))
        with self._lock:
            if not self.events_file.exists():
                return []
            rows = []
            with self.events_file.open("r", encoding="utf-8") as stream:
                for line in stream:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not event_type or row.get("type") == event_type:
                        rows.append(row)
            return list(reversed(rows[-limit:]))

    def get_config_policy(self) -> Dict[str, Any]:
        with self._lock:
            if not self.policy_file.is_file():
                return {"version": 1, "devices": {}}
            try:
                value = json.loads(self.policy_file.read_text(encoding="utf-8"))
                return value if isinstance(value, dict) else {"version": 1, "devices": {}}
            except (OSError, ValueError):
                return {"version": 1, "devices": {}}

    def set_config_policy(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        devices = policy.get("devices", policy)
        if not isinstance(devices, dict):
            raise ValueError("devices must be an object")
        normalized = {"version": 1, "devices": {}}
        for device_id, device_policy in devices.items():
            if not isinstance(device_policy, dict):
                raise ValueError(f"device {device_id} policy must be an object")
            files = device_policy.get("files", {})
            if not isinstance(files, dict):
                raise ValueError(f"device {device_id} files must be an object")
            normalized_files = {}
            for file_path, rule in files.items():
                if not isinstance(rule, dict):
                    raise ValueError(f"rule for {file_path} must be an object")
                keys = rule.get("keys", [])
                if not isinstance(keys, list) or not all(isinstance(key, str) and key.strip() for key in keys):
                    raise ValueError(f"keys for {file_path} must be a list of strings")
                normalized_files[self._normalize_config_path(file_path)] = {
                    "protect_all": bool(rule.get("protect_all", False)),
                    "keys": [key.strip() for key in keys],
                }
            normalized["devices"][str(device_id)] = {"files": normalized_files}
        with self._lock:
            self.policy_file.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        self.record("configuration_policy_changed", "Политика защиты конфигурации изменена",
                    details={"policy": normalized})
        return normalized

    def config_rules(self, device_id: int) -> Dict[str, Dict[str, Any]]:
        policy = self.get_config_policy()
        device_policy = (policy.get("devices") or {}).get(str(device_id), {})
        return device_policy.get("files", {}) if isinstance(device_policy, dict) else {}

    def has_config_policy(self, device_id: int) -> bool:
        return bool(self.config_rules(device_id))

    @classmethod
    def uptime_from_ports(cls, ports: Iterable[Dict[str, Any]]) -> Optional[float]:
        candidates = []
        for port in ports:
            code = str(port.get("code") or "")
            title = str(port.get("title") or "")
            if cls._UPTIME_RE.search(code) or cls._UPTIME_RE.search(title):
                value = port.get("value", port.get("val"))
                try:
                    candidates.append(float(value))
                except (TypeError, ValueError):
                    pass
        return min(candidates) if candidates else None

    async def collect_coredump(self, *, device_id: int, device_name: str, ip: str,
                               previous_uptime: float, current_uptime: float,
                               reason: Optional[str]) -> Optional[Dict[str, Any]]:
        url = f"http://{ip}/coredump"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        device_dir = self.dumps_root / str(device_id)
        device_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{timestamp}_{device_id}.bin"
        target = device_dir / filename
        details = {
            "previous_uptime": previous_uptime,
            "current_uptime": current_uptime,
            "url": url,
        }
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise RuntimeError(f"HTTP {response.status}")
                    content = await response.content.read(self.MAX_DUMP_BYTES + 1)
                    if len(content) > self.MAX_DUMP_BYTES:
                        raise RuntimeError("coredump exceeds 50 MiB limit")
                    target.write_bytes(content)
                    details.update({"status": response.status, "size": len(content), "filename": filename})
            return self.record("coredump_collected", f"Coredump скачан: {filename}",
                               device_id=device_id, device_name=device_name, level="error",
                               reason=reason or "uptime_reset", details=details)
        except Exception as error:
            if target.exists():
                target.unlink()
            details["error"] = str(error)
            return self.record("coredump_failed", f"Не удалось скачать coredump: {error}",
                               device_id=device_id, device_name=device_name, level="warning",
                               reason=reason or "uptime_reset", details=details)

    def dump_path(self, device_id: int, filename: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", filename):
            raise ValueError("invalid filename")
        path = (self.dumps_root / str(device_id) / filename).resolve()
        if path.parent != (self.dumps_root / str(device_id)).resolve():
            raise ValueError("invalid dump path")
        if not path.is_file():
            raise FileNotFoundError(filename)
        return path

    def _latest_config_backup(self, device_id: int) -> Optional[tuple[Path, Dict[str, str]]]:
        """Return the newest usable config backup and path -> stored filename map."""
        backup_root = Path(get_data_dir()) / "backup" / str(device_id)
        if not backup_root.is_dir():
            return None
        directories = sorted((item for item in backup_root.iterdir() if item.is_dir()),
                             key=lambda item: item.name, reverse=True)
        for directory in directories:
            manifest_path = directory / "manifest.json"
            mapping: Dict[str, str] = {}
            if manifest_path.is_file():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    mapping = {str(item["path"]): str(item["stored_name"])
                               for item in manifest.get("files", [])
                               if item.get("path") and item.get("stored_name")}
                except (OSError, ValueError, TypeError, KeyError):
                    mapping = {}
            if not mapping:
                mapping = {item.name: item.name for item in directory.iterdir()
                           if item.is_file() and item.name not in {"manifest.json", "backup.log"}}
            if mapping and any((directory / stored).is_file() for stored in mapping.values()):
                return directory, mapping
        return None

    def _named_config_backup(self, device_id: int, backup_name: str) -> Optional[tuple[Path, Dict[str, str]]]:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", str(backup_name or "")):
            return None
        root = Path(get_data_dir()) / "backup" / str(device_id)
        directory = root / backup_name
        if not directory.is_dir():
            return None
        manifest_path = directory / "manifest.json"
        mapping: Dict[str, str] = {}
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                mapping = {str(item["path"]): str(item["stored_name"])
                           for item in manifest.get("files", [])
                           if item.get("path") and item.get("stored_name")}
            except (OSError, ValueError, TypeError, KeyError):
                return None
        if not mapping:
            mapping = {item.name: item.name for item in directory.iterdir()
                       if item.is_file() and item.name not in {"manifest.json", "backup.log"}}
        if not mapping or not all((directory / stored).is_file() for stored in mapping.values()):
            return None
        return directory, mapping

    def config_backup_file(self, device_id: int, backup_name: str, file_path: str) -> Path:
        backup = self._named_config_backup(device_id, backup_name)
        if not backup:
            raise FileNotFoundError(file_path)
        directory, mapping = backup
        stored_name = mapping.get(self._normalize_config_path(file_path))
        if not stored_name:
            raise FileNotFoundError(file_path)
        target = (directory / stored_name).resolve()
        if target.parent != directory.resolve() or not target.is_file():
            raise FileNotFoundError(file_path)
        return target

    async def rollback_to_backup(self, *, device_id: int, device_name: str, ip: str,
                                backup_name: str, reason: str = "manual_rollback") -> Dict[str, Any]:
        backup = self._named_config_backup(device_id, backup_name)
        if not backup:
            raise FileNotFoundError(backup_name)
        backup_dir, mapping = backup
        details = {"backup": backup_name, "manual": True}
        self.record("configuration_rollback_started", "Запущен ручной откат конфигурации",
                    device_id=device_id, device_name=device_name, level="warning",
                    reason=reason, details=details)
        timeout = aiohttp.ClientTimeout(total=self.CONFIG_REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            return await self._restore_configuration(
                session=session, device_id=device_id, device_name=device_name, ip=ip,
                backup_dir=backup_dir, mapping=mapping, details=details,
                rollback_reason=reason,
            )

    @staticmethod
    def _normalize_config_path(value: Any) -> str:
        value = str(value or "").strip()
        if value.startswith("/"):
            value = value[1:]
        return value

    @staticmethod
    def _entry_path(entry: Any) -> Optional[str]:
        if isinstance(entry, str):
            return DiagnosticsManager._normalize_config_path(entry)
        if isinstance(entry, dict) and entry.get("name") and entry.get("type", "file") == "file":
            return DiagnosticsManager._normalize_config_path(entry["name"])
        return None

    @staticmethod
    def _sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _parse_config_document(content: bytes, path: str) -> Any:
        """Parse JSON and JSONL configs into the same value/path model."""
        text = content.decode("utf-8")
        if str(path).lower().endswith(".jsonl"):
            rows = []
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise json.JSONDecodeError(
                        f"invalid JSONL record at line {line_number}: {error.msg}",
                        error.doc, error.pos,
                    ) from error
            return rows
        return json.loads(text)

    def _can_recover(self, device_id: int, recovery_key: str) -> bool:
        key = (device_id, recovery_key)
        with self._lock:
            if key in self._recovery_keys:
                return False
            self._recovery_keys.add(key)
            if len(self._recovery_keys) > 1000:
                self._recovery_keys = set(list(self._recovery_keys)[-500:])
            return True

    async def inspect_configuration_after_crash(self, *, device_id: int, device_name: str,
                                                ip: str, previous_uptime: Optional[float],
                                                current_uptime: Optional[float], reason: Optional[str],
                                                allow_loss_recovery: bool = False) -> Dict[str, Any]:
        """Classify config state and rollback loss or protected changes."""
        backup = self._latest_config_backup(device_id)
        if not backup:
            result = {"classification": "unknown", "reason": "no_config_backup"}
            self.record("configuration_unknown", "Не удалось проверить конфигурацию: нет бэкапа",
                        device_id=device_id, device_name=device_name, level="warning",
                        reason=reason, details=result)
            return result

        backup_dir, mapping = backup
        expected = set(mapping)
        base_url = f"http://{ip}".rstrip("/")
        try:
            timeout = aiohttp.ClientTimeout(total=self.CONFIG_REQUEST_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{base_url}/list", params={"dir": "/config"}) as response:
                    response.raise_for_status()
                    entries = await response.json(content_type=None)
                current = {path for path in (self._entry_path(item) for item in entries) if path}

                missing = expected - current
                changed = []
                current_contents: Dict[str, bytes] = {}
                for path in sorted(expected & current):
                    stored_name = mapping[path]
                    backup_file = backup_dir / stored_name
                    if not backup_file.is_file():
                        continue
                    async with session.get(f"{base_url}/config/{path}") as response:
                        if response.status != 200:
                            missing.add(path)
                            continue
                        content = await response.read()
                    current_contents[path] = content
                    if self._sha256(content) != self._sha256(backup_file.read_bytes()):
                        changed.append(path)

                protected_changes = []
                policy_mismatch = []
                for path, rule in self.config_rules(device_id).items():
                    path = self._normalize_config_path(path)
                    if path not in expected:
                        policy_mismatch.append(path)
                        continue
                    if path in missing:
                        protected_changes.append({"path": path, "keys": ["<file missing>"]})
                        continue
                    if path not in changed:
                        continue
                    if rule.get("protect_all"):
                        protected_changes.append({"path": path, "keys": ["<file>"]})
                        continue
                    keys = rule.get("keys", [])
                    try:
                        before = self._parse_config_document(
                            (backup_dir / mapping[path]).read_bytes(), path
                        )
                        after = self._parse_config_document(current_contents[path], path)
                        changed_keys = [key for key in keys
                                        if self._json_value(before, key) != self._json_value(after, key)]
                    except (UnicodeDecodeError, json.JSONDecodeError, OSError):
                        changed_keys = keys or ["<invalid JSON>"]
                    if changed_keys:
                        protected_changes.append({"path": path, "keys": changed_keys})

                missing_ratio = len(missing) / max(len(expected), 1)
                if not current or missing_ratio >= self._LOSS_RATIO:
                    classification = "configuration_lost"
                elif missing:
                    classification = "configuration_partially_lost"
                elif changed:
                    classification = "configuration_changed"
                else:
                    classification = "configuration_intact"

                details = {
                    "expected_files": len(expected), "current_files": len(current),
                    "missing_files": sorted(missing), "changed_files": changed,
                    "protected_changes": protected_changes,
                    "policy_mismatch": policy_mismatch,
                    "backup": backup_dir.name, "missing_ratio": round(missing_ratio, 3),
                }
                if policy_mismatch:
                    self.record("configuration_policy_mismatch",
                                "Защищённые файлы отсутствуют в последнем бэкапе",
                                device_id=device_id, device_name=device_name, level="warning",
                                reason="protected_file_not_in_backup",
                                details={"files": policy_mismatch, "backup": backup_dir.name})
                self.record(classification, f"Состояние конфигурации: {classification}",
                            device_id=device_id, device_name=device_name,
                            level="error" if classification == "configuration_lost" else "warning"
                            if classification in {"configuration_partially_lost", "configuration_changed"}
                            else "info", reason=reason, details=details)

                if protected_changes:
                    rollback_reason = "protected_configuration_changed"
                    recovery_scope = "protected:" + self._sha256(json.dumps(protected_changes, sort_keys=True).encode())
                else:
                    rollback_reason = reason or "configuration_lost"
                    recovery_scope = f"loss:{previous_uptime}:{current_uptime}"
                if ((classification == "configuration_lost" and allow_loss_recovery) or protected_changes) and self._can_recover(
                    device_id, recovery_scope
                ):
                    self.record("configuration_rollback_started", "Запущен откат конфигурации",
                                device_id=device_id, device_name=device_name, level="warning",
                                reason=rollback_reason, details=details)
                    return await self._restore_configuration(
                        session=session, device_id=device_id, device_name=device_name,
                        ip=ip, backup_dir=backup_dir, mapping=mapping, details=details,
                        rollback_reason=rollback_reason,
                    )
                return {"classification": classification, **details}
        except Exception as error:
            details = {"error": str(error), "backup": backup_dir.name}
            self.record("configuration_unknown", "Не удалось проверить конфигурацию после падения",
                        device_id=device_id, device_name=device_name, level="warning",
                        reason=reason, details=details)
            return {"classification": "unknown", **details}

    async def _restore_configuration(self, *, session: aiohttp.ClientSession, device_id: int,
                                     device_name: str, ip: str, backup_dir: Path,
                                     mapping: Dict[str, str], details: Dict[str, Any],
                                     rollback_reason: str) -> Dict[str, Any]:
        base_url = f"http://{ip}".rstrip("/")
        uploaded = []
        try:
            for path, stored_name in mapping.items():
                content = (backup_dir / stored_name).read_bytes()
                filename = "/" + path.lstrip("/")
                form = aiohttp.FormData()
                form.add_field("data", content, filename=filename,
                               content_type="application/octet-stream")
                async with session.post(f"{base_url}/edit", data=form) as response:
                    if response.status not in {200, 201, 204}:
                        raise RuntimeError(f"POST /edit {response.status} for {filename}")
                uploaded.append(path)

            # Verify every restored file before allowing a reboot.
            for path, stored_name in mapping.items():
                async with session.get(f"{base_url}/config/{path}") as response:
                    if response.status != 200:
                        raise RuntimeError(f"verification failed for {path}: HTTP {response.status}")
                    if self._sha256(await response.read()) != self._sha256((backup_dir / stored_name).read_bytes()):
                        raise RuntimeError(f"verification hash mismatch for {path}")

            self.record("configuration_restored", f"Конфигурация восстановлена: {len(uploaded)} файлов",
                        device_id=device_id, device_name=device_name, level="error",
                        reason=rollback_reason, details={**details, "uploaded_files": uploaded})
            async with session.get(f"{base_url}/restart") as response:
                if response.status in {200, 202, 204}:
                    restart = "requested"
                else:
                    restart = f"unsupported_http_{response.status}"
            self.record("configuration_recovery_restart", f"Перезагрузка после восстановления: {restart}",
                        device_id=device_id, device_name=device_name,
                        level="info" if restart == "requested" else "warning",
                        reason=rollback_reason, details={"restart": restart})
            return {"classification": "configuration_restored", "uploaded_files": uploaded,
                    "restart": restart}
        except Exception as error:
            self.record("configuration_restore_failed", f"Восстановление конфигурации не удалось: {error}",
                        device_id=device_id, device_name=device_name, level="critical",
                        reason=rollback_reason, details={**details, "uploaded_files": uploaded})
            return {"classification": "configuration_restore_failed", "error": str(error),
                    "uploaded_files": uploaded}

    @staticmethod
    def _json_value(value: Any, path: str) -> Any:
        """Read dotted JSON keys, including array indexes, without exceptions."""
        current = value
        for part in path.split("."):
            if isinstance(current, list) and part.isdigit():
                index = int(part)
                if index >= len(current):
                    return None
                current = current[index]
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current


diagnostics = DiagnosticsManager()
