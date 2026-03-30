from __future__ import annotations

from copy import deepcopy
from typing import Any

READ_ONLY_CONTRACT_FIELDS = (
    "apiVersion",
    "kind",
    "id",
    "name",
    "status",
    "domain",
    "dataProduct",
    "tenant",
    "servers",
)

EDITABLE_SCHEMA_FIELDS = {"businessName", "description", "tags", "quality", "properties"}
EDITABLE_PROPERTY_FIELDS = {
    "businessName",
    "description",
    "examples",
    "tags",
    "classification",
    "transformDescription",
    "quality",
    "properties",
    "items",
}


def normalize_draft_contract(draft_contract: dict[str, Any], main_contract: dict[str, Any]) -> dict[str, Any]:
    """Preserve non-editable fields from the main contract in a user draft.

    ContractHub allows business-facing edits on descriptive metadata but keeps
    contract fundamentals and technical schema/property attributes sourced from
    the canonical main contract.

    Version is intentionally not preserved here because release/version
    management is handled by the delivery pipeline.
    """
    normalized = deepcopy(draft_contract)
    for field in READ_ONLY_CONTRACT_FIELDS:
        if field in main_contract:
            normalized[field] = deepcopy(main_contract[field])
        else:
            normalized.pop(field, None)
    _preserve_schema_and_property_fields(normalized, main_contract)
    return normalized


def _preserve_schema_and_property_fields(draft_contract: dict[str, Any], main_contract: dict[str, Any]) -> None:
    schema_key = _schema_key(draft_contract, main_contract)
    draft_schemas = draft_contract.get(schema_key)
    main_schemas = main_contract.get(schema_key)
    if not isinstance(draft_schemas, list) or not isinstance(main_schemas, list):
        return

    normalized_schemas: list[Any] = []
    for index, draft_schema in enumerate(draft_schemas):
        if index < len(main_schemas) and isinstance(draft_schema, dict) and isinstance(main_schemas[index], dict):
            normalized_schemas.append(_preserve_schema_fields(draft_schema, main_schemas[index]))
        else:
            normalized_schemas.append(draft_schema)
    draft_contract[schema_key] = normalized_schemas


def _preserve_schema_fields(draft_schema: dict[str, Any], main_schema: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(draft_schema)
    for field_name, value in main_schema.items():
        if field_name in EDITABLE_SCHEMA_FIELDS:
            continue
        normalized[field_name] = deepcopy(value)

    for field_name in list(normalized.keys()):
        if field_name in EDITABLE_SCHEMA_FIELDS:
            continue
        if field_name not in main_schema:
            normalized.pop(field_name, None)

    draft_properties = normalized.get("properties")
    main_properties = main_schema.get("properties")
    if isinstance(draft_properties, list) and isinstance(main_properties, list):
        normalized["properties"] = [
            _preserve_property_fields(draft_property, main_properties[index])
            if index < len(main_properties) and isinstance(draft_property, dict) and isinstance(main_properties[index], dict)
            else draft_property
            for index, draft_property in enumerate(draft_properties)
        ]
    return normalized


def _preserve_property_fields(draft_property: dict[str, Any], main_property: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(draft_property)
    for field_name, value in main_property.items():
        if field_name in EDITABLE_PROPERTY_FIELDS:
            continue
        normalized[field_name] = deepcopy(value)

    for field_name in list(normalized.keys()):
        if field_name in EDITABLE_PROPERTY_FIELDS:
            continue
        if field_name not in main_property:
            normalized.pop(field_name, None)

    draft_children = normalized.get("properties")
    main_children = main_property.get("properties")
    if isinstance(draft_children, list) and isinstance(main_children, list):
        normalized["properties"] = [
            _preserve_property_fields(draft_child, main_children[index])
            if index < len(main_children) and isinstance(draft_child, dict) and isinstance(main_children[index], dict)
            else draft_child
            for index, draft_child in enumerate(draft_children)
        ]

    draft_items = normalized.get("items")
    main_items = main_property.get("items")
    if isinstance(draft_items, dict) and isinstance(main_items, dict):
        normalized["items"] = _preserve_property_fields(draft_items, main_items)
    return normalized


def _schema_key(*contracts: dict[str, Any]) -> str:
    for contract in contracts:
        if isinstance(contract.get("schema"), list):
            return "schema"
        if isinstance(contract.get("schemas"), list):
            return "schemas"
    return "schema"
