from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from datacontract.data_contract import DataContract
from open_data_contract_standard.model import OpenDataContractStandard
from contracthub.core.validator import ValidationIssue, ValidationReport
from contracthub.devops.audit import AuditMetadata
from contracthub.lifecycle.merge_engine import MergeConflict, MergeResult
from contracthub.lifecycle.policy import BreakingChange, PolicyEvaluation
from contracthub.orchestrator.pipeline import ContractPipeline


def test_pipeline_import_schema_supports_delta_and_sql(monkeypatch):
    def fake_import(format: str, source: str | None = None, **_kwargs):  # noqa: ANN001
        return OpenDataContractStandard.model_validate(
            {
                "apiVersion": "v3.1.0",
                "kind": "DataContract",
                "id": "from-importer",
                "name": source or "unknown",
                "version": "1.0.0",
                "status": "draft",
                "schema": [{"name": "t1", "properties": [{"name": "id", "logicalType": "string"}]}],
            }
        )

    monkeypatch.setattr(DataContract, "import_from_source", staticmethod(fake_import))

    pipeline = ContractPipeline()

    delta_contract = pipeline.import_schema("delta", "delta://orders")
    sql_contract = pipeline.import_schema("sql", "orders_folder")

    assert delta_contract.id == "from-importer"
    assert sql_contract.id == "from-importer"


def test_pipeline_import_schema_requires_uc_credentials():
    pipeline = ContractPipeline()

    with pytest.raises(ValueError, match="uc_workspace_url and uc_token"):
        pipeline.import_schema("uc", "main.silver.orders")


def test_pipeline_import_schema_supports_uc_when_credentials_are_given(monkeypatch):
    def fake_import(format: str, source: str | None = None, **_kwargs):  # noqa: ANN001
        return OpenDataContractStandard.model_validate(
            {
                "apiVersion": "v3.1.0",
                "kind": "DataContract",
                "id": "uc-id",
                "name": "orders",
                "version": "1.0.0",
                "status": "draft",
                "schema": [{"name": "t1", "properties": [{"name": "id", "logicalType": "string"}]}],
            }
        )

    monkeypatch.setattr(DataContract, "import_from_source", staticmethod(fake_import))
    pipeline = ContractPipeline()

    contract = pipeline.import_schema(
        "uc",
        "main.silver.orders",
        uc_workspace_url="https://adb.example",
        uc_token="token",
    )

    assert contract.id == "uc-id"


def test_pipeline_import_schema_rejects_unknown_source_type():
    pipeline = ContractPipeline()

    with pytest.raises(ValueError, match="Unsupported source_type"):
        pipeline.import_schema("unknown", "src")  # type: ignore[arg-type]


def test_pipeline_prepare_ci_cd_artifacts_writes_manifest_and_outputs(monkeypatch, tmp_path, sample_odcs_model):
    pipeline = ContractPipeline()
    merged_contract = sample_odcs_model
    merge_result = MergeResult(contract=merged_contract, conflicts=[MergeConflict("p", "r", 1, 2)])
    validation = ValidationReport(valid=True, issues=[])
    policy = PolicyEvaluation(valid=True, breaking_changes=[])
    audit = AuditMetadata(last_merge_ts="2026-02-24T00:00:00+00:00", last_merge_actor="tester", last_merge_source="sql")
    fake_suite_path = tmp_path / "suite.json"
    fake_suite_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "contracthub.orchestrator.pipeline.GreatExpectationsExporter.export_to_path",
        lambda self, *args, **kwargs: fake_suite_path,
    )

    artifacts = pipeline.prepare_ci_cd_artifacts(
        merged_contract,
        merge_result,
        validation,
        policy,
        merged_contract_output_path=str(tmp_path / "merged.yaml"),
        ge_suite_output_path=str(tmp_path / "suite.json"),
        ci_manifest_output_path=str(tmp_path / "manifest.json"),
        audit_metadata=audit,
    )

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert artifacts.merged_contract_path.exists()
    assert artifacts.ge_suite_path.exists()
    assert artifacts.ci_manifest_path.exists()
    assert manifest["valid"] is True
    assert manifest["policyValid"] is True
    assert manifest["audit"]["last_merge_actor"] == "tester"


