from __future__ import annotations

import pytest

import contracthub.lifecycle.merge_engine as merge_engine
from contracthub.lifecycle.merge_engine import ContractMergeEngine


BASE_CONTRACT = {
    "apiVersion": "v3.1.0",
    "kind": "DataContract",
    "id": "orders",
    "name": "orders",
    "version": "1.0.0",
    "status": "active",
    "schema": [
        {
            "name": "orders",
            "physicalName": "orders",
            "properties": [
                {
                    "name": "id",
                    "physicalName": "id",
                    "logicalType": "integer",
                    "physicalType": "int",
                    "required": True,
                    "quality": [{"name": "id_not_null", "metric": "nullValues", "mustBe": 0}],
                },
                {
                    "name": "amount",
                    "physicalName": "amount",
                    "logicalType": "number",
                    "physicalType": "decimal(10,2)",
                },
            ],
            "quality": [{"name": "row_count", "metric": "rowCount", "mustBeGreaterThan": 0}],
        }
    ],
}

BUSINESS_CONTRACT = {
    "apiVersion": "v3.1.0",
    "kind": "DataContract",
    "id": "orders",
    "name": "orders",
    "version": "1.0.0",
    "status": "active",
    "schema": [
        {
            "name": "orders",
            "physicalName": "orders",
            "properties": [
                {
                    "name": "id",
                    "physicalName": "id",
                    "logicalType": "string",
                    "physicalType": "varchar(18)",
                    "required": False,
                    "quality": [{"name": "id_unique", "metric": "uniqueValues", "mustBe": "100%"}],
                },
                {
                    "name": "amount",
                    "physicalName": "amount",
                    "logicalType": "number",
                    "physicalType": "decimal(12,4)",
                },
            ],
            "quality": [{"name": "freshness", "metric": "freshness", "mustBeLessThan": 1}],
        }
    ],
}


def test_merge_engine_detects_type_required_and_decimal_conflicts():
    engine = ContractMergeEngine()

    conflicts = engine.detect_conflicts(BASE_CONTRACT, BUSINESS_CONTRACT)

    rules = {item.rule for item in conflicts}
    assert "logical_type_mismatch" in rules
    assert "physical_type_mismatch" in rules
    assert "required_tightening" in rules
    assert "decimal_reduction" in rules


def test_merge_engine_can_fail_fast_when_conflicts_exist():
    engine = ContractMergeEngine()

    with pytest.raises(ValueError, match="Merge conflicts detected"):
        engine.merge(BASE_CONTRACT, BUSINESS_CONTRACT, fail_on_conflict=True)


def test_merge_engine_combines_quality_rules_without_duplicates():
    engine = ContractMergeEngine()

    result = engine.merge(BASE_CONTRACT, BUSINESS_CONTRACT)

    merged_schema = result.contract.model_dump(by_alias=True, exclude_none=True)["schema"][0]
    schema_quality = merged_schema["quality"]
    id_property = next(prop for prop in merged_schema["properties"] if prop.get("name") == "id")
    id_quality = id_property["quality"]

    assert len(schema_quality) == 2
    assert len(id_quality) == 2


def test_merge_engine_helpers_cover_edge_cases_for_internal_functions():
    assert merge_engine._value_conflict("a", "b") is True  # noqa: SLF001
    assert merge_engine._value_conflict(None, "b") is False  # noqa: SLF001
    assert merge_engine._decimal_precision_scale("decimal(9,2)") == (9, 2)  # noqa: SLF001
    assert merge_engine._decimal_precision_scale("int") is None  # noqa: SLF001
    assert merge_engine._decimal_reduction("decimal(8,2)", "decimal(10,2)") is True  # noqa: SLF001
    assert merge_engine._decimal_reduction("decimal(12,4)", "decimal(10,2)") is False  # noqa: SLF001
