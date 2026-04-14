from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
from typing import Any

from open_data_contract_standard.model import OpenDataContractStandard
from contracthub.core.loader import ContractLoader
from contracthub.core.release import classify_contract_change, prepare_release_candidate, suggest_release_version
from datacontract.data_contract import DataContract
from contracthub.devops.pr_creator import AzureDevOpsConfig, GitHubConfig, PullRequestCreator, GitProviderConfig
from contracthub.devops.release_workflow import (
    batch_manifest_build_to_dict,
    batch_task_to_dict,
    build_batch_release_manifest,
    build_release_pr_plan,
    classify_contracts_in_repo,
    create_release_pull_request,
    create_release_pull_requests_from_manifest,
    load_batch_release_tasks,
    release_plan_to_dict,
    repository_change_to_dict,
)
import contracthub.importers  # ensure custom importers are registered
from contracthub.lifecycle.merge_engine import ContractMergeEngine
from contracthub.quality.ge_exporter import GreatExpectationsExporter
from contracthub.utils.schema_utils import contract_to_dict
from contracthub.utils.yaml_utils import dump_yaml

DEFAULT_AZURE_STORAGE_SCOPE = "https://storage.azure.com/.default"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contracthub")
    subparsers = parser.add_subparsers(dest="command", required=True)



    setup_parser = subparsers.add_parser("setup", help="Bootstrap repository with GitOps templates and CI pipelines")

    plan_parser = subparsers.add_parser("plan", help="Dry run and summarize changes between source and base contract")
    plan_parser.add_argument("--source", required=True)
    plan_parser.add_argument("--base", required=True)
    plan_parser.add_argument("--type", choices=["delta", "sql", "sql-folder", "uc", "unity"], required=True)
    plan_parser.add_argument("--tables")
    plan_parser.add_argument("--workspace-url")
    plan_parser.add_argument("--token")

    import_parser = subparsers.add_parser("import", help="Import contract from source")
    import_parser.add_argument("--type", choices=["delta", "sql", "sql-folder", "uc", "unity"], required=True)
    import_parser.add_argument("--source", required=True)
    import_parser.add_argument("--output", required=True)
    import_parser.add_argument("--existing")
    import_parser.add_argument("--runtime-context", default="auto")
    import_parser.add_argument("--workspace-url")
    import_parser.add_argument("--token")
    import_parser.add_argument("--adls-oauth-token", help="OAuth bearer token for ADLS Gen2 access")
    import_parser.add_argument(
        "--use-azure-identity",
        action="store_true",
        help="Fetch ADLS OAuth token via azure-identity DefaultAzureCredential",
    )
    import_parser.add_argument(
        "--azure-scope",
        default=DEFAULT_AZURE_STORAGE_SCOPE,
        help=f"Azure scope for token acquisition (default: {DEFAULT_AZURE_STORAGE_SCOPE})",
    )
    import_parser.add_argument(
        "--tables",
        help="Comma-separated list of additional Delta table URIs (used with --type delta)",
    )

    merge_parser = subparsers.add_parser("merge", help="Merge base and business-edited contracts")
    merge_parser.add_argument("--base", required=True)
    merge_parser.add_argument("--business", required=True)
    merge_parser.add_argument("--output", required=True)
    merge_parser.add_argument("--runtime-context", default="auto")
    merge_parser.add_argument("--fail-on-conflict", action="store_true")

    ge_parser = subparsers.add_parser("export-ge", help="Export Great Expectations suite")
    ge_parser.add_argument("--contract", required=True)
    ge_parser.add_argument("--output", required=True)
    ge_parser.add_argument("--schema-name", default="all")
    ge_parser.add_argument("--suite-name")

    pr_parser = subparsers.add_parser("create-pr", help="Create Azure DevOps PR")
    pr_parser.add_argument("--git-provider", choices=["azure", "github"], default="azure")
    pr_parser.add_argument("--organization")
    pr_parser.add_argument("--github-owner")
    pr_parser.add_argument("--github-repo")
    pr_parser.add_argument("--github-token")
    pr_parser.add_argument("--project")
    pr_parser.add_argument("--repository-id")
    pr_parser.add_argument("--pat-token")
    pr_parser.add_argument("--repo-path", required=True)
    pr_parser.add_argument("--source-branch", required=True)
    pr_parser.add_argument("--target-branch", required=True)
    pr_parser.add_argument("--commit-message", required=True)
    pr_parser.add_argument("--title", required=True)
    pr_parser.add_argument("--description", required=True)
    pr_parser.add_argument("--paths", nargs="*")
    pr_parser.add_argument("--push", action="store_true")

    release_parser = subparsers.add_parser("release", help="Per-contract release workflow helpers")
    release_subparsers = release_parser.add_subparsers(dest="release_command", required=True)

    release_classify_parser = release_subparsers.add_parser(
        "classify",
        help="Classify the required version bump for one contract change set",
    )
    release_classify_parser.add_argument("--base", required=True)
    release_classify_parser.add_argument("--candidate", required=True)
    release_classify_parser.add_argument("--runtime-context", default="auto")

    release_classify_repo_parser = release_subparsers.add_parser(
        "classify-repo",
        help="Classify per-contract required bumps across two contract roots",
    )
    release_classify_repo_parser.add_argument("--base-root", required=True)
    release_classify_repo_parser.add_argument("--candidate-root", required=True)

    release_build_manifest_parser = release_subparsers.add_parser(
        "build-manifest",
        help="Build an editable per-contract release manifest from two contract roots",
    )
    release_build_manifest_parser.add_argument("--base-root", required=True)
    release_build_manifest_parser.add_argument("--candidate-root", required=True)
    release_build_manifest_parser.add_argument("--output", required=True)
    release_build_manifest_parser.add_argument("--target-branch", default="release")
    release_build_manifest_parser.add_argument("--source-branch-prefix", default="release/")

    release_prepare_parser = release_subparsers.add_parser(
        "prepare",
        help="Prepare one promoted contract candidate using an explicit release tag",
    )
    release_prepare_parser.add_argument("--base", required=True)
    release_prepare_parser.add_argument("--candidate", required=True)
    release_prepare_parser.add_argument("--release-tag", required=True)
    release_prepare_parser.add_argument("--output", required=True)
    release_prepare_parser.add_argument("--runtime-context", default="auto")

    release_pr_parser = release_subparsers.add_parser(
        "create-pr",
        help="Prepare one promoted contract candidate and open a release PR",
    )
    release_pr_parser.add_argument("--base", required=True)
    release_pr_parser.add_argument("--candidate", required=True)
    release_pr_parser.add_argument("--release-tag", required=True)
    release_pr_parser.add_argument("--repo-path", required=True)
    release_pr_parser.add_argument("--contract-path", required=True)
    release_pr_parser.add_argument("--source-branch", required=True)
    release_pr_parser.add_argument("--target-branch", required=True)
    release_pr_parser.add_argument("--git-provider", choices=["azure", "github"], default="azure")
    release_pr_parser.add_argument("--organization")
    release_pr_parser.add_argument("--github-owner")
    release_pr_parser.add_argument("--github-repo")
    release_pr_parser.add_argument("--github-token")
    release_pr_parser.add_argument("--project")
    release_pr_parser.add_argument("--repository-id")
    release_pr_parser.add_argument("--pat-token")
    release_pr_parser.add_argument("--title")
    release_pr_parser.add_argument("--description")
    release_pr_parser.add_argument("--commit-message")
    release_pr_parser.add_argument("--push", action="store_true")
    release_pr_parser.add_argument("--runtime-context", default="auto")

    release_prs_parser = release_subparsers.add_parser(
        "create-prs",
        help="Run explicit per-contract release PR automation from a batch manifest",
    )
    release_prs_parser.add_argument("--manifest", required=True)
    release_prs_parser.add_argument("--repo-path", required=True)
    release_prs_parser.add_argument("--git-provider", choices=["azure", "github"], default="azure")
    release_prs_parser.add_argument("--organization")
    release_prs_parser.add_argument("--github-owner")
    release_prs_parser.add_argument("--github-repo")
    release_prs_parser.add_argument("--github-token")
    release_prs_parser.add_argument("--project")
    release_prs_parser.add_argument("--repository-id")
    release_prs_parser.add_argument("--pat-token")
    release_prs_parser.add_argument("--push", action="store_true")

    return parser