def test_pipeline_run_raises_on_failed_contract_validation(monkeypatch, sample_odcs_model):
    pipeline = ContractPipeline()

    monkeypatch.setattr(ContractPipeline, "import_schema", lambda self, *args, **kwargs: sample_odcs_model)
    monkeypatch.setattr(type(pipeline.loader), "load", lambda self, _: sample_odcs_model)
    monkeypatch.setattr(
        ContractPipeline,
        "merge_contract_updates",
        lambda self, *args, **kwargs: MergeResult(contract=sample_odcs_model, conflicts=[]),
    )
    monkeypatch.setattr(
        ContractPipeline,
        "validate_contract",
        lambda self, _: ValidationReport(valid=False, issues=[ValidationIssue(path="schema", message="bad")]),
    )

    with pytest.raises(ValueError, match="Merged contract validation failed"):
        pipeline.run(
            source_type="sql",
            source="sql_folder",
            business_contract_path="sample_odcs.yaml",
            merged_contract_output_path="/tmp/merged.yaml",
            ge_suite_output_path="/tmp/suite.json",
            ci_manifest_output_path="/tmp/manifest.json",
        )


def test_pipeline_run_raises_on_failed_lifecycle_policy(monkeypatch, sample_odcs_model):
    pipeline = ContractPipeline()

    monkeypatch.setattr(ContractPipeline, "import_schema", lambda self, *args, **kwargs: sample_odcs_model)
    monkeypatch.setattr(type(pipeline.loader), "load", lambda self, _: sample_odcs_model)
    monkeypatch.setattr(
        ContractPipeline,
        "merge_contract_updates",
        lambda self, *args, **kwargs: MergeResult(contract=sample_odcs_model, conflicts=[]),
    )
    monkeypatch.setattr(ContractPipeline, "validate_contract", lambda self, _: ValidationReport(valid=True, issues=[]))
    monkeypatch.setattr(
        ContractPipeline,
        "evaluate_policy",
        lambda self, *args, **kwargs: SimpleNamespace(
            valid=False,
            version_violation=True,
            breaking_changes=[BreakingChange(path="schema[tbl]", message="removed")],
        ),
    )

    with pytest.raises(ValueError, match="Lifecycle policy validation failed"):
        pipeline.run(
            source_type="sql",
            source="sql_folder",
            business_contract_path="sample_odcs.yaml",
            merged_contract_output_path="/tmp/merged.yaml",
            ge_suite_output_path="/tmp/suite.json",
            ci_manifest_output_path="/tmp/manifest.json",
        )


def test_pipeline_run_does_not_block_non_version_policy_findings(monkeypatch, sample_odcs_model, tmp_path):
    pipeline = ContractPipeline()
    from contracthub.orchestrator.pipeline import PipelineArtifacts

    expected_artifacts = PipelineArtifacts(
        merged_contract_path=tmp_path / "merged.yaml",
        ge_suite_path=tmp_path / "suite.json",
        ci_manifest_path=tmp_path / "manifest.json",
    )

    monkeypatch.setattr(ContractPipeline, "import_schema", lambda self, *args, **kwargs: sample_odcs_model)
    monkeypatch.setattr(type(pipeline.loader), "load", lambda self, _: sample_odcs_model)
    monkeypatch.setattr(
        ContractPipeline,
        "merge_contract_updates",
        lambda self, *args, **kwargs: MergeResult(contract=sample_odcs_model, conflicts=[]),
    )
    monkeypatch.setattr(ContractPipeline, "validate_contract", lambda self, _: ValidationReport(valid=True, issues=[]))
    monkeypatch.setattr(
        ContractPipeline,
        "evaluate_policy",
        lambda self, *args, **kwargs: PolicyEvaluation(
            valid=False,
            breaking_changes=[BreakingChange(path="schema[tbl]", message="removed")],
        ),
    )
    monkeypatch.setattr(
        ContractPipeline,
        "prepare_ci_cd_artifacts",
        lambda self, *args, **kwargs: expected_artifacts,
    )

    artifacts = pipeline.run(
        source_type="sql",
        source="sql_folder",
        business_contract_path="sample_odcs.yaml",
        merged_contract_output_path=str(tmp_path / "merged2.yaml"),
        ge_suite_output_path=str(tmp_path / "suite2.json"),
        ci_manifest_output_path=str(tmp_path / "manifest2.json"),
    )

    assert artifacts == expected_artifacts


