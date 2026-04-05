from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from contracthub.core.release import PromotionResult, prepare_release_candidate
from contracthub.devops.pr_creator import AzureDevOpsConfig, PullRequestCreator
from contracthub.utils.schema_utils import contract_to_model
from contracthub.utils.yaml_utils import dump_yaml


@dataclass(slots=True)
class ReleasePullRequestPlan:
    """Prepared per-contract release PR payload."""

    contract_id: str
    current_version: str
    target_version: str
    required_bump: str
    actual_bump: str
    release_tag: str
    contract_repo_path: str
    source_branch: str
    target_branch: str
    commit_message: str
    title: str
    description: str


def build_release_pr_plan(
    *,
    promotion: PromotionResult,
    contract_repo_path: str,
    source_branch: str,
    target_branch: str,
    title: str | None = None,
    description: str | None = None,
    commit_message: str | None = None,
) -> ReleasePullRequestPlan:
    """Build a per-contract release PR plan from a prepared promotion result."""
    contract_id = str(promotion.contract.id or "")
    target_version = promotion.target_version
    default_title = f"Release {contract_id} {target_version}"
    default_commit = f"release({contract_id}): prepare {target_version}"
    default_description = (
        f"Prepare release for contract `{contract_id}`.\n\n"
        f"- current version: `{promotion.current_version}`\n"
        f"- target version: `{promotion.target_version}`\n"
        f"- required bump: `{promotion.required_bump}`\n"
        f"- actual bump: `{promotion.actual_bump}`\n"
        f"- release tag: `{promotion.release_tag}`\n"
    )
    return ReleasePullRequestPlan(
        contract_id=contract_id,
        current_version=promotion.current_version,
        target_version=target_version,
        required_bump=promotion.required_bump,
        actual_bump=promotion.actual_bump,
        release_tag=promotion.release_tag,
        contract_repo_path=contract_repo_path,
        source_branch=source_branch,
        target_branch=target_branch,
        commit_message=commit_message or default_commit,
        title=title or default_title,
        description=description or default_description,
    )


def create_release_pull_request(
    *,
    config: AzureDevOpsConfig,
    repo_path: str,
    contract_repo_path: str,
    base_contract: Any,
    candidate_contract: Any,
    release_tag: str,
    source_branch: str,
    target_branch: str,
    title: str | None = None,
    description: str | None = None,
    commit_message: str | None = None,
    push: bool = False,
) -> dict[str, Any]:
    """Prepare one promoted contract and open a release PR for it."""
    promotion = prepare_release_candidate(base_contract, candidate_contract, release_tag)
    repo_root = Path(repo_path).expanduser().resolve()
    contract_path = repo_root / contract_repo_path
    dump_yaml(promotion.contract, contract_path)

    plan = build_release_pr_plan(
        promotion=promotion,
        contract_repo_path=contract_repo_path,
        source_branch=source_branch,
        target_branch=target_branch,
        title=title,
        description=description,
        commit_message=commit_message,
    )

    creator = PullRequestCreator(config=config)
    pr_payload = creator.create_update_pr(
        repo_path=str(repo_root),
        source_branch=source_branch,
        target_branch=target_branch,
        commit_message=plan.commit_message,
        title=plan.title,
        description=plan.description,
        paths=[contract_repo_path],
        push=push,
    )
    return {
        "promotion": {
            "contractId": plan.contract_id,
            "currentVersion": plan.current_version,
            "targetVersion": plan.target_version,
            "requiredBump": plan.required_bump,
            "actualBump": plan.actual_bump,
            "releaseTag": plan.release_tag,
            "contractPath": plan.contract_repo_path,
            "sourceBranch": plan.source_branch,
            "targetBranch": plan.target_branch,
        },
        "pullRequest": pr_payload,
    }


def release_plan_to_dict(plan: ReleasePullRequestPlan) -> dict[str, Any]:
    """Serialize a release PR plan for CLI/JSON output."""
    return asdict(plan)
