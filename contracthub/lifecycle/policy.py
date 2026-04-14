from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from open_data_contract_standard.model import CustomProperty, OpenDataContractStandard, SchemaObject, SchemaProperty
from contracthub.lifecycle.helpers import is_active_contract, normalize_status, schema_items
from contracthub.lifecycle.merge_engine import _decimal_precision_reduction, _decimal_scale_reduction


@dataclass(slots=True)
class BreakingChange:
    """Detected breaking change in lifecycle evaluation."""

    path: str
    message: str


@dataclass(slots=True)
class PolicyEvaluation:
    """Lifecycle policy evaluation result."""

    valid: bool
    breaking_changes: list[BreakingChange] = field(default_factory=list)
    id_violation: bool = False
    version_violation: bool = False


def evaluate_merge_policy(
    base_contract: OpenDataContractStandard,
    merged_contract: OpenDataContractStandard,
) -> PolicyEvaluation:
    """Evaluate breaking-change policy for a merged contract.

    Breaking checks apply only when contract status is active and schema/field
    lifecycleStatus is not draft/deprecated.
    """
    if not is_active_contract(base_contract):
        return PolicyEvaluation(valid=True)

    breaks: list[BreakingChange] = []
    id_violation = False
    version_violation = False

    if _root_id_changed(base_contract, merged_contract):
        id_violation = True
        breaks.append(
            BreakingChange(
                path="id",
                message="Contract ID mismatch. You changed the root ID of the contract, which is immutable. If you want to create a new contract, use 'contracthub import --new' or change the ID back.",
            )
        )

    if _root_version_changed(base_contract, merged_contract):
        version_violation = True
        breaks.append(
            BreakingChange(
                path="version",
                message="Contract version mismatch. Contract versions are release-managed and cannot be manually updated during normal import/merge. Please revert the version change and use 'contracthub release prepare'.",
            )
        )

    merged_schema_index = _schema_index(merged_contract)

    for schema in schema_items(base_contract):
        schema_key = _schema_key(schema)
        if not schema_key:
            continue

        if _is_draft_or_deprecated(schema):
            continue

        target_schema = merged_schema_index.get(schema_key)
        if target_schema is None:
            breaks.append(BreakingChange(path=f"schema[{schema_key}]", message="Schema removed from active contract"))
            continue


        base_relationships = {f"{rel.type}:{rel.from_}->{rel.to}".lower() for rel in getattr(schema, "relationships", []) or []}
        target_relationships = {f"{rel.type}:{rel.from_}->{rel.to}".lower() for rel in getattr(target_schema, "relationships", []) or []}

        for rel_key in base_relationships:
            if rel_key and rel_key not in target_relationships:
                breaks.append(
                    BreakingChange(
                        path=f"schema[{schema_key}].relationships",
                        message=f"Relationship '{rel_key}' removed from active lifecycle scope. Downstream joins may fail."
                    )
                )

        base_props = _prop_index(schema)



        target_props = _prop_index(target_schema)
        for prop_key, base_prop in base_props.items():
            if _is_draft_or_deprecated(base_prop):
                continue
            if prop_key not in target_props:
                breaks.append(
                    BreakingChange(
                        path=f"schema[{schema_key}].properties[{prop_key}]",
                        message="Property removed from active lifecycle scope",
                    )
                )
                continue

            target_prop = target_props[prop_key]
            breaks.extend(
                _property_breaking_changes(
                    base_prop=base_prop,
                    target_prop=target_prop,
                    path=f"schema[{schema_key}].properties[{prop_key}]",
                )
            )

    return PolicyEvaluation(
        valid=not breaks,
        breaking_changes=breaks,
        id_violation=id_violation,
        version_violation=version_violation,
    )


def _root_id_changed(
    base_contract: OpenDataContractStandard,
    merged_contract: OpenDataContractStandard,
) -> bool:
    base_id = str(base_contract.id or "").strip()
    merged_id = str(merged_contract.id or "").strip()
    if not base_id and not merged_id:
        return False
    return base_id != merged_id


def _root_version_changed(
    base_contract: OpenDataContractStandard,
    merged_contract: OpenDataContractStandard,
) -> bool:
    base_version = str(base_contract.version or "").strip()
    merged_version = str(merged_contract.version or "").strip()
    if not base_version and not merged_version:
        return False
    return base_version != merged_version


def _schema_key(schema: SchemaObject) -> str:
    value = schema.physicalName or schema.name or ""
    return str(value).lower()


