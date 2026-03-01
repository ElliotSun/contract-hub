from __future__ import annotations

from copy import deepcopy

from contracthub.lifecycle.helpers import allows_breaking_changes, is_active_contract, normalize_status, schema_items
from contracthub.lifecycle.policy import evaluate_merge_policy


def test_policy_skips_breaking_checks_for_non_active_contract(sample_odcs_dict):
    base = deepcopy(sample_odcs_dict)
    base["status"] = "draft"
    merged = {"schema": []}

    evaluation = evaluate_merge_policy(base, merged)

    assert evaluation.valid is True
    assert evaluation.breaking_changes == []


def test_policy_flags_removed_schema_in_active_contract(sample_odcs_dict):
    base = deepcopy(sample_odcs_dict)
    merged = deepcopy(sample_odcs_dict)
    merged["schema"] = merged["schema"][1:]

    evaluation = evaluate_merge_policy(base, merged)

    assert evaluation.valid is False
    assert any("Schema removed" in item.message for item in evaluation.breaking_changes)


def test_policy_flags_removed_property_in_active_contract(sample_odcs_dict):
    base = deepcopy(sample_odcs_dict)
    merged = deepcopy(sample_odcs_dict)
    merged["schema"][0]["properties"] = merged["schema"][0]["properties"][1:]

    evaluation = evaluate_merge_policy(base, merged)

    assert evaluation.valid is False
    assert any("Property removed" in item.message for item in evaluation.breaking_changes)


def test_policy_ignores_removed_property_when_lifecycle_is_draft(sample_odcs_dict):
    base = deepcopy(sample_odcs_dict)
    base["schema"][0]["properties"][0]["lifecycleStatus"] = "draft"
    merged = deepcopy(sample_odcs_dict)
    merged["schema"][0]["properties"] = merged["schema"][0]["properties"][1:]

    evaluation = evaluate_merge_policy(base, merged)

    assert evaluation.valid is True
    assert evaluation.breaking_changes == []


def test_lifecycle_helpers_cover_status_and_schema_alias_paths(sample_odcs_dict):
    assert normalize_status(" ACTIVE ") == "active"
    assert normalize_status(None, default="x") == "x"
    assert is_active_contract({"status": "active"}) is True
    assert is_active_contract({"status": "deprecated"}) is False
    assert allows_breaking_changes({"lifecycleStatus": "active"}) is True
    assert allows_breaking_changes({"lifecycleStatus": "deprecated"}) is False
    assert schema_items(sample_odcs_dict)
    assert schema_items({"schema_": [{"name": "alias_table"}, "x"]}) == [{"name": "alias_table"}]
