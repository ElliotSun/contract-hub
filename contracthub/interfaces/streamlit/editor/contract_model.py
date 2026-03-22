"""ODCS-centric helpers for editor state and mutations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import yaml

from .constants import BUSINESS_PROPERTY_KEYS, QUALITY_SEVERITY_OPTIONS, QUALITY_TYPE_OPTIONS, TABLE_RULE_COLUMN, TECHNICAL_PROPERTY_KEYS, TYPE_OPTIONS
from .helpers import is_blank_quality_row, is_blank_quick_field_row, normalize_tags, optional_int, rule_condition, set_mapping_text, text_to_tags


def parse_yaml_payload(source_yaml: str) -> dict[str, Any]:
    """Parse YAML into the working contract mapping."""
    payload = yaml.safe_load(source_yaml)
    if not isinstance(payload, dict):
        raise ValueError("Contract YAML must deserialize into a mapping object.")
    if not schema_items(payload):
        payload["schema"] = [{"name": "default_schema", "properties": []}]
    return payload


def contract_to_yaml(contract: dict[str, Any]) -> str:
    """Serialize the working contract back to YAML."""
    return yaml.safe_dump(contract, sort_keys=False, allow_unicode=False)


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


def description_mapping(contract: dict[str, Any], *, create: bool = False) -> dict[str, Any]:
    """Return the ODCS root description mapping."""
    description = contract.get("description")
    if isinstance(description, dict):
        return description
    if create:
        contract["description"] = {"purpose": description} if isinstance(description, str) and description.strip() else {}
        return contract["description"]
    return {}


def contract_description_part(contract: dict[str, Any], part: str) -> str:
    """Resolve a structured contract description field."""
    return str(description_mapping(contract).get(part, "") or "")


def set_contract_description_part(contract: dict[str, Any], part: str, value: str) -> None:
    """Persist a structured contract description field."""
    description = description_mapping(contract, create=True)
    set_mapping_text(description, part, value)
    if not description:
        contract.pop("description", None)


def contract_tags(contract: dict[str, Any]) -> list[str]:
    """Resolve contract tags."""
    if isinstance(contract.get("tags"), list):
        return normalize_tags(contract["tags"])
    nested_contract = contract.get("contract")
    if isinstance(nested_contract, dict) and isinstance(nested_contract.get("tags"), list):
        return normalize_tags(nested_contract["tags"])
    return []


def set_contract_tags_list(contract: dict[str, Any], tags: list[str]) -> None:
    """Persist contract tags from a normalized list."""
    contract["tags"] = normalize_tags(tags)


def schema_items(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the contract schema list."""
    if isinstance(contract.get("schema"), list):
        return contract["schema"]
    if isinstance(contract.get("schemas"), list):
        return contract["schemas"]
    contract["schema"] = []
    return contract["schema"]


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


def field_lifecycle_status(field_obj: dict[str, Any]) -> str:
    """Resolve field lifecycle status."""
    status = field_obj.get("status")
    if status is not None:
        return str(status)
    for item in field_obj.get("customProperties", []) or []:
        if isinstance(item, dict) and str(item.get("property", "")).strip().lower() == "lifecyclestatus":
            return str(item.get("value", ""))
    return ""


def set_field_lifecycle_status(field_obj: dict[str, Any], value: Any) -> None:
    """Persist field lifecycle status."""
    status_value = str(value or "").strip() or "draft"
    field_obj["status"] = status_value
    custom_properties = [
        deepcopy(item)
        for item in field_obj.get("customProperties", []) or []
        if isinstance(item, dict) and str(item.get("property", "")).strip().lower() != "lifecyclestatus"
    ]
    custom_properties.append({"property": "lifecycleStatus", "value": status_value})
    field_obj["customProperties"] = custom_properties


def field_examples_text(field_obj: dict[str, Any]) -> str:
    """Render examples as a newline-separated text block."""
    examples = field_obj.get("examples")
    if not isinstance(examples, list):
        return ""
    return "\n".join(str(example) for example in examples if str(example).strip())


def set_field_examples(field_obj: dict[str, Any], examples_text: str) -> None:
    """Persist examples from a newline-separated text block."""
    examples = [line.strip() for line in examples_text.splitlines() if line.strip()]
    if examples:
        field_obj["examples"] = examples
    else:
        field_obj.pop("examples", None)


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


def apply_quick_field_rows(schema_obj: dict[str, Any], edited_rows: list[dict[str, Any]]) -> None:
    """Write quick-edit business fields back to the selected schema."""
    original_fields = schema_obj.get("properties", []) or []
    updated_fields: list[dict[str, Any]] = []

    for row in edited_rows:
        if is_blank_quick_field_row(row):
            continue
        original_index = optional_int(row.get("__original_index"))
        base_field = (
            deepcopy(original_fields[original_index])
            if original_index is not None and 0 <= original_index < len(original_fields)
            else {}
        )
        if is_business_property_key("description"):
            set_mapping_text(base_field, "description", str(row.get("description", "")))
        if is_business_property_key("businessName"):
            set_mapping_text(base_field, "businessName", str(row.get("businessName", "")))
        set_field_lifecycle_status(base_field, row.get("lifecycleStatus", "draft"))
        if "physicalName" not in base_field:
            base_field["physicalName"] = base_field.get("name", "")
        updated_fields.append(base_field)

    schema_obj["properties"] = updated_fields


