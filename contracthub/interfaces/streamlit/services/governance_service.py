"""Streamlit governance service wrappers for lifecycle merge operations."""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass, field
from typing import Any

import yaml
from open_data_contract_standard.model import OpenDataContractStandard

from contracthub.lifecycle.merge_engine import ContractMergeEngine, MergeAnalysis, MergeResult


@dataclass(slots=True)
class GovernanceService:
    """Parse YAML inputs and delegate lifecycle operations to the merge engine."""

    merge_engine: ContractMergeEngine = field(default_factory=ContractMergeEngine)

    def analyze(self, source_yaml: str, target_yaml: str) -> dict[str, Any]:
        """Return UI-friendly analysis results for the provided source and target contracts."""
        source_contract = _parse_contract_yaml(source_yaml)
        target_contract = _parse_contract_yaml(target_yaml)
        analysis = self.merge_engine._analyze_merge(  # noqa: SLF001
            target_model=target_contract,
            source_model=source_contract,
        )
        return _serialize_analysis(analysis)

    def apply(self, source_yaml: str, target_yaml: str) -> dict[str, Any]:
        """Merge source technical updates into the target governance contract."""
        source_contract = _parse_contract_yaml(source_yaml)
        target_contract = _parse_contract_yaml(target_yaml)
        merge_result = self.merge_engine.merge(
            base_contract=source_contract,
            business_contract=target_contract,
        )
        return _serialize_merge_result(merge_result)


def analyze(source_yaml: str, target_yaml: str) -> dict[str, Any]:
    """Convenience wrapper for conflict analysis."""
    return GovernanceService().analyze(source_yaml=source_yaml, target_yaml=target_yaml)


def apply(source_yaml: str, target_yaml: str) -> dict[str, Any]:
    """Convenience wrapper for merge application."""
    return GovernanceService().apply(source_yaml=source_yaml, target_yaml=target_yaml)


def _parse_contract_yaml(contract_yaml: str) -> OpenDataContractStandard:
    """Deserialize YAML text into the ODCS model used across ContractHub."""
    payload = yaml.safe_load(contract_yaml)
    if not isinstance(payload, dict):
        raise ValueError("Contract YAML must deserialize into a mapping object")
    return OpenDataContractStandard.model_validate(payload)


def _serialize_analysis(analysis: MergeAnalysis) -> dict[str, Any]:
    """Convert merge analysis output into a JSON-friendly structure for the UI."""
    conflicts = [asdict(conflict) for conflict in analysis.conflicts]
    deprecated_schemas = sorted(analysis.deprecated_schemas)
    deprecated_properties = {
        schema_id: sorted(property_ids)
        for schema_id, property_ids in sorted(analysis.deprecated_properties.items())
    }
    return {
        "allowed": not conflicts,
        "conflicts": conflicts,
        "deprecated_schemas": deprecated_schemas,
        "deprecated_properties": deprecated_properties,
    }


def _serialize_merge_result(merge_result: MergeResult) -> dict[str, Any]:
    """Convert a merge result into UI-friendly fields."""
    contract = merge_result.contract
    version = None
    if contract.info is not None:
        version = contract.info.version

    contract_yaml = yaml.safe_dump(
        contract.model_dump(by_alias=True, exclude_none=True),
        sort_keys=False,
        allow_unicode=False,
    )
    return {
        "new_version": version,
        "merged_contract_yaml": contract_yaml,
        "conflicts": [asdict(conflict) for conflict in merge_result.conflicts],
    }
