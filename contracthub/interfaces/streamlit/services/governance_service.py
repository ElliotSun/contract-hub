"""Thin governance wrapper for UI-facing analyze/apply flows.

This module exists so the UI can call governance operations without depending
directly on lifecycle implementation details.

Service boundary intent:
- accept ODCS contract inputs from the caller
- normalize those inputs into the canonical ODCS model
- delegate analyze/apply operations to the lifecycle merge engine
- return merge engine results directly

What this module must not do:
- enforce UI permissions
- implement merge or lifecycle policy logic
- reshape outputs for presentation concerns
- depend on Streamlit or session state
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from open_data_contract_standard.model import OpenDataContractStandard

from contracthub.lifecycle.merge_engine import (
    ContractMergeEngine,
    MergeAnalysis,
    MergeResult,
)
from contracthub.utils.schema_utils import contract_to_model


ContractInput = OpenDataContractStandard | dict[str, Any] | str | Path

_MERGE_ENGINE = ContractMergeEngine()


def analyze(source_yaml: str, target_yaml: str) -> MergeAnalysis:
    """Analyze two raw ODCS YAML payloads.

    This YAML-based entrypoint is kept for compatibility with callers that
    still hold raw contract text.
    """
    return analyze_contracts(_to_odcs_model(source_yaml), _to_odcs_model(target_yaml))


def apply(source_yaml: str, target_yaml: str) -> MergeResult:
    """Apply merge to two raw ODCS YAML payloads.

    This YAML-based entrypoint is kept for compatibility with callers that
    still hold raw contract text.
    """
    return apply_contracts(_to_odcs_model(source_yaml), _to_odcs_model(target_yaml))


def analyze_contracts(
    source_contract: ContractInput, target_contract: ContractInput
) -> MergeAnalysis:
    """Analyze two contracts after normalizing them into ODCS models."""
    return _MERGE_ENGINE.analyze(
        base_contract=contract_to_model(source_contract),
        business_contract=contract_to_model(target_contract),
    )


def apply_contracts(
    source_contract: ContractInput, target_contract: ContractInput
) -> MergeResult:
    """Apply lifecycle-aware merge after normalizing inputs into ODCS models."""
    return _MERGE_ENGINE.merge(
        base_contract=contract_to_model(source_contract),
        business_contract=contract_to_model(target_contract),
    )


def _to_odcs_model(contract_yaml: str) -> OpenDataContractStandard:
    """Parse ODCS YAML into the canonical contract model."""
    try:
        return OpenDataContractStandard.from_string(contract_yaml)
    except TypeError as exc:
        raise ValueError(
            "Contract YAML must deserialize into a mapping object"
        ) from exc
