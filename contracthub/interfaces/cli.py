from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from contracthub.devops.pr_creator import GitProviderConfig

DEFAULT_AZURE_STORAGE_SCOPE = "https://storage.azure.com/.default"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contracthub")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "setup", help="Bootstrap repository with GitOps templates and CI pipelines"
    )

    enrich_parser = subparsers.add_parser(
        "enrich", help="Enrich data contract with semantic relationship labels via LLM"
    )
    enrich_parser.add_argument(
        "--contract", required=True, help="Path to the YAML contract"
    )
    enrich_parser.add_argument(
        "--concurrency", type=int, default=1, help="Max parallel LLM API calls"
    )
    enrich_parser.add_argument(
        "--mode",
        choices=["label", "infer_joins"],
        default="label",
        help="Enrichment mode: 'label' tags existing relationships, 'infer_joins' discovers new ones",
    )

    plan_parser = subparsers.add_parser(
        "plan", help="Dry run and summarize changes between source and base contract"
    )
    plan_parser.add_argument("--source", required=True)
    plan_parser.add_argument("--base", required=True)
    plan_parser.add_argument(
        "--type", choices=["delta", "sql", "sql-folder", "uc", "unity"], required=True
    )
    plan_parser.add_argument("--tables")
    plan_parser.add_argument("--workspace-url")
    plan_parser.add_argument("--token")

    import_parser = subparsers.add_parser("import", help="Import contract from source")
    import_parser.add_argument(
        "--format",
        choices=[
            "delta",
            "delta-table",
            "delta-ddl",
            "sql",
            "sql-folder",
            "uc",
            "unity",
        ],
        required=True,
    )
    import_parser.add_argument("--source", required=True)
    import_parser.add_argument("--output", required=True)
    import_parser.add_argument("--existing")
    import_parser.add_argument("--runtime-context", default="auto")
    import_parser.add_argument("--workspace-url")
    import_parser.add_argument("--token")
    import_parser.add_argument(
        "--adls-oauth-token", help="OAuth bearer token for ADLS Gen2 access"
    )
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
        help="Comma-separated list of additional Delta table URIs (used with --format delta or --format delta-table)",
    )

    merge_parser = subparsers.add_parser(
        "merge", help="Merge base and business-edited contracts"
    )
    merge_parser.add_argument("--base", required=True)
    merge_parser.add_argument("--business", required=True)
    merge_parser.add_argument("--output", required=True)
    merge_parser.add_argument("--runtime-context", default="auto")
    merge_parser.add_argument("--fail-on-conflict", action="store_true")

    export_parser = subparsers.add_parser(
        "export", help="Convert data contract to a specific format"
    )
    export_parser.add_argument(
        "location",
        nargs="?",
        default="datacontract.yaml",
        help="The location (url or path) of the data contract yaml",
    )
    export_parser.add_argument(
        "--format",
        required=True,
        help="The export format (e.g. html, graph, jsonschema, dbt, etc.)",
    )
    export_parser.add_argument(
        "--output",
        help="Specify the file path where the exported data will be saved. If no path is provided, the output will be printed to stdout.",
    )
    export_parser.add_argument("--server", help="The server name to export.")
    export_parser.add_argument(
        "--schema-name",
        default="all",
        help="The name of the schema to export, e.g., orders, or all for all schemas (default).",
    )
    export_parser.add_argument(
        "--sql-server-type",
        default="auto",
        help="The server type to determine the sql dialect.",
    )
    export_parser.add_argument(
        "--export-args",
        help='Additional arguments for custom exporters in JSON string format, e.g. \'{"format": "cypher"}\'',
    )

    ge_parser = subparsers.add_parser(
        "export-ge", help="Export Great Expectations suite"
    )
    ge_parser.add_argument("--contract", required=True)
    ge_parser.add_argument("--output", required=True)
    ge_parser.add_argument("--schema-name", default="all")
    ge_parser.add_argument("--suite-name")

    pr_parser = subparsers.add_parser("create-pr", help="Create Azure DevOps PR")
    pr_parser.add_argument(
        "--git-provider",
        choices=["azure", "github"],
        default=os.environ.get("CONTRACTHUB_GIT_PROVIDER", "azure"),
    )
    pr_parser.add_argument(
        "--organization", default=os.environ.get("CONTRACTHUB_ORGANIZATION")
    )
    pr_parser.add_argument(
        "--github-owner", default=os.environ.get("CONTRACTHUB_GITHUB_OWNER")
    )
    pr_parser.add_argument(
        "--github-repo", default=os.environ.get("CONTRACTHUB_GITHUB_REPO")
    )
    pr_parser.add_argument(
        "--github-token", default=os.environ.get("CONTRACTHUB_GITHUB_TOKEN")
    )
    pr_parser.add_argument("--project", default=os.environ.get("CONTRACTHUB_PROJECT"))
    pr_parser.add_argument(
        "--repository-id", default=os.environ.get("CONTRACTHUB_REPOSITORY_ID")
    )
    pr_parser.add_argument(
        "--pat-token", default=os.environ.get("CONTRACTHUB_PAT_TOKEN")
    )
    pr_parser.add_argument("--repo-path", required=True)
    pr_parser.add_argument("--source-branch", required=True)
    pr_parser.add_argument("--target-branch", required=True)
    pr_parser.add_argument("--commit-message", required=True)
    pr_parser.add_argument("--title", required=True)
    pr_parser.add_argument("--description", required=True)
    pr_parser.add_argument("--paths", nargs="*")
    pr_parser.add_argument("--push", action="store_true")

    release_parser = subparsers.add_parser(
        "release", help="Per-contract release workflow helpers"
    )
    release_subparsers = release_parser.add_subparsers(
        dest="release_command", required=True
    )

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
    release_build_manifest_parser.add_argument(
        "--source-branch-prefix", default="release/"
    )

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
    release_pr_parser.add_argument(
        "--git-provider",
        choices=["azure", "github"],
        default=os.environ.get("CONTRACTHUB_GIT_PROVIDER", "azure"),
    )
    release_pr_parser.add_argument(
        "--organization", default=os.environ.get("CONTRACTHUB_ORGANIZATION")
    )
    release_pr_parser.add_argument(
        "--github-owner", default=os.environ.get("CONTRACTHUB_GITHUB_OWNER")
    )
    release_pr_parser.add_argument(
        "--github-repo", default=os.environ.get("CONTRACTHUB_GITHUB_REPO")
    )
    release_pr_parser.add_argument(
        "--github-token", default=os.environ.get("CONTRACTHUB_GITHUB_TOKEN")
    )
    release_pr_parser.add_argument(
        "--project", default=os.environ.get("CONTRACTHUB_PROJECT")
    )
    release_pr_parser.add_argument(
        "--repository-id", default=os.environ.get("CONTRACTHUB_REPOSITORY_ID")
    )
    release_pr_parser.add_argument(
        "--pat-token", default=os.environ.get("CONTRACTHUB_PAT_TOKEN")
    )
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
    release_prs_parser.add_argument(
        "--git-provider",
        choices=["azure", "github"],
        default=os.environ.get("CONTRACTHUB_GIT_PROVIDER", "azure"),
    )
    release_prs_parser.add_argument(
        "--organization", default=os.environ.get("CONTRACTHUB_ORGANIZATION")
    )
    release_prs_parser.add_argument(
        "--github-owner", default=os.environ.get("CONTRACTHUB_GITHUB_OWNER")
    )
    release_prs_parser.add_argument(
        "--github-repo", default=os.environ.get("CONTRACTHUB_GITHUB_REPO")
    )
    release_prs_parser.add_argument(
        "--github-token", default=os.environ.get("CONTRACTHUB_GITHUB_TOKEN")
    )
    release_prs_parser.add_argument(
        "--project", default=os.environ.get("CONTRACTHUB_PROJECT")
    )
    release_prs_parser.add_argument(
        "--repository-id", default=os.environ.get("CONTRACTHUB_REPOSITORY_ID")
    )
    release_prs_parser.add_argument(
        "--pat-token", default=os.environ.get("CONTRACTHUB_PAT_TOKEN")
    )
    release_prs_parser.add_argument("--push", action="store_true")

    return parser


