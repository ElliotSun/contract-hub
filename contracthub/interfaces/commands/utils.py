import argparse
import os

def _resolve_adls_oauth_token_from_config() -> str | None:
    from contracthub.core.cloud_storage import AzureADLSCloudStorageAdapter
    from contracthub.core.config import config_manager

    adapter = AzureADLSCloudStorageAdapter()
    try:
        resolved_cred = adapter.resolve_credential()
        if resolved_cred is not None:
            scope = config_manager.get("azure.scope", default="https://storage.azure.com/.default")
            return resolved_cred.get_token(scope).token
    except Exception as exc:
        from contracthub.exceptions import LifecycleError
        raise LifecycleError(f"Azure authentication failed: {exc}") from exc
    return None


def _parse_table_uris(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None

def _build_git_config(args: argparse.Namespace):
    from contracthub.devops.pr_creator import AzureDevOpsConfig, GitHubConfig
    from contracthub.core.config import config_manager

    provider = getattr(args, "git_provider", None) or config_manager.get("git.provider", "CONTRACTHUB_GIT_PROVIDER", "azure")
    if provider == "github":
        return GitHubConfig(
            owner=getattr(args, "github_owner", None) or config_manager.get("git.github_owner", "CONTRACTHUB_GITHUB_OWNER", ""),
            repo=getattr(args, "github_repo", None) or config_manager.get("git.github_repo", "CONTRACTHUB_GITHUB_REPO", ""),
            token=getattr(args, "github_token", None) or config_manager.get("git.github_token", "CONTRACTHUB_GITHUB_TOKEN", ""),
        )
    return AzureDevOpsConfig(
        organization=getattr(args, "organization", None) or config_manager.get("git.organization", "CONTRACTHUB_ORGANIZATION", ""),
        project=getattr(args, "project", None) or config_manager.get("git.project", "CONTRACTHUB_PROJECT", ""),
        repository_id=getattr(args, "repository_id", None) or config_manager.get("git.repository_id", "CONTRACTHUB_REPOSITORY_ID", ""),
        pat_token=getattr(args, "pat_token", None) or config_manager.get("git.pat_token", "CONTRACTHUB_PAT_TOKEN", ""),
    )

def _get_repo_path(args: argparse.Namespace) -> str:
    if getattr(args, "repo_path", None):
        return args.repo_path

    from contracthub.core.config import config_manager
    repo_path_config = config_manager.get("git.repo_path", "CONTRACTHUB_REPO_PATH")
    if repo_path_config:
        return repo_path_config

    gh_workspace = os.environ.get("GITHUB_WORKSPACE")
    if gh_workspace:
        return gh_workspace

    az_workspace = os.environ.get("BUILD_SOURCESDIRECTORY")
    if az_workspace:
        return az_workspace

    raise ValueError(
        "Could not determine repository path. Please provide --repo-path "
        "or set git.repo_path in config or set GITHUB_WORKSPACE / BUILD_SOURCESDIRECTORY environment variables."
    )
