from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Tuple

from open_data_contract_standard.model import (
    CustomProperty,
    DataQuality,
    OpenDataContractStandard,
    SchemaObject,
    SchemaProperty,
)

BUSINESS_METADATA_KEYS = {
    "description",
    "businessName",
    "classification",
    "tags",
    "examples",
    "lifecycleStatus",
    "status",
}
# Quality rules are lifecycle metadata and must be merged using name-based lifecycle semantics.

REMOVED_FLAG = {"property": "contracthub.removed", "value": "true"}


@dataclass(slots=True)
class MergeConflict:
    """Represents a merge conflict between source and target contracts."""

    path: str
    rule: str
    base_value: Any
    business_value: Any


@dataclass(slots=True)
class MergeResult:
    """Merge result payload."""

    contract: OpenDataContractStandard
    conflicts: list[MergeConflict] = field(default_factory=list)


@dataclass(slots=True)
class ContractMergeEngine:
    """Merge ODCS contracts while preserving business metadata and quality rules."""

    def merge(
        self,
        base_contract: OpenDataContractStandard | dict[str, Any],
        business_contract: OpenDataContractStandard | dict[str, Any],
        *,
        fail_on_conflict: bool = False,
    ) -> MergeResult:
        base_model = _to_odcs_model(base_contract)
        business_model = _to_odcs_model(business_contract)

        conflicts = self.detect_conflicts(base_model, business_model)
        if fail_on_conflict and conflicts:
            rules = ", ".join({c.rule for c in conflicts})
            raise ValueError(f"Merge conflicts detected: {rules}")

        merged_model = self._merge_odcs_models(existing_model=business_model, imported_model=base_model)
        return MergeResult(contract=merged_model, conflicts=conflicts)

    def detect_conflicts(
        self,
        base_contract: OpenDataContractStandard | dict[str, Any],
        business_contract: OpenDataContractStandard | dict[str, Any],
    ) -> list[MergeConflict]:
        base_model = _to_odcs_model(base_contract)
        business_model = _to_odcs_model(business_contract)

        conflicts: list[MergeConflict] = []
        base_schema = { _schema_object_id(schema): schema for schema in (base_model.schema_ or []) if _schema_object_id(schema) }
        business_schema = { _schema_object_id(schema): schema for schema in (business_model.schema_ or []) if _schema_object_id(schema) }

        for schema_key, base_schema_obj in base_schema.items():
            business_schema_obj = business_schema.get(schema_key)
            if business_schema_obj is None:
                continue

            base_props = {
                _property_id(prop): prop
                for prop in (getattr(base_schema_obj, "properties", None) or [])
                if _property_id(prop)
            }
            business_props = {
                _property_id(prop): prop
                for prop in (getattr(business_schema_obj, "properties", None) or [])
                if _property_id(prop)
            }

            for prop_key, base_prop in base_props.items():
                business_prop = business_props.get(prop_key)
                if business_prop is None:
                    continue

                path = f"schema[{schema_key}].properties[{prop_key}]"
                conflicts.extend(self._property_conflicts(path, base_prop, business_prop))

        return conflicts

    def _property_conflicts(self, path: str, base_prop: Any, business_prop: Any) -> list[MergeConflict]:
        conflicts: list[MergeConflict] = []
        base_logical = _object_value(base_prop, "logicalType")
        business_logical = _object_value(business_prop, "logicalType")
        base_physical = _object_value(base_prop, "physicalType")
        business_physical = _object_value(business_prop, "physicalType")

        if _value_conflict(base_logical, business_logical):
            conflicts.append(
                MergeConflict(
                    path=f"{path}.logicalType",
                    rule="logical_type_mismatch",
                    base_value=base_logical,
                    business_value=business_logical,
                )
            )

        if _value_conflict(base_physical, business_physical):
            conflicts.append(
                MergeConflict(
                    path=f"{path}.physicalType",
                    rule="physical_type_mismatch",
                    base_value=base_physical,
                    business_value=business_physical,
                )
            )

        base_required = _object_value(base_prop, "required")
        business_required = _object_value(business_prop, "required")
        if base_required is True and business_required is False:
            conflicts.append(
                MergeConflict(
                    path=f"{path}.required",
                    rule="required_tightening",
                    base_value=base_required,
                    business_value=business_required,
                )
            )

        if _decimal_reduction(base_physical, business_physical):
            conflicts.append(
                MergeConflict(
                    path=f"{path}.physicalType",
                    rule="decimal_reduction",
                    base_value=base_physical,
                    business_value=business_physical,
                )
            )

        return conflicts

    def _merge_odcs_models(
        self,
        *,
        existing_model: OpenDataContractStandard,
        imported_model: OpenDataContractStandard,
    ) -> OpenDataContractStandard:
        merged = existing_model.model_copy(deep=True)

        # Technical updates come from imported model at contract level, except schema which is merged separately.
        for field_name in OpenDataContractStandard.model_fields:
            if field_name in {"schema_", "quality", "customProperties"}:
                continue
            imported_value = getattr(imported_model, field_name, None)
            if imported_value is not None:
                setattr(merged, field_name, deepcopy(imported_value))

        # Governance metadata from existing contract remains source of truth.
        for metadata_key in BUSINESS_METADATA_KEYS:
            if not hasattr(merged, metadata_key):
                continue
            existing_value = _object_value(existing_model, metadata_key)
            if existing_value is not None:
                setattr(merged, metadata_key, deepcopy(existing_value))

        # customProperties are lifecycle metadata and must always be key-merged, never overwritten.
        merged.customProperties = _merge_custom_properties_models(
            existing_model.customProperties,
            imported_model.customProperties,
        )
        # Quality rules represent governance lifecycle state and must be merged by rule identity.
        if hasattr(merged, "quality"):
            merged.quality = _combine_quality_rules_models(  # type: ignore[attr-defined]
                getattr(existing_model, "quality", None),
                getattr(imported_model, "quality", None),
            )

        merged.schema_ = _merge_schema_objects_models(existing_model.schema_ or [], imported_model.schema_ or [])
        self._merge_quality_rules_on_models(base_model=imported_model, business_model=existing_model, merged_model=merged)
        return merged

    def _merge_quality_rules_on_models(
        self,
        *,
        base_model: OpenDataContractStandard,
        business_model: OpenDataContractStandard,
        merged_model: OpenDataContractStandard,
    ) -> None:
        # Root customProperties lifecycle merge: imported overrides by key, existing preserved otherwise.
        merged_model.customProperties = _merge_custom_properties_models(
            business_model.customProperties,
            base_model.customProperties,
        )
        if hasattr(merged_model, "quality"):
            merged_model.quality = _combine_quality_rules_models(  # type: ignore[attr-defined]
                getattr(business_model, "quality", None),
                getattr(base_model, "quality", None),
            )

        base_schema = {_schema_object_id(schema): schema for schema in (base_model.schema_ or []) if _schema_object_id(schema)}
        business_schema = {
            _schema_object_id(schema): schema for schema in (business_model.schema_ or []) if _schema_object_id(schema)
        }

        for merged_schema_obj in merged_model.schema_ or []:
            schema_key = _schema_object_id(merged_schema_obj)
            if not schema_key:
                continue
            base_schema_obj = base_schema.get(schema_key)
            business_schema_obj = business_schema.get(schema_key)

            schema_metadata_custom_props = _merge_custom_properties_models(
                getattr(business_schema_obj, "customProperties", None),
                getattr(base_schema_obj, "customProperties", None),
            )
            merged_schema_obj.customProperties = _merge_custom_properties_models(
                merged_schema_obj.customProperties,
                schema_metadata_custom_props,
            )
            merged_schema_obj.quality = _combine_quality_rules_models(
                getattr(business_schema_obj, "quality", None),
                getattr(base_schema_obj, "quality", None),
            )

            merged_props = {
                _property_id(prop): prop
                for prop in (merged_schema_obj.properties or [])
                if _property_id(prop)
            }
            base_props = {
                _property_id(prop): prop
                for prop in (getattr(base_schema_obj, "properties", None) or [])
                if _property_id(prop)
            }
            business_props = {
                _property_id(prop): prop
                for prop in (getattr(business_schema_obj, "properties", None) or [])
                if _property_id(prop)
            }

            for prop_key, merged_prop in merged_props.items():
                base_prop = base_props.get(prop_key)
                business_prop = business_props.get(prop_key)
                prop_metadata_custom_props = _merge_custom_properties_models(
                    getattr(business_prop, "customProperties", None),
                    getattr(base_prop, "customProperties", None),
                )
                merged_prop.customProperties = _merge_custom_properties_models(
                    merged_prop.customProperties,
                    prop_metadata_custom_props,
                )
                merged_prop.quality = _combine_quality_rules_models(
                    getattr(business_prop, "quality", None),
                    getattr(base_prop, "quality", None),
                )

