"""Thin governance wrapper for UI-facing analyze/apply flows.

This module exists so the UI can call governance operations without depending
directly on lifecycle implementation details.

Service boundary intent:
- accept ODCS YAML text from the caller
- normalize that YAML into the canonical ODCS model
- delegate analyze/apply operations to the lifecycle merge engine
- return merge engine results directly

What this module must not do:
- enforce UI permissions
- implement merge or lifecycle policy logic
- reshape outputs for presentation concerns
- depend on Streamlit or session state
"""

from __future__ import annotations

from open_data_contract_standard.model import OpenDataContractStandard

from contracthub.lifecycle.merge_engine import ContractMergeEngine, MergeAnalysis, MergeResult


_MERGE_ENGINE = ContractMergeEngine()


def analyze(source_yaml: str, target_yaml: str) -> MergeAnalysis:
    """Delegate governance analysis to the merge engine.

    Inputs are raw ODCS YAML strings so the service boundary stays simple for
    UI callers. The result is the merge engine's native `MergeAnalysis`.
    """
    return _MERGE_ENGINE.analyze(
        base_contract=_to_odcs_model(source_yaml),
        business_contract=_to_odcs_model(target_yaml),
    )


def apply(source_yaml: str, target_yaml: str) -> MergeResult:
    """Delegate governance apply to the merge engine.

    This applies the lifecycle-aware merge using the merge engine's native
    contract/result types without adding UI-specific behavior.
    """
    return _MERGE_ENGINE.merge(
        base_contract=_to_odcs_model(source_yaml),
        business_contract=_to_odcs_model(target_yaml),
    )


def _to_odcs_model(contract_yaml: str) -> OpenDataContractStandard:
    """Parse ODCS YAML into the canonical contract model."""
    try:
        return OpenDataContractStandard.from_string(contract_yaml)
    except TypeError as exc:
        raise ValueError("Contract YAML must deserialize into a mapping object") from exc
