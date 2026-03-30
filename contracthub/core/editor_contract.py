from __future__ import annotations

from copy import deepcopy
from typing import Any

BUSINESS_PROPERTY_KEYS = {"businessName", "description", "examples", "tags"}
TABLE_RULE_COLUMN = "__table__"
DEFAULT_QUALITY_TYPE = "GE"
DEFAULT_QUALITY_SEVERITY = "warning"


def tags_to_text(tags: Any) -> str:
    """Render tags as a comma-separated string."""
    return ", ".join(normalize_tags(tags))


def text_to_tags(value: str) -> list[str]:
    """Parse tags from a comma-separated string."""
    return normalize_tags(value.split(","))


def normalize_tags(tags: Any) -> list[str]:
    """Normalize tag values into a stable, de-duplicated list."""
    if not isinstance(tags, list):
        return []

    normalized_tags: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = str(tag).strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized_tags.append(normalized)
    return normalized_tags


def set_mapping_text(mapping: dict[str, Any], key: str, value: str) -> None:
    """Set or remove a string mapping field."""
    if value.strip():
        mapping[key] = value
    else:
        mapping.pop(key, None)


def is_blank_quick_field_row(row: dict[str, Any]) -> bool:
    """Return True when a quick-edit row is effectively empty."""
    return not any(
        [
            str(row.get("name", "")).strip(),
            str(row.get("type", "")).strip(),
            str(row.get("description", "")).strip(),
            bool(row.get("required", False)),
        ]
    )


def is_blank_quality_row(row: dict[str, Any]) -> bool:
    """Return True when a quality row is effectively empty."""
    return not any(
        [
            str(row.get("rule_name", "")).strip(),
            str(row.get("condition", "")).strip(),
            str(row.get("column", "")).strip(),
        ]
    )


def rule_condition(rule: dict[str, Any]) -> tuple[str, str]:
    """Resolve a readable condition field for a quality rule."""
    for key in ("condition", "mustBe", "mustBeGreaterThan", "mustBeLessThan", "query", "rule"):
        if key in rule:
            value = rule.get(key)
            return key, "" if value is None else str(value)
    return "condition", ""


def optional_int(value: Any) -> int | None:
    """Convert a nullable dataframe value to an int."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
        set_mapping_text(base_field, "description", str(row.get("description", "")))
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
    set_mapping_text(field_obj, "businessName", business_name)
    set_mapping_text(field_obj, "description", description)
    set_field_examples(field_obj, examples_text)
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
        "type": str(rule.get("type") or DEFAULT_QUALITY_TYPE).strip() or DEFAULT_QUALITY_TYPE,
        "column": property_name if scope == "field" else TABLE_RULE_COLUMN,
        "condition": condition_value,
        "severity": str(rule.get("severity") or DEFAULT_QUALITY_SEVERITY).strip() or DEFAULT_QUALITY_SEVERITY,
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
            "type": str(row.get("type", DEFAULT_QUALITY_TYPE)).strip() or DEFAULT_QUALITY_TYPE,
            "severity": str(row.get("severity", DEFAULT_QUALITY_SEVERITY)).strip() or DEFAULT_QUALITY_SEVERITY,
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
            "type": DEFAULT_QUALITY_TYPE,
            "severity": DEFAULT_QUALITY_SEVERITY,
            "condition": "",
        }
    )