def merge_contract(existing: Dict[str, Any], imported: Dict[str, Any]) -> Dict[str, Any]:
    """Merge imported contract into existing contract in patch mode."""
    engine = ContractMergeEngine()
    merged_model = engine.merge(base_contract=imported, business_contract=existing).contract
    merged_dict = merged_model.model_dump(by_alias=True, exclude_none=True)

    # Backward compatibility: preserve schema_ alias if caller used it.
    if "schema_" in existing or "schema_" in imported:
        merged_dict["schema_"] = merged_dict.pop("schema", [])

    # Backward compatibility: keep explicit deprecated markers for removed entities.
    _apply_legacy_removed_markers(merged_dict)
    return merged_dict


def _merge_schema_objects_models(
    existing_schema: list[SchemaObject],
    imported_schema: list[SchemaObject],
) -> list[SchemaObject]:
    existing_index = {_schema_object_id(obj): obj for obj in existing_schema if _schema_object_id(obj)}
    imported_index = {_schema_object_id(obj): obj for obj in imported_schema if _schema_object_id(obj)}

    merged_schema: list[SchemaObject] = []
    # All ordering must be identity-based to ensure stable Git diffs.
    for imported_id in sorted(imported_index):
        imported_obj = imported_index[imported_id]
        existing_obj = existing_index.get(imported_id)
        if existing_obj is None:
            merged_schema.append(imported_obj.model_copy(deep=True))
            continue
        merged_schema.append(_merge_schema_object_models(existing_obj, imported_obj))

    # Removed entities are appended in deterministic identity order.
    for existing_id in sorted(existing_index):
        if existing_id in imported_index:
            continue
        merged_schema.append(_flag_removed_schema_model(existing_index[existing_id]))

    # Final deterministic ordering by canonical ODCS identity (`name`).
    merged_schema.sort(key=_schema_object_id)
    return merged_schema


