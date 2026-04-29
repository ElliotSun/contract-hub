"""ODCS-centric helpers for editor state and presentation."""

from __future__ import annotations

from typing import Any

from contracthub.constants import BUSINESS_PROPERTY_KEYS, TECHNICAL_PROPERTY_KEYS
from contracthub.core.editor_semantics import (
    field_lifecycle_status,
    field_type,
    schema_items,
)
from contracthub.interfaces.streamlit.services.contract_service import (
    parse_contract_yaml,
    serialize_contract_yaml,
)


def parse_yaml_payload(source_yaml: str) -> dict[str, Any]:
    """Parse YAML into the working contract mapping."""
    payload = parse_contract_yaml(source_yaml)
    if not schema_items(payload):
        payload["schema"] = [{"name": "default_schema", "properties": []}]
    return payload


def contract_to_yaml(contract: dict[str, Any]) -> str:
    """Serialize the working contract back to YAML."""
    return serialize_contract_yaml(contract)


def is_technical_property_key(key: str) -> bool:
    """Return True when an ODCS property attribute is technical metadata."""
    return key in TECHNICAL_PROPERTY_KEYS


def is_business_property_key(key: str) -> bool:
    """Return True when a property attribute is editable business metadata."""
    return key in BUSINESS_PROPERTY_KEYS


def is_technical_editor_column(column: str) -> bool:
    """Map editor column names to ODCS technical attributes."""
    if column == "type":
        return is_technical_property_key("logicalType") or is_technical_property_key(
            "physicalType"
        )
    return is_technical_property_key(column)


def quick_field_rows(schema_obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten fields into quick-edit rows."""
    rows: list[dict[str, Any]] = []
    for index, field_obj in enumerate(schema_obj.get("properties", []) or []):
        if not isinstance(field_obj, dict):
            continue
        rows.append(
            {
                "name": str(field_obj.get("name", "") or ""),
                "businessName": str(field_obj.get("businessName", "") or ""),
                "type": field_type(field_obj),
                "required": bool(field_obj.get("required", False)),
                "lifecycleStatus": field_lifecycle_status(field_obj) or "draft",
                "description": str(field_obj.get("description", "") or ""),
                "__original_index": index,
            }
        )
    return rows
