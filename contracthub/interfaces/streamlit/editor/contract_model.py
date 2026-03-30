"""ODCS-centric helpers for editor state and presentation."""

from __future__ import annotations

from typing import Any

from contracthub.core.editor_contract import (
    add_field,
    add_quality_rule,
    apply_field_detail,
    apply_quality_rows,
    apply_quick_field_rows,
    contract_description_part,
    contract_tags,
    field_by_name,
    field_examples_text,
    field_lifecycle_status,
    normalize_tags,
    quality_rows,
    schema_items,
    selected_schema_field_names,
    set_contract_description_part,
    set_contract_tags_list,
)
from contracthub.interfaces.streamlit.services.contract_service import parse_contract_yaml, serialize_contract_yaml

from .constants import BUSINESS_PROPERTY_KEYS, TECHNICAL_PROPERTY_KEYS, TYPE_OPTIONS


def parse_yaml_payload(source_yaml: str) -> dict[str, Any]:
    """Parse YAML into the working contract mapping."""
    payload = parse_contract_yaml(source_yaml)
    if not schema_items(payload):
        payload["schema"] = [{"name": "default_schema", "properties": []}]
    return payload


def contract_to_yaml(contract: dict[str, Any]) -> str:
    """Serialize the working contract back to YAML."""
    return serialize_contract_yaml(contract)


def contract_name(contract: dict[str, Any]) -> str:
    """Resolve contract name."""
    if contract.get("name") is not None:
        return str(contract.get("name", ""))
    nested_contract = contract.get("contract")
    if isinstance(nested_contract, dict) and nested_contract.get("name") is not None:
        return str(nested_contract.get("name", ""))
    return str(contract.get("name", ""))


def contract_version(contract: dict[str, Any]) -> str:
    """Resolve contract version."""
    if contract.get("version") is not None:
        return str(contract.get("version", ""))
    nested_contract = contract.get("contract")
    if isinstance(nested_contract, dict) and nested_contract.get("version") is not None:
        return str(nested_contract.get("version", ""))
    return str(contract.get("version", ""))


def contract_status(contract: dict[str, Any]) -> str:
    """Resolve contract status."""
    if contract.get("status") is not None:
        return str(contract.get("status", ""))
    nested_contract = contract.get("contract")
    if isinstance(nested_contract, dict) and nested_contract.get("status") is not None:
        return str(nested_contract.get("status", ""))
    return str(contract.get("status", ""))


def contract_domain(contract: dict[str, Any]) -> str:
    """Resolve contract domain."""
    return str(contract.get("domain", "") or "")


def contract_data_product(contract: dict[str, Any]) -> str:
    """Resolve contract data product."""
    return str(contract.get("dataProduct", "") or "")


def contract_tenant(contract: dict[str, Any]) -> str:
    """Resolve contract tenant."""
    return str(contract.get("tenant", "") or "")


def contract_id(contract: dict[str, Any]) -> str:
    """Resolve contract identifier."""
    return str(contract.get("id", "") or "")


def contract_api_version(contract: dict[str, Any]) -> str:
    """Resolve ODCS API version."""
    return str(contract.get("apiVersion", "") or "")


def contract_kind(contract: dict[str, Any]) -> str:
    """Resolve ODCS kind."""
    return str(contract.get("kind", "") or "")


def schema_label(contract: dict[str, Any], index: int) -> str:
    """Format a schema label for selection."""
    schema_obj = schema_items(contract)[index]
    return str(schema_obj.get("name", f"schema_{index + 1}"))


def field_option_label(field_obj: dict[str, Any], index: int) -> str:
    """Format a field label for display."""
    field_name = str(field_obj.get("name", "")).strip()
    return field_name or f"field_{index + 1}"


def field_type(field_obj: dict[str, Any]) -> str:
    """Resolve the editor type for a field."""
    type_value = str(field_obj.get("logicalType") or field_obj.get("physicalType") or "string")
    return type_value if type_value in TYPE_OPTIONS else "string"


def is_technical_property_key(key: str) -> bool:
    """Return True when an ODCS property attribute is technical metadata."""
    return key in TECHNICAL_PROPERTY_KEYS


def is_business_property_key(key: str) -> bool:
    """Return True when a property attribute is editable business metadata."""
    return key in BUSINESS_PROPERTY_KEYS


def is_technical_editor_column(column: str) -> bool:
    """Map editor column names to ODCS technical attributes."""
    if column == "type":
        return is_technical_property_key("logicalType") or is_technical_property_key("physicalType")
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


def server_items(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Return server objects defined on the contract."""
    return [server for server in contract.get("servers", []) or [] if isinstance(server, dict)]


def server_label(server: dict[str, Any]) -> str:
    """Format a server label for selection."""
    server_id = str(server.get("id", "") or "").strip()
    server_name = str(server.get("server", "") or "").strip()
    environment = str(server.get("environment", "") or "").strip()

    if server_id and environment:
        return f"{server_id} ({environment})"
    if server_id:
        return server_id
    if server_name and environment:
        return f"{server_name} ({environment})"
    return server_name or "server"