def _merge_schema_object_models(existing_obj: SchemaObject, imported_obj: SchemaObject) -> SchemaObject:
    merged_obj = imported_obj.model_copy(deep=True)
    _preserve_business_metadata_on_model(merged_obj, existing_obj)
    merged_obj.customProperties = _merge_custom_properties_models(
        existing_obj.customProperties,
        imported_obj.customProperties,
    )
    merged_obj.properties = _merge_properties_models(existing_obj.properties or [], imported_obj.properties or [])
    return merged_obj


def _merge_properties_models(
    existing_props: list[SchemaProperty],
    imported_props: list[SchemaProperty],
) -> list[SchemaProperty]:
    existing_index = {_property_id(prop): prop for prop in existing_props if _property_id(prop)}
    imported_index = {_property_id(prop): prop for prop in imported_props if _property_id(prop)}

    merged_props: list[SchemaProperty] = []
    # All ordering must be identity-based to ensure stable Git diffs.
    for imported_id in sorted(imported_index):
        imported_prop = imported_index[imported_id]
        existing_prop = existing_index.get(imported_id)
        if existing_prop is None:
            merged_props.append(imported_prop.model_copy(deep=True))
            continue

        merged_prop = imported_prop.model_copy(deep=True)
        _preserve_business_metadata_on_model(merged_prop, existing_prop)
        merged_prop.customProperties = _merge_custom_properties_models(
            existing_prop.customProperties,
            imported_prop.customProperties,
        )
        merged_props.append(merged_prop)

    # Removed entities are appended in deterministic identity order.
    for existing_id in sorted(existing_index):
        if existing_id in imported_index:
            continue
        merged_props.append(_flag_removed_property_model(existing_index[existing_id]))

    # Final deterministic ordering by canonical ODCS identity (`name`).
    merged_props.sort(key=_property_id)
    return merged_props


def _preserve_business_metadata_on_model(target: Any, source: Any) -> None:
    for key in BUSINESS_METADATA_KEYS:
        if not hasattr(target, key):
            continue
        value = _object_value(source, key)
        if value is not None:
            setattr(target, key, deepcopy(value))


def _flag_removed_schema_model(entity: SchemaObject) -> SchemaObject:
    removed = entity.model_copy(deep=True)
    removed.customProperties = _merge_custom_properties_models(removed.customProperties, [REMOVED_FLAG])
    return removed


def _flag_removed_property_model(entity: SchemaProperty) -> SchemaProperty:
    removed = entity.model_copy(deep=True)
    removed.customProperties = _merge_custom_properties_models(removed.customProperties, [REMOVED_FLAG])
    return removed


def _apply_legacy_removed_markers(contract: dict[str, Any]) -> None:
    schema_key = "schema_" if isinstance(contract.get("schema_"), list) else "schema"
    schema_items = contract.get(schema_key)
    if not isinstance(schema_items, list):
        return

    for schema_obj in schema_items:
        if not isinstance(schema_obj, dict):
            continue
        if _has_removed_flag(_normalize_custom_properties(schema_obj.get("customProperties"))):
            schema_obj["deprecated"] = True

        props = schema_obj.get("properties")
        if not isinstance(props, list):
            continue
        for prop in props:
            if not isinstance(prop, dict):
                continue
            if _has_removed_flag(_normalize_custom_properties(prop.get("customProperties"))):
                prop["deprecated"] = True


def _schema_object_id(schema_obj: Any) -> str:
    # ODCS defines `name` as the stable identity.
    # `physicalName` is a technical attribute and must not be used as merge identity.
    return str(_object_value(schema_obj, "name") or "").lower()


