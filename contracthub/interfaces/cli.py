from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from contracthub.core.loader import ContractLoader
from contracthub.devops.pr_creator import AzureDevOpsConfig, PullRequestCreator
from contracthub.importers.delta_importer import DeltaTableImporter
from contracthub.importers.sql_importer import SQLFolderImporter
from contracthub.importers.uc_importer import UnityCatalogImporter
from contracthub.lifecycle.merge_engine import ContractMergeEngine
from contracthub.quality.ge_exporter import GreatExpectationsExporter
from contracthub.utils.schema_utils import contract_to_dict, contract_to_model
from contracthub.utils.yaml_utils import dump_yaml


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contracthub")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="Import contract from source")
    import_parser.add_argument("--type", choices=["delta", "sql", "uc"], required=True)
    import_parser.add_argument("--source", required=True)
    import_parser.add_argument("--output", required=True)
    import_parser.add_argument("--existing")
    import_parser.add_argument("--runtime-context", default="auto")
    import_parser.add_argument("--workspace-url")
    import_parser.add_argument("--token")

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
    pr_parser.add_argument("--organization", required=True)
    pr_parser.add_argument("--project", required=True)
    pr_parser.add_argument("--repository-id", required=True)
    pr_parser.add_argument("--pat-token", required=True)
    pr_parser.add_argument("--repo-path", required=True)
    pr_parser.add_argument("--source-branch", required=True)
    pr_parser.add_argument("--target-branch", required=True)
    pr_parser.add_argument("--commit-message", required=True)
    pr_parser.add_argument("--title", required=True)
    pr_parser.add_argument("--description", required=True)
    pr_parser.add_argument("--paths", nargs="*")
    pr_parser.add_argument("--push", action="store_true")

    return parser


def _run_import(args: argparse.Namespace) -> Path:
    loader = ContractLoader(runtime_context=args.runtime_context)
    existing_contract: dict[str, Any] | None = None
    if args.existing:
        existing_contract = contract_to_dict(loader.load(args.existing))

    if args.type == "delta":
        contract_dict = DeltaTableImporter(args.source).import_contract(existing_contract=existing_contract)
        contract = contract_to_model(contract_dict)
    elif args.type == "sql":
        contract_dict = SQLFolderImporter(args.source).import_contract(existing_contract=existing_contract)
        contract = contract_to_model(contract_dict)
    else:
        if not args.workspace_url or not args.token:
            raise ValueError("--workspace-url and --token are required for uc imports")
        contract = UnityCatalogImporter(workspace_url=args.workspace_url, token=args.token).import_contract(
            args.source,
            existing_contract=existing_contract,
        )

    return dump_yaml(contract_to_dict(contract), args.output)


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
    config = AzureDevOpsConfig(
        organization=args.organization,
        project=args.project,
        repository_id=args.repository_id,
        pat_token=args.pat_token,
    )
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

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
