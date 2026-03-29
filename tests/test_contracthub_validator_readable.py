from __future__ import annotations

from open_data_contract_standard.model import DataQuality, SchemaProperty

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
        [None, DataQuality()],
    )

    issue_paths = {issue.path for issue in issues}
    assert "schema[0].quality[0]" in issue_paths
    assert "schema[0].quality[1].metric" in issue_paths


def test_validator_accepts_custom_ge_quality_rule_without_metric():
    validator = ContractValidator()

    issues = validator._validate_quality_rules(  # noqa: SLF001
        "schema[0].quality",
        [
            DataQuality(
                type="custom",
                engine="greatExpectations",
                implementation="type: expect_table_row_count_to_be_between",
            )
        ],
    )

    assert issues == []


def test_validator_reports_sql_quality_rule_missing_query_or_comparison():
    validator = ContractValidator()

    issues = validator._validate_quality_rules(  # noqa: SLF001
        "schema[0].quality",
        [DataQuality(type="sql")],
    )

    issue_paths = {issue.path for issue in issues}
    assert "schema[0].quality[0].query" in issue_paths
    assert "schema[0].quality[0]" in issue_paths


def test_validator_reports_invalid_values_rule_missing_arguments():
    validator = ContractValidator()

    issues = validator._validate_quality_rules(  # noqa: SLF001
        "schema[0].properties[0].quality",
        [DataQuality(metric="invalidValues", mustBe=0)],
    )

    assert issues[0].path == "schema[0].properties[0].quality[0].arguments"


def test_validator_reports_schema_duplicate_values_without_properties_argument():
    validator = ContractValidator()

    issues = validator._validate_quality_rules(  # noqa: SLF001
        "schema[0].quality",
        [DataQuality(metric="duplicateValues", mustBe=0, arguments={})],
    )

    assert issues[0].path == "schema[0].quality[0].arguments.properties"


def test_validator_treats_metric_without_type_as_library_rule():
    validator = ContractValidator()

    issues = validator._validate_quality_rules(  # noqa: SLF001
        "schema[0].properties[0].quality",
        [DataQuality(metric="nullValues", mustBe=0)],
    )

    assert issues == []