def _property_id(prop: Any) -> str:
    # ODCS defines `name` as the stable identity.
    # `physicalName` is a technical attribute and must not be used as merge identity.
    return str(_object_value(prop, "name") or "").lower()


def _has_removed_flag(custom_properties: Iterable[Dict[str, Any]]) -> bool:
    for item in custom_properties:
        if item.get("property") == REMOVED_FLAG["property"] and str(item.get("value")).lower() == "true":
            return True
    return False


def _value_conflict(base_value: Any, business_value: Any) -> bool:
    return base_value is not None and business_value is not None and base_value != business_value


def _decimal_reduction(base_physical_type: Any, business_physical_type: Any) -> bool:
    base_ps = _decimal_precision_scale(base_physical_type)
    business_ps = _decimal_precision_scale(business_physical_type)
    if base_ps is None or business_ps is None:
        return False

    base_precision, base_scale = base_ps
    business_precision, business_scale = business_ps
    return base_precision < business_precision or base_scale < business_scale


def _decimal_precision_scale(physical_type: Any) -> tuple[int, int] | None:
    if not isinstance(physical_type, str):
        return None

    match = re.match(r"\s*decimal\((\d+)\s*,\s*(\d+)\)\s*", physical_type, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _quality_rule_sort_key(rule: Any) -> str:
    return _quality_rule_name(rule)


def _quality_rule_name(rule: Any) -> str:
    return str(_object_value(rule, "name") or "").strip().lower()


def _combine_quality_rules_models(*rule_sets: Any) -> list[DataQuality] | None:
    # Quality rules represent governance lifecycle state.
    named: dict[str, DataQuality] = {}
    unnamed: list[DataQuality] = []

    for rules in rule_sets:
        for rule in _normalize_quality_models(rules):
            rule_name = _quality_rule_name(rule)
            if rule_name:
                named[rule_name] = rule.model_copy(deep=True)
            else:
                unnamed.append(rule.model_copy(deep=True))

    merged = list(named.values()) + unnamed
    # Sorting must be based solely on identity to guarantee deterministic GitOps diffs.
    merged.sort(key=_quality_rule_sort_key)
    return merged or None


def _merge_custom_properties_models(existing: Any, imported: Any) -> list[CustomProperty] | None:
    merged_index: dict[str, CustomProperty] = {}
    unnamed: list[CustomProperty] = []

    for item in _normalize_custom_property_models(existing):
        item_key = _custom_property_key(item)
        if item_key:
            merged_index[item_key] = item.model_copy(deep=True)
        else:
            unnamed.append(item.model_copy(deep=True))

    for item in _normalize_custom_property_models(imported):
        item_key = _custom_property_key(item)
        if item_key:
            merged_index[item_key] = item.model_copy(deep=True)
        else:
            unnamed.append(item.model_copy(deep=True))

    merged = list(merged_index.values()) + unnamed
    merged.sort(key=_custom_property_sort_key)
    return merged or None


def _normalize_quality_models(rules: Any) -> list[DataQuality]:
    if not isinstance(rules, list):
        return []

    normalized: list[DataQuality] = []
    for rule in rules:
        if isinstance(rule, DataQuality):
            normalized.append(rule)
        elif isinstance(rule, dict):
            normalized.append(DataQuality.model_validate(deepcopy(rule)))
    return normalized


def _normalize_custom_property_models(items: Any) -> list[CustomProperty]:
    if not isinstance(items, list):
        return []

    normalized: list[CustomProperty] = []
    for item in items:
        if isinstance(item, CustomProperty):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append(CustomProperty.model_validate(deepcopy(item)))
    return normalized


def _normalize_custom_properties(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _custom_property_key(item: Any) -> str:
    return str(_object_value(item, "property") or "").strip().lower()


def _custom_property_sort_key(item: Any) -> str:
    return _custom_property_key(item)


def _to_odcs_model(contract: OpenDataContractStandard | dict[str, Any]) -> OpenDataContractStandard:
    # ContractMergeEngine is ODCS-only: always normalize to the canonical ODCS model.
    if isinstance(contract, OpenDataContractStandard):
        return contract.model_copy(deep=True)
    if isinstance(contract, dict):
        normalized = _normalize_odcs_input(contract)
        return OpenDataContractStandard.model_validate(normalized)
    raise TypeError("ContractMergeEngine only supports OpenDataContractStandard or ODCS dictionaries")


def _normalize_odcs_input(contract: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(contract)
    if "schema_" in normalized and "schema" not in normalized:
        normalized["schema"] = normalized.pop("schema_")

    description = normalized.get("description")
    if isinstance(description, str):
        normalized["description"] = {"usage": description}
    return normalized


def _object_value(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