def _build_git_config(args: argparse.Namespace) -> "GitProviderConfig":
    from contracthub.devops.pr_creator import AzureDevOpsConfig, GitHubConfig

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

    print("🚀 Bootstrapping ContractHub repository...")

    dirs = [
        "contracts",
        "contracts-main",
        "contracts-feature",
        ".github/workflows",
        ".gitlab/ci",
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
    gh_action_path = ".github/workflows/contract-check.yaml"
    if not os.path.exists(gh_action_path):
        with open(gh_action_path, "w") as f:
            f.write(github_action)
        print(f"📄 Created GitHub Actions workflow: {gh_action_path}")
    else:
        print(f"⏭️ Skipped existing GitHub Actions workflow: {gh_action_path}")

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
        sample_path = "contracts/sample.yaml"
        if not os.path.exists(sample_path):
            with open(sample_path, "w") as f:
                f.write(sample_yaml.lstrip())
            print(f"📄 Created sample contract: {sample_path}")
        else:
            print(f"⏭️ Skipped existing sample contract: {sample_path}")
    except Exception:
        import logging

        logging.getLogger("contracthub").debug(
            "Failed to generate sample contract via datacontract-cli", exc_info=True
        )

    print("✅ Setup complete! You can now use GitOps for your data contracts.")


def _run_plan(args: argparse.Namespace) -> None:
    from contracthub.orchestrator.pipeline import ContractPipeline
    from contracthub.core.release import classify_contract_change

    pipeline = ContractPipeline()

    print(f"\n🔍 Contract Analysis: {args.base}")

    try:
        # Import temporary contract from source
        imported = pipeline.import_schema(
            source_type=args.type,
            source=args.source,
            uc_workspace_url=args.workspace_url,
            uc_token=args.token,
            import_args={"tables": args.tables} if args.tables else None,
        )

        # Load base contract
        base_contract = pipeline.loader.load(args.base)

        # Merge them (to normalize and evaluate breaks)
        merge_result = pipeline.merge_contract_updates(
            imported, base_contract, fail_on_conflict=False
        )
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
                print(
                    f"\n⚠️ Action Required: This is an ADDITIVE change. The required bump is {bump}."
                )
            elif bump == "MAJOR":
                print(
                    f"\n⚠️ Action Required: This is a BREAKING change. The required bump is {bump}."
                )

    except Exception as e:
        from contracthub.exceptions import ContractHubError
        import logging

        if isinstance(e, ContractHubError):
            logging.getLogger("contracthub").error("Plan failed: %s", e)
        else:
            logging.getLogger("contracthub").error("Plan failed: %s", e, exc_info=True)
        print(f"❌ Error during plan: {e}")
        raise SystemExit(1)


def _run_import(args: argparse.Namespace) -> Path:
    from contracthub.core.loader import ContractLoader
    from datacontract.data_contract import DataContract
    from contracthub.importers.unity_importer import import_unity_contract
    from contracthub.lifecycle.merge_engine import ContractMergeEngine
    from contracthub.utils.schema_utils import contract_to_dict
    from contracthub.utils.yaml_utils import dump_yaml

    loader = ContractLoader(runtime_context=args.runtime_context)
    existing_contract: Any | None = None
    if args.existing:
        existing_contract = loader.load(args.existing)

    if args.format in {"delta", "delta-table"}:
        oauth_token = _resolve_adls_oauth_token(args)
        table_uris = _parse_table_uris(args.tables)
        contract = DataContract.import_from_source(
            format="delta",
            source=args.source,
            oauth_bearer_token=oauth_token,
            table_uris=table_uris,
        )
    elif args.format == "delta-ddl":
        contract = DataContract.import_from_source(
            format="delta-ddl",
            source=args.source,
        )
    elif args.format in {"sql", "sql-folder"}:
        # Note: 'sql' uses the upstream datacontract-cli native importer for single files.
        # 'sql-folder' uses our custom extension (contracthub.importers.sql_importer.SQLFolderImporter)
        # to batch import multiple DDL files from a directory.
        contract = DataContract.import_from_source(
            format=args.format,
            source=args.source,
        )
    else:
        contract = import_unity_contract(
            table_fqn=args.source,
            workspace_url=args.workspace_url,
            token=args.token,
        )

    if existing_contract is not None:
        contract = (
            ContractMergeEngine()
            .merge(
                base_contract=contract,
                business_contract=existing_contract,
            )
            .contract
        )

    return dump_yaml(contract_to_dict(contract), args.output)


def _resolve_adls_oauth_token(args: argparse.Namespace) -> str | None:
    if args.adls_oauth_token and args.use_azure_identity:
        raise ValueError(
            "Use either --adls-oauth-token or --use-azure-identity, not both"
        )
    if args.adls_oauth_token:
        return args.adls_oauth_token
    if not args.use_azure_identity:
        return None
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        from contracthub.exceptions import LifecycleError

        raise LifecycleError(
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
    from contracthub.core.loader import ContractLoader
    from contracthub.lifecycle.merge_engine import ContractMergeEngine
    from contracthub.utils.schema_utils import contract_to_dict
    from contracthub.utils.yaml_utils import dump_yaml

    loader = ContractLoader(runtime_context=args.runtime_context)
    base_contract = loader.load(args.base)
    business_contract = loader.load(args.business)

    result = ContractMergeEngine().merge(
        base_contract,
        business_contract,
        fail_on_conflict=args.fail_on_conflict,
    )
    return dump_yaml(contract_to_dict(result.contract), args.output)


def _run_export(args: argparse.Namespace) -> str:
    from datacontract.data_contract import DataContract

    export_args_dict = {}
    if args.export_args:
        try:
            export_args_dict = json.loads(args.export_args)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse --export-args as JSON: {exc}")

    # Pre-parse using contracthub's more robust loader if it's our graph exporter
    # because DataContract SDK doesn't consistently attach the payload schema_
    # to the `m` object for unregistered legacy or custom ODCS schemas out-of-the-box in the same way.
    if args.format == "graph":
        from contracthub.utils.schema_utils import contract_to_model
        from contracthub.exporters.graph_exporter import GraphExporter

        contract_model = contract_to_model(args.location)
        exporter = GraphExporter(export_format="graph")
        result = exporter.export(
            data_contract=contract_model,
            schema_name=args.schema_name,
            server=args.server,
            sql_server_type=args.sql_server_type,
            export_args=export_args_dict,
        )
    else:
        contract = DataContract(data_contract_file=args.location)
        # We call the datacontract sdk export method which handles stdout printing
        # and file writing according to the output arg, while dynamically using registered exporters
        result = contract.export(
            export_format=args.format,
            server=args.server,
            schema_name=args.schema_name,
            sql_server_type=args.sql_server_type,
            export_args=export_args_dict,
        )

    if args.output:
        # data contract sdk `export` method already writes to file if `export()` handles output,
        # but in datacontract-cli 0.11.x sometimes we need to write manually if custom exporter doesn't handle writing
        # SDK usually returns the exported string.
        if result is not None:
            Path(args.output).write_text(result, encoding="utf-8")
            return f"Exported to {args.output}"
        return f"Exported to {args.output}"

    # If no output file, we just return the result to print to stdout
    return result if result is not None else ""


def _run_export_ge(args: argparse.Namespace) -> Path:
    import sys
    from contracthub.quality.ge_exporter import GreatExpectationsExporter

    try:
        return GreatExpectationsExporter().export_to_path(
            args.contract,
            args.output,
            schema_name=args.schema_name,
            suite_name=args.suite_name,
        )
    except (RuntimeError, ImportError) as exc:
        if "requires pyspark to be installed" in str(exc) or "pyspark" in str(exc):
            sys.exit(str(exc))
        raise


def _run_create_pr(args: argparse.Namespace) -> dict[str, Any]:
    from contracthub.devops.pr_creator import PullRequestCreator

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
    from contracthub.core.loader import ContractLoader
    from contracthub.core.release import (
        classify_contract_change,
        suggest_release_version,
    )
    from dataclasses import asdict

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
    from contracthub.core.loader import ContractLoader
    from contracthub.core.release import prepare_release_candidate
    from contracthub.utils.schema_utils import contract_to_dict
    from contracthub.utils.yaml_utils import dump_yaml
    from dataclasses import asdict

    loader = ContractLoader(runtime_context=args.runtime_context)
    base_contract = loader.load(args.base)
    candidate_contract = loader.load(args.candidate)

    result = prepare_release_candidate(
        base_contract, candidate_contract, args.release_tag
    )
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
    from contracthub.devops.release_workflow import (
        classify_contracts_in_repo,
        repository_change_to_dict,
    )

    results = classify_contracts_in_repo(
        base_root=args.base_root,
        candidate_root=args.candidate_root,
    )
    return {
        "contracts": [repository_change_to_dict(item) for item in results],
    }


def _run_release_build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    from contracthub.devops.release_workflow import (
        build_batch_release_manifest,
        batch_task_to_dict,
        batch_manifest_build_to_dict,
    )

    build = build_batch_release_manifest(
        base_root=args.base_root,
        candidate_root=args.candidate_root,
        target_branch=args.target_branch,
        source_branch_prefix=args.source_branch_prefix,
    )
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            [batch_task_to_dict(item) for item in build.tasks], indent=2, sort_keys=True
        ),
        encoding="utf-8",
    )
    payload = batch_manifest_build_to_dict(build)
    payload["output"] = str(output_path)
    return payload


