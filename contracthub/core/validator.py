from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
from pathlib import Path

from open_data_contract_standard.model import OpenDataContractStandard, SchemaObject, SchemaProperty

from contracthub.utils.schema_utils import contract_to_model


@dataclass(slots=True)
class ValidationIssue:
    """Represents a contract validation issue."""

    path: str
    message: str
    severity: str = "error"


@dataclass(slots=True)
class ValidationReport:
    """Validation result envelope."""

    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass(slots=True)
class ContractValidator:
    """Validate ODCS schema structure and quality rule completeness."""

    def validate(self, contract_input: OpenDataContractStandard | str | Path) -> ValidationReport:
        contract = contract_to_model(contract_input)
        issues: list[ValidationIssue] = []

        if not contract.schema_:
            issues.append(ValidationIssue(path="schema", message="Contract must define at least one schema object"))
            return ValidationReport(valid=False, issues=issues)

        for schema_idx, schema_obj in enumerate(contract.schema_):
            issues.extend(self._validate_schema_object(schema_idx, schema_obj))

        return ValidationReport(valid=not issues, issues=issues)

    def _validate_schema_object(self, schema_idx: int, schema_obj: SchemaObject) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        path = f"schema[{schema_idx}]"

        if not schema_obj.name:
            issues.append(ValidationIssue(path=f"{path}.name", message="Schema object name is required"))

        if not schema_obj.properties:
            issues.append(ValidationIssue(path=f"{path}.properties", message="Schema object must define properties"))
            return issues

        for prop_idx, prop in enumerate(schema_obj.properties):
            issues.extend(self._validate_property(f"{path}.properties[{prop_idx}]", prop))

        if schema_obj.quality:
            issues.extend(self._validate_quality_rules(f"{path}.quality", schema_obj.quality))

        return issues

    def _validate_property(self, path: str, prop: SchemaProperty) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if not prop.name:
            issues.append(ValidationIssue(path=f"{path}.name", message="Property name is required"))

        if not (prop.logicalType or prop.physicalType):
            issues.append(
                ValidationIssue(
                    path=path,
                    message="Property must define logicalType or physicalType",
                )
            )

        if prop.quality:
            issues.extend(self._validate_quality_rules(f"{path}.quality", prop.quality))

        if prop.properties:
            for idx, nested_prop in enumerate(prop.properties):
                issues.extend(self._validate_property(f"{path}.properties[{idx}]", nested_prop))

        if prop.items:
            issues.extend(self._validate_property(f"{path}.items", prop.items))

        return issues

    def _validate_quality_rules(self, path: str, rules: Iterable[Any]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        threshold_keys = {
            "mustBe",
            "mustNotBe",
            "mustBeGreaterThan",
            "mustBeGreaterOrEqualTo",
            "mustBeLessThan",
            "mustBeLessOrEqualTo",
            "mustBeBetween",
            "mustNotBeBetween",
            "rule",
            "query",
            "implementation",
        }

        for idx, rule in enumerate(rules):
            if rule is None:
                issues.append(ValidationIssue(path=f"{path}[{idx}]", message="Quality rule must not be null"))
                continue

            metric = getattr(rule, "metric", None)
            if not metric:
                issues.append(ValidationIssue(path=f"{path}[{idx}].metric", message="Quality rule metric is required"))

            has_threshold = any(getattr(rule, key, None) is not None for key in threshold_keys)
            if not has_threshold:
                issues.append(
                    ValidationIssue(
                        path=f"{path}[{idx}]",
                        message="Quality rule must include at least one assertion threshold or implementation",
                    )
                )

        return issues
