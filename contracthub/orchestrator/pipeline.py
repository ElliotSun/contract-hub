from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
import os
from pathlib import Path
from typing import Any, Literal

from open_data_contract_standard.model import OpenDataContractStandard

from datacontract.data_contract import DataContract

import contracthub.importers  # ensure custom importers are registered
from contracthub.core.loader import ContractLoader
from contracthub.core.validator import ContractValidator, ValidationReport
from contracthub.devops.audit import AuditMetadata
from contracthub.lifecycle.merge_engine import ContractMergeEngine, MergeResult
from contracthub.lifecycle.policy import PolicyEvaluation, evaluate_merge_policy
from contracthub.quality.ge_exporter import GreatExpectationsExporter
from contracthub.utils.schema_utils import contract_to_dict
from contracthub.utils.yaml_utils import dump_yaml

ImportSourceType = str


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
        existing_contract: OpenDataContractStandard | None = None,
        uc_workspace_url: str | None = None,
        uc_token: str | None = None,
        import_args: dict[str, Any] | None = None,
    ) -> OpenDataContractStandard:
        import_args = import_args or {}
        normalized = source_type.strip().lower()

        if normalized in {"uc", "unity"}:
            return _import_unity_contract(
                table_fqn=source,
                workspace_url=uc_workspace_url,
                token=uc_token,
            )

        try:
            imported = DataContract.import_from_source(
                format=normalized,
                source=source,
                **import_args,
            )
        except ValueError as exc:
            raise ValueError(f"Unsupported source_type: {source_type}") from exc

        if existing_contract is not None:
            return self.merge_engine.merge(
                imported,
                existing_contract,
            ).contract

        return imported

    def merge_contract_updates(
        self,
        imported_contract: OpenDataContractStandard,
        business_contract: OpenDataContractStandard,
        *,
        fail_on_conflict: bool = False,
    ) -> MergeResult:
        # `business_contract` is the lifecycle-governed target contract in Git.
        target_contract = business_contract
        return self.merge_engine.merge(
            imported_contract,
            target_contract,
            fail_on_conflict=fail_on_conflict,
        )

    def validate_contract(self, contract: OpenDataContractStandard) -> ValidationReport:
        return self.validator.validate(contract)

    def evaluate_policy(
        self,
        base_contract: OpenDataContractStandard,
        merged_contract: OpenDataContractStandard,
    ) -> PolicyEvaluation:
        return evaluate_merge_policy(base_contract, merged_contract)

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
        if self._resolve_lifecycle(business_contract) == "retired":
            raise ValueError("Cannot run pipeline on retired contract")

        merge_result = self.merge_contract_updates(
            imported_contract,
            business_contract,
            fail_on_conflict=fail_on_conflict,
        )
        if merge_result.conflicts and fail_on_conflict:
            message = "; ".join(
                f"{c.schema_id}.{c.property_name}: {c.message}"
                for c in merge_result.conflicts
            )
            raise ValueError(f"Merge conflicts detected: {message}")
        if merge_result.contract is None:
            raise ValueError("Merge did not produce a contract")

        validation = self.validate_contract(merge_result.contract)
        if not validation.valid:
            message = "; ".join(f"{item.path}: {item.message}" for item in validation.issues)
            raise ValueError(f"Merged contract validation failed: {message}")

        policy_evaluation = self.evaluate_policy(business_contract, merge_result.contract)
        version_violation = getattr(policy_evaluation, "version_violation", None)
        if version_violation is None:
            version_violation = any(
                getattr(change, "requires_version_bump", False) for change in policy_evaluation.breaking_changes
            )
        if not policy_evaluation.valid and version_violation:
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

    def _resolve_lifecycle(self, contract: OpenDataContractStandard) -> str:
        value = (contract.status or "").strip().lower()
        if value:
            return value
        for item in contract.customProperties or []:
            key = (item.property or "").strip().lower()
            if key != "lifecyclestatus":
                continue
            resolved = (str(item.value) if item.value is not None else "").strip().lower()
            return resolved or "draft"
        return "draft"


def _import_unity_contract(
    *,
    table_fqn: str,
    workspace_url: str | None,
    token: str | None,
) -> OpenDataContractStandard:
    if not workspace_url or not token:
        raise ValueError("uc_workspace_url and uc_token are required for uc source_type")

    env_backup = {
        "DATACONTRACT_DATABRICKS_SERVER_HOSTNAME": os.environ.get("DATACONTRACT_DATABRICKS_SERVER_HOSTNAME"),
        "DATACONTRACT_DATABRICKS_TOKEN": os.environ.get("DATACONTRACT_DATABRICKS_TOKEN"),
    }
    os.environ["DATACONTRACT_DATABRICKS_SERVER_HOSTNAME"] = workspace_url
    os.environ["DATACONTRACT_DATABRICKS_TOKEN"] = token
    try:
        return DataContract.import_from_source(
            format="unity",
            source=None,
            unity_table_full_name=[table_fqn],
        )
    finally:
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