def _run_release_create_pr(args: argparse.Namespace) -> dict[str, Any]:
    from contracthub.core.loader import ContractLoader
    from contracthub.core.release import prepare_release_candidate
    from contracthub.devops.release_workflow import (
        build_release_pr_plan,
        create_release_pull_request,
        release_plan_to_dict,
    )

    loader = ContractLoader(runtime_context=args.runtime_context)
    base_contract = loader.load(args.base)
    candidate_contract = loader.load(args.candidate)

    promotion = prepare_release_candidate(
        base_contract, candidate_contract, args.release_tag
    )
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


def _run_enrich(args: argparse.Namespace) -> str:
    from contracthub.tools.enricher import ContractEnricher

    enricher = ContractEnricher()
    enricher.process(
        args.contract, max_workers=args.concurrency, mode=getattr(args, "mode", "label")
    )
    return f"Successfully enriched {args.contract} (mode: {getattr(args, 'mode', 'label')})"


def _run_release_create_prs(args: argparse.Namespace) -> dict[str, Any]:
    from contracthub.devops.release_workflow import (
        load_batch_release_tasks,
        create_release_pull_requests_from_manifest,
        batch_task_to_dict,
    )

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
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    try:
        if args.command == "setup":
            _run_setup(args)
            return 0

        if args.command == "enrich":
            output = _run_enrich(args)
            print(output)
            return 0

        if args.command == "plan":
            _run_plan(args)
            return 0

        if args.command == "import":
            output = _run_import(args)
            print(output)
            return 0

        if args.command == "export":
            output = _run_export(args)
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

    except KeyboardInterrupt:
        return 130
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:
        from contracthub.exceptions import ContractHubError
        import logging

        if isinstance(exc, ContractHubError):
            logging.getLogger("contracthub").error("Fatal error: %s", exc)
        else:
            logging.getLogger("contracthub").error(
                "Fatal error: %s", exc, exc_info=True
            )
        print(f"❌ {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
