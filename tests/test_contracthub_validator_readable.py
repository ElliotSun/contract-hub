from __future__ import annotations

from types import SimpleNamespace

from open_data_contract_standard.model import SchemaProperty

from contracthub.core.validator import ContractValidator


def test_validator_accepts_full_sample_contract(sample_odcs_model):
    report = ContractValidator().validate(sample_odcs_model)

    assert report.valid is True
    assert report.issues == []


def test_validator_reports_missing_schema_on_empty_contract(sample_odcs_model):
    sample_odcs_model = sample_odcs_model.model_copy(deep=True)
    sample_odcs_model.schema_ = []

    report = ContractValidator().validate(sample_odcs_model)

    assert report.valid is False
    assert report.issues[0].path == "schema"


def test_validator_reports_missing_schema_name_and_properties(sample_odcs_model):
    sample_odcs_model = sample_odcs_model.model_copy(deep=True)
    assert sample_odcs_model.schema_ is not None
    sample_odcs_model.schema_[0].name = ""
    sample_odcs_model.schema_[0].properties = []

    report = ContractValidator().validate(sample_odcs_model)

    issue_paths = {issue.path for issue in report.issues}
    assert "schema[0].name" in issue_paths
    assert "schema[0].properties" in issue_paths


def test_validator_reports_property_without_name_or_type(sample_odcs_model):
    sample_odcs_model = sample_odcs_model.model_copy(deep=True)
    assert sample_odcs_model.schema_ is not None
    assert sample_odcs_model.schema_[0].properties is not None
    sample_odcs_model.schema_[0].properties.append(SchemaProperty())

    report = ContractValidator().validate(sample_odcs_model)

    issue_paths = {issue.path for issue in report.issues}
    assert "schema[0].properties[3].name" in issue_paths
    assert "schema[0].properties[3]" in issue_paths


def test_validator_reports_quality_rule_missing_metric_and_threshold():
    validator = ContractValidator()

    issues = validator._validate_quality_rules(  # noqa: SLF001
        "schema[0].quality",
        [None, SimpleNamespace(metric=None)],
    )

    issue_paths = {issue.path for issue in issues}
    assert "schema[0].quality[0]" in issue_paths
    assert "schema[0].quality[1].metric" in issue_paths
    assert "schema[0].quality[1]" in issue_paths
