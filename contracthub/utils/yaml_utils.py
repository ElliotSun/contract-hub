from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from contracthub.core import loader as contract_loader


def read_yaml_text(path: str | Path) -> str:
    """Read raw YAML text from supported storage backends."""
    path_str = str(path)
    if _is_local_path(path_str):
        resolved = _resolve_local_path(path)
        return resolved.read_text(encoding="utf-8")
    return contract_loader._read_contract_text(path_str, contract_loader._resolve_runtime_context(None))  # noqa: SLF001


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load YAML document as a mapping."""
    payload = yaml.safe_load(read_yaml_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML content must be a mapping object: {path}")
    return payload


def dump_yaml(payload: dict[str, Any], path: str | Path) -> Path:
    """Write mapping payload to YAML."""
    resolved = Path(path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return resolved


def load_yaml_metadata(path: str | Path, keys: list[str] | tuple[str, ...]) -> dict[str, str]:
    """Read only top-level scalar metadata keys from a YAML file.

    This avoids deserializing the full contract when the UI only needs catalog
    metadata such as id, name, version, status, or tenant.
    """
    wanted = {str(key) for key in keys}
    metadata: dict[str, str] = {}

    for raw_line in read_yaml_text(path).splitlines():
        if not raw_line or raw_line.startswith((" ", "\t", "#")):
            continue
        if ":" not in raw_line:
            continue

        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        if key not in wanted or key in metadata:
            continue

        value = raw_value.strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        metadata[key] = value

        if len(metadata) == len(wanted):
            break

    return metadata


def list_yaml_documents(root: str | Path) -> list[str]:
    """List YAML contract documents under a local or ADLS2 root path."""
    root_str = str(root)
    if contract_loader._is_uc_volume_path(root_str):  # noqa: SLF001
        return _list_local_yaml_documents(contract_loader._normalize_uc_volume_local_path(root_str))  # noqa: SLF001
    if _is_local_path(root_str):
        return _list_local_yaml_documents(root)
    if contract_loader._is_adls2_path(root_str):  # noqa: SLF001
        return contract_loader._list_adls2_paths(root_str)  # noqa: SLF001
    raise ValueError(f"Unsupported contract storage root: {root}")


def _list_local_yaml_documents(root: str | Path) -> list[str]:
    resolved = _resolve_local_path(root)
    if resolved.is_file():
        return [str(resolved)] if _is_yaml_name(resolved.name) else []
    if not resolved.exists():
        return []

    paths = [*resolved.rglob("*.yaml"), *resolved.rglob("*.yml")]
    return [str(path.resolve()) for path in sorted(paths, key=lambda item: str(item).lower())]
def _resolve_local_path(path: str | Path) -> Path:
    parsed = urlparse(str(path))
    if parsed.scheme == "file":
        return Path(parsed.path).expanduser().resolve()
    return Path(path).expanduser().resolve()


def _is_local_path(path: str) -> bool:
    return contract_loader._is_local_path(path)  # noqa: SLF001


def _is_yaml_name(name: str) -> bool:
    lowered = str(name).lower()
    return lowered.endswith(".yaml") or lowered.endswith(".yml")


# Example usage:
# contract = load_yaml("contracts/orders.yaml")
# dump_yaml(contract, "artifacts/orders.yaml")