def _build_git_config(args: any) -> GitProviderConfig:
    provider = getattr(args, "git_provider", "azure")
    if provider == "github":
        return GitHubConfig(
            owner=getattr(args, "github_owner", ""),
            repo=getattr(args, "github_repo", ""),
            token=getattr(args, "github_token", ""),
        )
    return AzureDevOpsConfig(
        organization=getattr(args, "organization", ""),
        project=getattr(args, "project", ""),
        repository_id=getattr(args, "repository_id", ""),
        pat_token=getattr(args, "pat_token", ""),
    )



def _run_setup(args: argparse.Namespace) -> None:
    import os
    import shutil

    print("🚀 Bootstrapping ContractHub repository...")

    dirs = [
        "contracts",
        "contracts-main",
        "contracts-feature",
        ".github/workflows",
        ".gitlab/ci"
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"📁 Created directory: {d}")

    github_action = """name: Contract Check
on: [pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install uv and deps
        run: pip install uv && uv venv && uv pip install datacontract-flow
      - name: Contract Check
        run: contracthub release classify-repo --base-root contracts-main --candidate-root contracts-feature
"""

    with open(".github/workflows/contract-check.yaml", "w") as f:
        f.write(github_action)
    print("📝 Created .github/workflows/contract-check.yaml")

    gitlab_ci = """stages:
  - validate

contract_check:
  stage: validate
  image: python:3.11-slim
  script:
    - pip install uv
    - uv venv && uv pip install datacontract-flow
    - contracthub release classify-repo --base-root contracts-main --candidate-root contracts-feature
"""
    with open(".gitlab/ci/contract-check.yml", "w") as f:
        f.write(gitlab_ci)
    print("📝 Created .gitlab/ci/contract-check.yml")

    # Try to initialize a default contract using datacontract-cli
    try:
        from datacontract.cli import app as dc_app
        print("📝 Generating sample contract via datacontract-cli...")
        # Just write a basic one manually to avoid click testing issues
        sample_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: sample-contract