def apply_field_detail(
    field_obj: dict[str, Any],
    *,
    lifecycle_status: str,
    business_name: str,
    description: str,
    examples_text: str,
    tags_text: str,
    classification: str,
    transform_description: str,
) -> None:
    """Apply editable business metadata from the detail panel."""
    set_field_lifecycle_status(field_obj, lifecycle_status)
    if is_business_property_key("businessName"):
        set_mapping_text(field_obj, "businessName", business_name)
    if is_business_property_key("description"):
        set_mapping_text(field_obj, "description", description)
    if is_business_property_key("examples"):
        set_field_examples(field_obj, examples_text)
    if is_business_property_key("tags"):
        field_obj["tags"] = text_to_tags(tags_text)
    set_mapping_text(field_obj, "classification", classification)
    set_mapping_text(field_obj, "transformDescription", transform_description)
    if "physicalName" not in field_obj:
        field_obj["physicalName"] = field_obj.get("name", "")


def add_field(schema_obj: dict[str, Any]) -> None:
    """Append a blank field to the selected schema."""
    fields = schema_obj.setdefault("properties", [])
    field_number = len(fields) + 1
    fields.append(
        {
            "name": f"field_{field_number}",
            "physicalName": f"field_{field_number}",
            "logicalType": "string",
            "physicalType": "string",
            "required": False,
            "status": "draft",
            "customProperties": [{"property": "lifecycleStatus", "value": "draft"}],
        }
    )


def field_by_name(schema_obj: dict[str, Any], field_name: str) -> dict[str, Any] | None:
    """Return a field by name."""
    target_name = field_name.strip()
    for field_obj in schema_obj.get("properties", []) or []:
        if isinstance(field_obj, dict) and str(field_obj.get("name", "")).strip() == target_name:
            return field_obj
    return None


def selected_schema_field_names(schema_obj: dict[str, Any]) -> list[str]:
    """Return field names for the selected schema."""
    return [
        str(field_obj.get("name", "")).strip()
        for field_obj in schema_obj.get("properties", []) or []
        if isinstance(field_obj, dict) and str(field_obj.get("name", "")).strip()
    ]


def quality_row(rule: dict[str, Any], *, scope: str, rule_index: int, property_name: str) -> dict[str, Any]:
    """Create a quality rule editor row."""
    condition_key, condition_value = rule_condition(rule)
    return {
        "rule_name": str(rule.get("name") or rule.get("metric") or "").strip(),
        "type": str(rule.get("type") or "GE").strip() or "GE",
        "column": property_name if scope == "field" else TABLE_RULE_COLUMN,
        "condition": condition_value,
        "severity": str(rule.get("severity") or "warning").strip() or "warning",
        "__scope": scope,
        "__rule_index": rule_index,
        "__property_name": property_name,
        "__condition_key": condition_key,
    }


def quality_rows(schema_obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten quality rules for the selected schema."""
    rows: list[dict[str, Any]] = []

    for index, rule in enumerate(schema_obj.get("quality", []) or []):
        if isinstance(rule, dict):
            rows.append(quality_row(rule, scope="table", rule_index=index, property_name=""))

    for field_obj in schema_obj.get("properties", []) or []:
        if not isinstance(field_obj, dict):
            continue
        field_name = str(field_obj.get("name", "")).strip()
        for index, rule in enumerate(field_obj.get("quality", []) or []):
            if isinstance(rule, dict):
                rows.append(quality_row(rule, scope="field", rule_index=index, property_name=field_name))

    return rows


def apply_quality_rows(schema_obj: dict[str, Any], edited_rows: list[dict[str, Any]]) -> None:
    """Write edited quality rows back to the selected schema."""
    schema_obj["quality"] = []
    for field_obj in schema_obj.get("properties", []) or []:
        if isinstance(field_obj, dict):
            field_obj.pop("quality", None)

    for row in edited_rows:
        if is_blank_quality_row(row):
            continue
        rule = {
            "name": str(row.get("rule_name", "")).strip(),
            "type": str(row.get("type", QUALITY_TYPE_OPTIONS[0])).strip() or QUALITY_TYPE_OPTIONS[0],
            "severity": str(row.get("severity", QUALITY_SEVERITY_OPTIONS[0])).strip() or QUALITY_SEVERITY_OPTIONS[0],
        }
        condition_key = str(row.get("__condition_key", "condition")).strip() or "condition"
        condition_value = str(row.get("condition", "")).strip()
        if condition_value:
            rule[condition_key] = condition_value

        target_column = str(row.get("column", TABLE_RULE_COLUMN)).strip() or TABLE_RULE_COLUMN
        if target_column == TABLE_RULE_COLUMN:
            schema_obj.setdefault("quality", []).append(rule)
            continue

        field_obj = field_by_name(schema_obj, target_column)
        if field_obj is not None:
            field_obj.setdefault("quality", []).append(rule)

    if not schema_obj.get("quality"):
        schema_obj.pop("quality", None)


def add_quality_rule(schema_obj: dict[str, Any]) -> None:
    """Append a blank table-level rule to the selected schema."""
    schema_obj.setdefault("quality", []).append(
        {
            "name": "",
            "type": QUALITY_TYPE_OPTIONS[0],
            "severity": QUALITY_SEVERITY_OPTIONS[0],
            "condition": "",
        }
    )


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
