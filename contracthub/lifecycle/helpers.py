from __future__ import annotations

from typing import Any

from open_data_contract_standard.model import CustomProperty, OpenDataContractStandard

ACTIVE_STATUSES = {"active"}
NON_BREAKING_LIFECYCLE_STATUSES = {"draft", "deprecated"}


def normalize_status(value: Any, default: str = "draft") -> str:
    """Normalize status-like values to lowercase strings."""
    if value is None:
        return default
    text = str(value).strip().lower()
    return text or default


def is_active_contract(contract: OpenDataContractStandard) -> bool:
    """Return True when contract-level status is active."""
    value = contract.status
    if not value:
        value = _lifecycle_from_custom_properties(contract.customProperties)
    return normalize_status(value, default="draft") in ACTIVE_STATUSES


def allows_breaking_changes(entity: Any) -> bool:
    """Return True when entity lifecycle status permits non-breaking updates only."""
    value = getattr(entity, "lifecycleStatus", None)
    if value is None:
        value = _lifecycle_from_custom_properties(getattr(entity, "customProperties", None))
    lifecycle_status = normalize_status(value, default="active")
    return lifecycle_status not in NON_BREAKING_LIFECYCLE_STATUSES


def schema_items(contract: OpenDataContractStandard) -> list[Any]:
    """Return schema entries for the ODCS contract."""
    return list(contract.schema_ or [])


def _lifecycle_from_custom_properties(custom_properties: Any) -> Any:
    if not isinstance(custom_properties, list):
        return None
    for item in custom_properties:
        if isinstance(item, CustomProperty):
            key = (item.property or "").strip().lower()
            if key == "lifecyclestatus":
                return item.value
        elif isinstance(item, dict):
            key = str(item.get("property") or "").strip().lower()
            if key == "lifecyclestatus":
                return item.get("value")
    return None
