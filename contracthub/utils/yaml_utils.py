from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load YAML document as a mapping."""
    resolved = Path(path).expanduser().resolve()
    payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML content must be a mapping object: {resolved}")
    return payload


def dump_yaml(payload: dict[str, Any], path: str | Path) -> Path:
    """Write mapping payload to YAML."""
    resolved = Path(path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return resolved


# Example usage:
# contract = load_yaml("contracts/orders.yaml")
# dump_yaml(contract, "artifacts/orders.yaml")
