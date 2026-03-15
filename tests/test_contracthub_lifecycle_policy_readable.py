from __future__ import annotations

from open_data_contract_standard.model import CustomProperty

from contracthub.lifecycle.helpers import allows_breaking_changes, is_active_contract, normalize_status, schema_items
from contracthub.lifecycle.policy import evaluate_merge_policy


def test_policy_skips_breaking_checks_for_non_active_contract(sample_odcs_model):
    base = sample_odcs_model.model_copy(deep=True)
    base.status = "draft"
    merged = base.model_copy(deep=True)
    merged.schema_ = []

    evaluation = evaluate_merge_policy(base, merged)

    assert evaluation.valid is True
    assert evaluation.breaking_changes == []


def test_policy_flags_removed_schema_in_active_contract(sample_odcs_model):
    base = sample_odcs_model.model_copy(deep=True)
    merged = sample_odcs_model.model_copy(deep=True)
    merged.schema_ = (merged.schema_ or [])[1:]

    evaluation = evaluate_merge_policy(base, merged)

    assert evaluation.valid is False
    assert any("Schema removed" in item.message for item in evaluation.breaking_changes)


def test_policy_flags_removed_property_in_active_contract(sample_odcs_model):
    base = sample_odcs_model.model_copy(deep=True)
    merged = sample_odcs_model.model_copy(deep=True)
    assert merged.schema_ is not None
    merged.schema_[0].properties = (merged.schema_[0].properties or [])[1:]

    evaluation = evaluate_merge_policy(base, merged)

    assert evaluation.valid is False
    assert any("Property removed" in item.message for item in evaluation.breaking_changes)


def test_policy_ignores_removed_property_when_lifecycle_is_draft(sample_odcs_model):
    base = sample_odcs_model.model_copy(deep=True)
    merged = sample_odcs_model.model_copy(deep=True)
    assert base.schema_ is not None
    assert base.schema_[0].properties is not None
    base.schema_[0].properties[0].customProperties = [
        CustomProperty(property="lifecycleStatus", value="draft"),
    ]
    assert merged.schema_ is not None
    merged.schema_[0].properties = (merged.schema_[0].properties or [])[1:]

    evaluation = evaluate_merge_policy(base, merged)

    assert evaluation.valid is True
    assert evaluation.breaking_changes == []


def test_lifecycle_helpers_cover_status_and_schema_alias_paths(sample_odcs_model, sample_odcs_dict):
    assert normalize_status(" ACTIVE ") == "active"
    assert normalize_status(None, default="x") == "x"
    active_contract = sample_odcs_model.model_copy(deep=True)
    active_contract.status = "active"
    assert is_active_contract(active_contract) is True
    inactive_contract = sample_odcs_model.model_copy(deep=True)
    inactive_contract.status = "deprecated"
    assert is_active_contract(inactive_contract) is False
    from types import SimpleNamespace

    assert allows_breaking_changes(SimpleNamespace(lifecycleStatus="active")) is True
    assert allows_breaking_changes(SimpleNamespace(lifecycleStatus="deprecated")) is False
    assert schema_items(sample_odcs_model)