def test_pipeline_run_blocks_retired_contract(monkeypatch, sample_odcs_model):
    pipeline = ContractPipeline()
    retired_contract = sample_odcs_model.model_copy(deep=True)
    retired_contract.status = "retired"

    monkeypatch.setattr(ContractPipeline, "import_schema", lambda self, *args, **kwargs: sample_odcs_model)
    monkeypatch.setattr(type(pipeline.loader), "load", lambda self, _: retired_contract)

    with pytest.raises(ValueError, match="Cannot run pipeline on retired contract"):
        pipeline.run(
            source_type="sql",
            source="sql_folder",
            business_contract_path="sample_odcs.yaml",
            merged_contract_output_path="/tmp/merged.yaml",
            ge_suite_output_path="/tmp/suite.json",
            ci_manifest_output_path="/tmp/manifest.json",
        )


def test_pipeline_run_blocks_when_merge_returns_none_contract(monkeypatch, sample_odcs_model):
    pipeline = ContractPipeline()

    monkeypatch.setattr(ContractPipeline, "import_schema", lambda self, *args, **kwargs: sample_odcs_model)
    monkeypatch.setattr(type(pipeline.loader), "load", lambda self, _: sample_odcs_model)
    monkeypatch.setattr(
        ContractPipeline,
        "merge_contract_updates",
        lambda self, *args, **kwargs: SimpleNamespace(contract=None, conflicts=[]),
    )

    with pytest.raises(ValueError, match="Merge did not produce a contract"):
        pipeline.run(
            source_type="sql",
            source="sql_folder",
            business_contract_path="sample_odcs.yaml",
            merged_contract_output_path="/tmp/merged.yaml",
            ge_suite_output_path="/tmp/suite.json",
            ci_manifest_output_path="/tmp/manifest.json",
        )


def test_pipeline_run_blocks_on_conflicts_when_fail_on_conflict(monkeypatch, sample_odcs_model):
    pipeline = ContractPipeline()
    conflict = MergeConflict(schema_id="orders", property_name="id", message="type mismatch")

    monkeypatch.setattr(ContractPipeline, "import_schema", lambda self, *args, **kwargs: sample_odcs_model)
    monkeypatch.setattr(type(pipeline.loader), "load", lambda self, _: sample_odcs_model)
    monkeypatch.setattr(
        ContractPipeline,
        "merge_contract_updates",
        lambda self, *args, **kwargs: MergeResult(contract=sample_odcs_model, conflicts=[conflict]),
    )

    with pytest.raises(ValueError, match="Merge conflicts detected: orders.id: type mismatch"):
        pipeline.run(
            source_type="sql",
            source="sql_folder",
            business_contract_path="sample_odcs.yaml",
            merged_contract_output_path="/tmp/merged.yaml",
            ge_suite_output_path="/tmp/suite.json",
            ci_manifest_output_path="/tmp/manifest.json",
            fail_on_conflict=True,
        )


def test_pipeline_run_returns_artifacts_on_success(monkeypatch, sample_odcs_model, tmp_path):
    pipeline = ContractPipeline()
    from contracthub.orchestrator.pipeline import PipelineArtifacts

    expected_artifacts = PipelineArtifacts(
        merged_contract_path=tmp_path / "merged.yaml",
        ge_suite_path=tmp_path / "suite.json",
        ci_manifest_path=tmp_path / "manifest.json",
    )

    monkeypatch.setattr(ContractPipeline, "import_schema", lambda self, *args, **kwargs: sample_odcs_model)
    monkeypatch.setattr(type(pipeline.loader), "load", lambda self, _: sample_odcs_model)
    monkeypatch.setattr(
        ContractPipeline,
        "merge_contract_updates",
        lambda self, *args, **kwargs: MergeResult(contract=sample_odcs_model, conflicts=[]),
    )
    monkeypatch.setattr(ContractPipeline, "validate_contract", lambda self, _: ValidationReport(valid=True, issues=[]))
    monkeypatch.setattr(
        ContractPipeline,
        "evaluate_policy",
        lambda self, *args, **kwargs: PolicyEvaluation(valid=True, breaking_changes=[]),
    )
    monkeypatch.setattr(
        ContractPipeline,
        "prepare_ci_cd_artifacts",
        lambda self, *args, **kwargs: expected_artifacts,
    )

    artifacts = pipeline.run(
        source_type="sql",
        source="sql_folder",
        business_contract_path="sample_odcs.yaml",
        merged_contract_output_path=str(tmp_path / "merged2.yaml"),
        ge_suite_output_path=str(tmp_path / "suite2.json"),
        ci_manifest_output_path=str(tmp_path / "manifest2.json"),
    )

    assert artifacts == expected_artifacts