name: Sample Contract
version: 1.0.0
status: draft
schema:
  - id: sample
    name: sample
    physicalType: table
    properties:
      - id: col1
        name: col1
        physicalType: string
"""
        with open("contracts/sample.yaml", "w") as f:
            f.write(sample_yaml.lstrip())
    except Exception as e:
        pass

    print("✅ Setup complete! You can now use GitOps for your data contracts.")


def _run_plan(args: argparse.Namespace) -> None:
    from contracthub.orchestrator.pipeline import ContractPipeline
    from contracthub.core.release import classify_contract_change
    from contracthub.utils.yaml_utils import load_yaml

    pipeline = ContractPipeline()

    print(f"\n🔍 Contract Analysis: {args.base}")

    try:
        # Import temporary contract from source
        imported = pipeline.import_schema(
            source_type=args.type,
            source=args.source,
            uc_workspace_url=args.workspace_url,
            uc_token=args.token,
            import_args={"tables": args.tables} if args.tables else None
        )

        # Load base contract
        base_contract = pipeline.loader.load(args.base)

        # Merge them (to normalize and evaluate breaks)
        merge_result = pipeline.merge_contract_updates(imported, base_contract, fail_on_conflict=False)
        merged = merge_result.contract

        # Classify the change
        assessment = classify_contract_change(base_contract, merged)

        if not assessment.has_changes:
            print("🟢 No changes detected.")
        else:
            for reason in assessment.reasons:
                if "Breaking:" in reason or "removed" in reason.lower():
                    print(f"🔴 REMOVED: {reason}")
                elif "added" in reason.lower():
                    print(f"🟢 ADDED: {reason}")
                else:
                    print(f"🟡 CHANGED: {reason}")

            bump = assessment.required_bump.upper()
            if bump == "NONE":
                print("\n✅ Action Required: No version bump needed.")
            elif bump == "MINOR":
                print(f"\n⚠️ Action Required: This is an ADDITIVE change. The required bump is {bump}.")
            elif bump == "MAJOR":
                print(f"\n⚠️ Action Required: This is a BREAKING change. The required bump is {bump}.")

    except Exception as e:
        print(f"❌ Error during plan: {e}")
        import traceback
        traceback.print_exc()
        raise SystemExit(1)

def _run_import(args: argparse.Namespace) -> Path:
    loader = ContractLoader(runtime_context=args.runtime_context)
    existing_contract: Any | None = None
    if args.existing:
        existing_contract = loader.load(args.existing)

    if args.type == "delta":
        oauth_token = _resolve_adls_oauth_token(args)
        table_uris = _parse_table_uris(args.tables)
        contract = DataContract.import_from_source(
            format="delta",
            source=args.source,
            oauth_bearer_token=oauth_token,
            table_uris=table_uris,
        )
    elif args.type in {"sql", "sql-folder"}:
        contract = DataContract.import_from_source(
            format=args.type,
            source=args.source,
        )
    else:
        contract = _import_unity_contract(
            table_fqn=args.source,
            workspace_url=args.workspace_url,
            token=args.token,
        )

    if existing_contract is not None:
        contract = ContractMergeEngine().merge(
            base_contract=contract,
            business_contract=existing_contract,
        ).contract

    return dump_yaml(contract_to_dict(contract), args.output)


def _import_unity_contract(
    *,
    table_fqn: str,
    workspace_url: str | None,
    token: str | None,
) -> OpenDataContractStandard:
    if not workspace_url or not token:
        raise ValueError("--workspace-url and --token are required for uc imports")

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


def _resolve_adls_oauth_token(args: argparse.Namespace) -> str | None:
    if args.adls_oauth_token and args.use_azure_identity:
        raise ValueError("Use either --adls-oauth-token or --use-azure-identity, not both")
    if args.adls_oauth_token:
        return args.adls_oauth_token
    if not args.use_azure_identity:
        return None
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise ValueError(
            "azure-identity is required for --use-azure-identity. Install with `pip install datacontract-flow[azure]`."
        ) from exc
    credential = DefaultAzureCredential()
    token = credential.get_token(args.azure_scope)
    return token.token


def _parse_table_uris(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _run_merge(args: argparse.Namespace) -> Path:
    loader = ContractLoader(runtime_context=args.runtime_context)
    base_contract = loader.load(args.base)
    business_contract = loader.load(args.business)

    result = ContractMergeEngine().merge(
        base_contract,
        business_contract,
        fail_on_conflict=args.fail_on_conflict,
    )
    return dump_yaml(contract_to_dict(result.contract), args.output)


def _run_export_ge(args: argparse.Namespace) -> Path:
    return GreatExpectationsExporter().export_to_path(
        args.contract,
        args.output,
        schema_name=args.schema_name,
        suite_name=args.suite_name,
    )


def _run_create_pr(args: argparse.Namespace) -> dict[str, Any]:
    config = _build_git_config(args)
    manager = PullRequestCreator(config=config)
    return manager.create_update_pr(
        repo_path=args.repo_path,
        source_branch=args.source_branch,
        target_branch=args.target_branch,
        commit_message=args.commit_message,
        title=args.title,
        description=args.description,
        paths=args.paths,
        push=args.push,
    )


def _run_release_classify(args: argparse.Namespace) -> dict[str, Any]:
    loader = ContractLoader(runtime_context=args.runtime_context)
    base_contract = loader.load(args.base)
    candidate_contract = loader.load(args.candidate)

    assessment = classify_contract_change(base_contract, candidate_contract)
    current_version = str(base_contract.version or "")
    return {
        "contractId": str(base_contract.id or ""),
        "currentVersion": current_version,
        "candidateVersion": str(candidate_contract.version or ""),
        "hasChanges": assessment.has_changes,
        "requiredBump": assessment.required_bump,
        "suggestedNextVersion": (
            suggest_release_version(current_version, assessment.required_bump)
            if assessment.has_changes and assessment.required_bump != "none"
            else current_version
        ),
        "reasons": assessment.reasons,
        "breakingChanges": [asdict(change) for change in assessment.breaking_changes],
    }


def _run_release_prepare(args: argparse.Namespace) -> dict[str, Any]:
    loader = ContractLoader(runtime_context=args.runtime_context)
    base_contract = loader.load(args.base)
    candidate_contract = loader.load(args.candidate)

    result = prepare_release_candidate(base_contract, candidate_contract, args.release_tag)
    output_path = dump_yaml(contract_to_dict(result.contract), args.output)
    return {
        "contractId": str(result.contract.id or ""),
        "currentVersion": result.current_version,
        "targetVersion": result.target_version,
        "requiredBump": result.required_bump,
        "actualBump": result.actual_bump,
        "releaseTag": result.release_tag,
        "reasons": result.reasons,
        "breakingChanges": [asdict(change) for change in result.breaking_changes],
        "output": str(output_path),
    }


def _run_release_classify_repo(args: argparse.Namespace) -> dict[str, Any]:
    results = classify_contracts_in_repo(
        base_root=args.base_root,
        candidate_root=args.candidate_root,
    )
    return {
        "contracts": [repository_change_to_dict(item) for item in results],
    }


def _run_release_build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    build = build_batch_release_manifest(
        base_root=args.base_root,
        candidate_root=args.candidate_root,
        target_branch=args.target_branch,
        source_branch_prefix=args.source_branch_prefix,
    )
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([batch_task_to_dict(item) for item in build.tasks], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    payload = batch_manifest_build_to_dict(build)
    payload["output"] = str(output_path)
    return payload


def _run_release_create_pr(args: argparse.Namespace) -> dict[str, Any]:
    loader = ContractLoader(runtime_context=args.runtime_context)
    base_contract = loader.load(args.base)
    candidate_contract = loader.load(args.candidate)

    promotion = prepare_release_candidate(base_contract, candidate_contract, args.release_tag)
    plan = build_release_pr_plan(
        promotion=promotion,
        contract_repo_path=args.contract_path,
        source_branch=args.source_branch,
        target_branch=args.target_branch,
        title=args.title,
        description=args.description,
        commit_message=args.commit_message,
    )
    config = _build_git_config(args)
    payload = create_release_pull_request(
        config=config,
        repo_path=args.repo_path,
        contract_repo_path=args.contract_path,
        base_contract=base_contract,
        candidate_contract=candidate_contract,
        release_tag=args.release_tag,
        source_branch=args.source_branch,
        target_branch=args.target_branch,
        title=plan.title,
        description=plan.description,
        commit_message=plan.commit_message,
        push=args.push,
    )
    payload["plan"] = release_plan_to_dict(plan)
    return payload


def _run_release_create_prs(args: argparse.Namespace) -> dict[str, Any]:
    config = _build_git_config(args)
    tasks = load_batch_release_tasks(args.manifest)
    payload = create_release_pull_requests_from_manifest(
        config=config,
        repo_path=args.repo_path,
        tasks=tasks,
        push=args.push,
    )
    return {
        "tasks": [batch_task_to_dict(item) for item in tasks],
        "results": payload,
    }


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "import":
        output = _run_import(args)
        print(output)
        return 0

    if args.command == "merge":
        output = _run_merge(args)
        print(output)
        return 0

    if args.command == "export-ge":
        output = _run_export_ge(args)
        print(output)
        return 0

    if args.command == "create-pr":
        payload = _run_create_pr(args)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.command == "release":
        if args.release_command == "classify":
            payload = _run_release_classify(args)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.release_command == "classify-repo":
            payload = _run_release_classify_repo(args)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.release_command == "build-manifest":
            payload = _run_release_build_manifest(args)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.release_command == "prepare":
            payload = _run_release_prepare(args)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.release_command == "create-pr":
            payload = _run_release_create_pr(args)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.release_command == "create-prs":
            payload = _run_release_create_prs(args)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
