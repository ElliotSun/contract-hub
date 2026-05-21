from __future__ import annotations

from pathlib import Path

import pytest
from open_data_contract_standard.model import CustomProperty, SchemaProperty

from contracthub.core.release import (
    classify_contract_change,
    classify_version_bump,
    parse_release_tag_version,
    prepare_release_candidate,
    suggest_release_version,
)
from contracthub.utils.yaml_utils import dump_yaml


def test_release_classification_returns_none_for_description_only_change(
    sample_odcs_model,
):
    base = sample_odcs_model.model_copy(deep=True)
    candidate = sample_odcs_model.model_copy(deep=True)
    assert candidate.description is not None
    candidate.description.usage = "Updated descriptive text only"

    result = classify_contract_change(base, candidate)

    assert result.has_changes is True
    assert result.required_bump == "none"


def test_release_classification_returns_minor_for_added_property(sample_odcs_model):
    base = sample_odcs_model.model_copy(deep=True)
    candidate = sample_odcs_model.model_copy(deep=True)
    candidate.schema_[0].properties.append(  # type: ignore[index,union-attr]
        SchemaProperty(
            name="new_optional_column",
            logicalType="string",
            physicalType="STRING",
            required=False,
        )
    )

    result = classify_contract_change(base, candidate)

    assert result.required_bump == "minor"
    assert any("minor version bump" in reason for reason in result.reasons)


def test_release_classification_treats_deprecation_as_minor(sample_odcs_model):
    base = sample_odcs_model.model_copy(deep=True)
    candidate = sample_odcs_model.model_copy(deep=True)
    candidate.schema_[0].properties[0].customProperties = [  # type: ignore[index,union-attr]
        CustomProperty(property="lifecycleStatus", value="deprecated")
    ]

    result = classify_contract_change(base, candidate)

    assert result.required_bump == "minor"


def test_release_classification_returns_major_for_breaking_change(sample_odcs_model):
    base = sample_odcs_model.model_copy(deep=True)
    candidate = sample_odcs_model.model_copy(deep=True)
    candidate.schema_[0].properties[0].required = True  # type: ignore[index,union-attr]

    result = classify_contract_change(base, candidate)

    assert result.required_bump == "major"
    assert result.breaking_changes


def test_release_tag_helpers_parse_and_classify_versions():
    assert parse_release_tag_version("orders/v1.2.3") == "1.2.3"
    assert parse_release_tag_version("v2.0.0") == "2.0.0"
    assert classify_version_bump("1.0.0", "1.0.1") == "patch"
    assert classify_version_bump("1.0.0", "1.1.0") == "minor"
    assert classify_version_bump("1.0.0", "2.0.0") == "major"


def test_suggest_release_version_uses_last_released_version_not_unreleased_chain():
    assert suggest_release_version("1.2.0", "major") == "2.0.0"
    assert suggest_release_version("1.2.0", "minor") == "1.3.0"
    assert suggest_release_version("1.2.0", "none") == "1.2.0"


def test_prepare_release_candidate_applies_explicit_release_tag(sample_odcs_model):
    base = sample_odcs_model.model_copy(deep=True)
    candidate = sample_odcs_model.model_copy(deep=True)
    candidate.schema_[0].properties.append(  # type: ignore[index,union-attr]
        SchemaProperty(
            name="new_optional_column",
            logicalType="string",
            physicalType="STRING",
            required=False,
        )
    )

    result = prepare_release_candidate(base, candidate, "orders/v1.2.0")

    assert result.current_version == str(base.version)
    assert result.target_version == "1.2.0"
    assert result.actual_bump == "minor"
    assert result.contract.version == "1.2.0"
    assert result.contract.id == base.id


def test_prepare_release_candidate_rejects_insufficient_bump(sample_odcs_model):
    base = sample_odcs_model.model_copy(deep=True)
    candidate = sample_odcs_model.model_copy(deep=True)
    candidate.schema_[0].properties.append(  # type: ignore[index,union-attr]
        SchemaProperty(
            name="new_optional_column",
            logicalType="string",
            physicalType="STRING",
            required=False,
        )
    )

    with pytest.raises(ValueError, match="requires at least a minor bump"):
        prepare_release_candidate(base, candidate, "orders/v1.1.1")


def test_prepare_release_candidate_rejects_description_only_changes(sample_odcs_model):
    base = sample_odcs_model.model_copy(deep=True)
    candidate = sample_odcs_model.model_copy(deep=True)
    assert candidate.description is not None
    candidate.description.usage = "Updated descriptive text only"

    with pytest.raises(ValueError, match="do not require a release version bump"):
        prepare_release_candidate(base, candidate, "orders/v1.1.1")


def test_prepare_release_candidate_preserves_governed_identity(
    sample_odcs_model,
):
    base_contract = sample_odcs_model.model_copy(deep=True)
    candidate_contract = sample_odcs_model.model_copy(deep=True)
    candidate_contract.id = "tampered-id"
    candidate_contract.version = "999.0.0"
    candidate_contract.schema_[0].properties.append(  # type: ignore[index,union-attr]
        SchemaProperty(
            name="new_optional_column",
            logicalType="string",
            physicalType="STRING",
            required=False,
        )
    )

    # In a real workflow, if a user tampered with ID and version, `prepare_release_candidate`
    # handles setting the final ID back to base and overriding the version to the target
    # release tag version.
    # Because ID and version changed, `classify_contract_change` natively flags it as major.
    # `prepare_release_candidate` uses the assessment but resolves the ID/Version
    # so the final output has correct properties.
    assessment = classify_contract_change(base_contract, candidate_contract)
    assert assessment.required_bump == "major" # Changed ID and Version are breaking changes

    promotion = prepare_release_candidate(base_contract, candidate_contract, "orders/v1.2.0")

    # `prepare_release_candidate` evaluates the bump based on the contract after applying
    # the base ID and version constraints, making it a minor bump.
    assert promotion.required_bump == "minor"
    assert promotion.contract.id == base_contract.id
    assert promotion.contract.version == "1.2.0"
    assert promotion.current_version == str(base_contract.version)
