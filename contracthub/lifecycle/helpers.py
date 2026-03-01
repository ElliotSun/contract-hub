from __future__ import annotations

from typing import Any

ACTIVE_STATUSES = {"active"}
NON_BREAKING_LIFECYCLE_STATUSES = {"draft", "deprecated"}


def normalize_status(value: Any, default: str = "draft") -> str:
    """Normalize status-like values to lowercase strings."""
    if value is None:
        return default
    text = str(value).strip().lower()
    return text or default


def is_active_contract(contract: dict[str, Any]) -> bool:
    """Return True when contract-level status is active."""
    return normalize_status(contract.get("status"), default="draft") in ACTIVE_STATUSES


def allows_breaking_changes(entity: dict[str, Any]) -> bool:
    """Return True when entity lifecycle status permits non-breaking updates only."""
    lifecycle_status = normalize_status(entity.get("lifecycleStatus"), default="active")
    return lifecycle_status not in NON_BREAKING_LIFECYCLE_STATUSES


def schema_items(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Return schema entries from either schema or schema_ keys."""
    schema = contract.get("schema")
    if isinstance(schema, list):
        return [item for item in schema if isinstance(item, dict)]
    schema_alias = contract.get("schema_")
    if isinstance(schema_alias, list):
        return [item for item in schema_alias if isinstance(item, dict)]
    return []
