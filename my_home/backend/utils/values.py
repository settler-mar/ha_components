"""Compatibility entry point for normalizing a board /values response."""

from typing import Any, Dict, List

from utils.device_protocol import normalize_values


def flatten_ports(values: Any) -> List[Dict[str, Any]]:
    """Keep the historical function name used by the device client."""
    return normalize_values(values)