def _schema_index(contract: OpenDataContractStandard) -> dict[str, SchemaObject]:
    index: dict[str, SchemaObject] = {}
    for schema in schema_items(contract):
        key = _schema_key(schema)
        if key:
            index[key] = schema
    return index


def _prop_index(schema: SchemaObject) -> dict[str, SchemaProperty]:
    properties = schema.properties
    if not isinstance(properties, list):
        return {}

    index: dict[str, SchemaProperty] = {}
    for prop in properties:
        key = str(prop.physicalName or prop.name or "").lower()
        if key:
            index[key] = prop
    return index


def _is_draft_or_deprecated(entity: SchemaObject | SchemaProperty) -> bool:
    value = getattr(entity, "lifecycleStatus", None)
    if value is None:
        value = _lifecycle_from_custom_properties(getattr(entity, "customProperties", None))
    lifecycle_status = normalize_status(value, default="active")
    return lifecycle_status in {"draft", "deprecated"}


def _property_breaking_changes(
    base_prop: SchemaProperty,
    target_prop: SchemaProperty,
    path: str,
) -> list[BreakingChange]:
    breaks: list[BreakingChange] = []

    base_logical = base_prop.logicalType
    target_logical = target_prop.logicalType
    if base_logical is not None and target_logical is not None and str(base_logical) != str(target_logical):
        breaks.append(
            BreakingChange(
                path=f"{path}.logicalType",
                message=f"Logical type changed from {base_logical!r} to {target_logical!r}",
            )
        )

    base_physical = base_prop.physicalType
    target_physical = target_prop.physicalType

    if _is_physical_type_narrowing(base_physical, target_physical):
        breaks.append(
            BreakingChange(
                path=f"{path}.physicalType",
                message=f"Physical type narrowed from {base_physical!r} to {target_physical!r}",
            )
        )

    if _decimal_precision_reduction(target_physical, base_physical) or _decimal_scale_reduction(
        target_physical, base_physical
    ):
        breaks.append(
            BreakingChange(
                path=f"{path}.physicalType",
                message=f"Decimal precision/scale reduced from {base_physical!r} to {target_physical!r}",
            )
        )

    base_required = base_prop.required
    target_required = target_prop.required
    if base_required is False and target_required is True:
        breaks.append(
            BreakingChange(
                path=f"{path}.required",
                message="Required flag tightened from False to True",
            )
        )

    if _is_enum_value_reduction(base_prop, target_prop):
        breaks.append(
            BreakingChange(
                path=f"{path}.enum",
                message="Enum values reduced",
            )
        )

    return breaks


def _is_physical_type_narrowing(base_physical: Any, target_physical: Any) -> bool:
    if not isinstance(base_physical, str) or not isinstance(target_physical, str):
        return False

    base_type = base_physical.strip().lower()
    target_type = target_physical.strip().lower()
    if base_type == target_type:
        return False

    base_family = _physical_type_family(base_type)
    target_family = _physical_type_family(target_type)
    if base_family != target_family:
        return False

    base_width = _type_width(base_type)
    target_width = _type_width(target_type)
    if base_width is None or target_width is None:
        return False
    return target_width < base_width


def _physical_type_family(physical_type: str) -> str:
    if physical_type.startswith(("varchar", "char", "string", "text")):
        return "string"
    if physical_type.startswith(("varbinary", "binary")):
        return "binary"
    if physical_type.startswith(("tinyint", "smallint", "int", "integer", "bigint")):
        return "integer"
    return physical_type.split("(", 1)[0]


def _type_width(physical_type: str) -> int | None:
    integer_widths = {
        "tinyint": 8,
        "smallint": 16,
        "int": 32,
        "integer": 32,
        "bigint": 64,
    }
    if physical_type in integer_widths:
        return integer_widths[physical_type]

    string_match = re.match(r"^(?:var)?char\((\d+)\)$", physical_type)
    if string_match:
        return int(string_match.group(1))

    binary_match = re.match(r"^(?:var)?binary\((\d+)\)$", physical_type)
    if binary_match:
        return int(binary_match.group(1))

    return None


def _is_enum_value_reduction(
    base_prop: SchemaProperty,
    target_prop: SchemaProperty,
) -> bool:
    base_values = _enum_values(base_prop)
    target_values = _enum_values(target_prop)
    if not base_values or not target_values:
        return False
    return not base_values.issubset(target_values)


def _enum_values(prop: SchemaProperty) -> set[str]:
    for key in ("enum", "enumValues"):
        values = getattr(prop, key, None)
        if not isinstance(values, list):
            continue
        return {str(item) for item in values}
    return set()


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
