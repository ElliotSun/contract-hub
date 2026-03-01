from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from open_data_contract_standard.model import OpenDataContractStandard

from contracthub.core.loader import ContractLoader
from contracthub.core.validator import ContractValidator, ValidationReport
from contracthub.devops.audit import AuditMetadata
from contracthub.importers.delta_importer import DeltaTableImporter
from contracthub.importers.sql_importer import SQLFolderImporter
from contracthub.importers.uc_importer import UnityCatalogImporter
from contracthub.lifecycle.merge_engine import ContractMergeEngine, MergeResult
from contracthub.lifecycle.policy import PolicyEvaluation, evaluate_merge_policy
from contracthub.quality.ge_exporter import GreatExpectationsExporter
from contracthub.utils.schema_utils import contract_to_dict, contract_to_model
from contracthub.utils.yaml_utils import dump_yaml

ImportSourceType = Literal["delta", "sql", "uc"]


@dataclass(slots=True)
class PipelineArtifacts:
    """Artifacts produced by a contract pipeline run."""

    merged_contract_path: Path
    ge_suite_path: Path
    ci_manifest_path: Path


@dataclass(slots=True)
class ContractPipeline:
    """Orchestrate ContractHub import, merge, export, and CI artifact generation."""

    runtime_context: str = "auto"
    loader: ContractLoader = field(init=False)
    validator: ContractValidator = field(init=False)
    merge_engine: ContractMergeEngine = field(init=False)
    ge_exporter: GreatExpectationsExporter = field(init=False)

    def __post_init__(self) -> None:
        self.loader = ContractLoader(runtime_context=self.runtime_context)
        self.validator = ContractValidator()
        self.merge_engine = ContractMergeEngine()
        self.ge_exporter = GreatExpectationsExporter()

    def import_schema(
        self,
        source_type: ImportSourceType,
        source: str,
        *,
        existing_contract: dict[str, Any] | None = None,
        uc_workspace_url: str | None = None,
        uc_token: str | None = None,
    ) -> OpenDataContractStandard:
        if source_type == "delta":
            contract_dict = DeltaTableImporter(source).import_contract(existing_contract=existing_contract)
            return contract_to_model(contract_dict)

        if source_type == "sql":
            contract_dict = SQLFolderImporter(source).import_contract(existing_contract=existing_contract)
            return contract_to_model(contract_dict)

        if source_type == "uc":
            if not uc_workspace_url or not uc_token:
                raise ValueError("uc_workspace_url and uc_token are required for uc source_type")
            return UnityCatalogImporter(workspace_url=uc_workspace_url, token=uc_token).import_contract(
                source,
                existing_contract=existing_contract,
            )

        raise ValueError(f"Unsupported source_type: {source_type}")

    def merge_contract_updates(
        self,
        imported_contract: OpenDataContractStandard,
        business_contract: OpenDataContractStandard,
        *,
        fail_on_conflict: bool = False,
    ) -> MergeResult:
        return self.merge_engine.merge(
            imported_contract,
            business_contract,
            fail_on_conflict=fail_on_conflict,
        )

    def validate_contract(self, contract: OpenDataContractStandard) -> ValidationReport:
        return self.validator.validate(contract)

    def evaluate_policy(
        self,
        base_contract: OpenDataContractStandard,
        merged_contract: OpenDataContractStandard,
    ) -> PolicyEvaluation:
        return evaluate_merge_policy(contract_to_dict(base_contract), contract_to_dict(merged_contract))

    def prepare_ci_cd_artifacts(
        self,
        merged_contract: OpenDataContractStandard,
        merge_result: MergeResult,
        validation: ValidationReport,
        policy_evaluation: PolicyEvaluation,
        *,
        merged_contract_output_path: str,
        ge_suite_output_path: str,
        ci_manifest_output_path: str,
        ge_schema_name: str = "all",
        ge_suite_name: str | None = None,
        audit_metadata: AuditMetadata | None = None,
    ) -> PipelineArtifacts:
        merged_contract_path = dump_yaml(contract_to_dict(merged_contract), merged_contract_output_path)
        ge_suite_path = self.ge_exporter.export_to_path(
            merged_contract,
            ge_suite_output_path,
            schema_name=ge_schema_name,
            suite_name=ge_suite_name,
        )

        ci_manifest_path = Path(ci_manifest_output_path).expanduser().resolve()
        ci_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "valid": validation.valid,
            "policyValid": policy_evaluation.valid,
            "issues": [asdict(issue) for issue in validation.issues],
            "breakingChanges": [asdict(change) for change in policy_evaluation.breaking_changes],
            "conflicts": [asdict(conflict) for conflict in merge_result.conflicts],
            "artifacts": {
                "mergedContract": str(merged_contract_path),
                "greatExpectationsSuite": str(ge_suite_path),
            },
            "audit": asdict(audit_metadata) if audit_metadata is not None else None,
        }
        ci_manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        return PipelineArtifacts(
            merged_contract_path=merged_contract_path,
            ge_suite_path=ge_suite_path,
            ci_manifest_path=ci_manifest_path,
        )

    def run(
        self,
        *,
        source_type: ImportSourceType,
        source: str,
        business_contract_path: str,
        merged_contract_output_path: str,
        ge_suite_output_path: str,
        ci_manifest_output_path: str,
        fail_on_conflict: bool = False,
        uc_workspace_url: str | None = None,
        uc_token: str | None = None,
        ge_schema_name: str = "all",
        ge_suite_name: str | None = None,
        audit_metadata: AuditMetadata | None = None,
    ) -> PipelineArtifacts:
        imported_contract = self.import_schema(
            source_type,
            source,
            uc_workspace_url=uc_workspace_url,
            uc_token=uc_token,
        )
        business_contract = self.loader.load(business_contract_path)

        merge_result = self.merge_contract_updates(
            imported_contract,
            business_contract,
            fail_on_conflict=fail_on_conflict,
        )

        validation = self.validate_contract(merge_result.contract)
        if not validation.valid:
            message = "; ".join(f"{item.path}: {item.message}" for item in validation.issues)
            raise ValueError(f"Merged contract validation failed: {message}")

        policy_evaluation = self.evaluate_policy(business_contract, merge_result.contract)
        if not policy_evaluation.valid:
            message = "; ".join(f"{item.path}: {item.message}" for item in policy_evaluation.breaking_changes)
            raise ValueError(f"Lifecycle policy validation failed: {message}")

        return self.prepare_ci_cd_artifacts(
            merge_result.contract,
            merge_result,
            validation,
            policy_evaluation,
            merged_contract_output_path=merged_contract_output_path,
            ge_suite_output_path=ge_suite_output_path,
            ci_manifest_output_path=ci_manifest_output_path,
            ge_schema_name=ge_schema_name,
            ge_suite_name=ge_suite_name,
            audit_metadata=audit_metadata,
        )
