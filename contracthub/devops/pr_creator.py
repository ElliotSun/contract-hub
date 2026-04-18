from __future__ import annotations

import base64
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

import requests


class GitProviderConfig(Protocol):
    """Protocol for Git provider configuration."""
    pass


@dataclass(slots=True)
class AzureDevOpsConfig:
    """Azure DevOps connection settings."""
    organization: str
    project: str
    repository_id: str
    pat_token: str
    api_version: str = "7.1-preview.1"


@dataclass(slots=True)
class GitHubConfig:
    """GitHub connection settings."""
    owner: str
    repo: str
    token: str


class GitProvider(Protocol):
    """Protocol for Git provider operations."""
    def create_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        reviewers: list[str] | None = None,
    ) -> dict[str, Any]:
        ...


class AzureDevOpsProvider:
    def __init__(self, config: AzureDevOpsConfig):
        self.config = config

    def create_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        reviewers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create an Azure DevOps pull request via REST API."""
        url = (
            f"https://dev.azure.com/{self.config.organization}/{self.config.project}"
            f"/_apis/git/repositories/{self.config.repository_id}/pullrequests"
            f"?api-version={self.config.api_version}"
        )

        payload: dict[str, Any] = {
            "sourceRefName": f"refs/heads/{source_branch}",
            "targetRefName": f"refs/heads/{target_branch}",
            "title": title,
            "description": description,
        }
        if reviewers:
            payload["reviewers"] = [{"id": reviewer} for reviewer in reviewers]

        response = requests.post(url, headers=self._headers(), data=json.dumps(payload), timeout=30)
        if not response.ok:
            raise RuntimeError(
                f"Failed to create PR in Azure DevOps: status={response.status_code}, body={response.text[:500]}"
            )
        return response.json()

    def _headers(self) -> dict[str, str]:
        token = f":{self.config.pat_token}".encode("utf-8")
        auth = base64.b64encode(token).decode("utf-8")
        return {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
        }


class GitHubProvider:
    def __init__(self, config: GitHubConfig):
        self.config = config

    def create_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        reviewers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a GitHub pull request via REST API."""
        url = f"https://api.github.com/repos/{self.config.owner}/{self.config.repo}/pulls"

        payload: dict[str, Any] = {
            "title": title,
            "head": source_branch,
            "base": target_branch,
            "body": description,
        }

        response = requests.post(url, headers=self._headers(), data=json.dumps(payload), timeout=30)
        if not response.ok:
            raise RuntimeError(
                f"Failed to create PR in GitHub: status={response.status_code}, body={response.text[:500]}"
            )

        pr_data = response.json()

        if reviewers:
            pr_number = pr_data.get("number")
            if pr_number:
                reviewers_url = f"{url}/{pr_number}/requested_reviewers"
                reviewers_payload = {"reviewers": reviewers}
                requests.post(reviewers_url, headers=self._headers(), data=json.dumps(reviewers_payload), timeout=30)

        return pr_data

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }


@dataclass(slots=True)
class PullRequestCreator:
    """Manage contract commits and pull requests for GitOps workflows."""

    provider: GitProvider

    def __init__(self, config: GitProviderConfig | GitProvider):
        # Support legacy init with just config
        if isinstance(config, AzureDevOpsConfig):
            self.provider = AzureDevOpsProvider(config)
        elif isinstance(config, GitHubConfig):
            self.provider = GitHubProvider(config)
        else:
            self.provider = config

    def commit_updated_contracts(
        self,
        repo_path: str,
        *,
        source_branch: str,
        commit_message: str,
        paths: list[str] | None = None,
    ) -> str:
        """Commit updated contract artifacts and return commit SHA."""
        repo = Path(repo_path).expanduser().resolve()
        self._ensure_branch(repo, source_branch)

        if paths:
            self._git(repo, ["add", *paths])
        else:
            self._git(repo, ["add", "-u"])

        status = self._git(repo, ["status", "--porcelain"], capture_output=True)
        if not status.stdout.strip():
            return self._git(repo, ["rev-parse", "HEAD"], capture_output=True).stdout.strip()

        self._git(repo, ["commit", "-m", commit_message])
        return self._git(repo, ["rev-parse", "HEAD"], capture_output=True).stdout.strip()

    def create_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        reviewers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a pull request using the configured provider."""
        return self.provider.create_pull_request(
            source_branch=source_branch,
            target_branch=target_branch,
            title=title,
            description=description,
            reviewers=reviewers,
        )

    def create_update_pr(
        self,
        *,
        repo_path: str,
        source_branch: str,
        target_branch: str,
        commit_message: str,
        title: str,
        description: str,
        paths: list[str] | None = None,
        push: bool = False,
    ) -> dict[str, Any]:
        """Commit changes and create PR in one operation."""
        self.commit_updated_contracts(
            repo_path,
            source_branch=source_branch,
            commit_message=commit_message,
            paths=paths,
        )

        if push:
            repo = Path(repo_path).expanduser().resolve()
            self._git(repo, ["push", "origin", source_branch])

        return self.create_pull_request(
            source_branch=source_branch,
            target_branch=target_branch,
            title=title,
            description=description,
        )

    @staticmethod
    def _git(repo: Path, args: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            text=True,
            capture_output=capture_output,
        )

    def _ensure_branch(self, repo: Path, source_branch: str) -> None:
        current_branch = self._git(repo, ["rev-parse", "--abbrev-ref", "HEAD"], capture_output=True).stdout.strip()
        if current_branch == source_branch:
            return

        branch_check = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", source_branch],
            check=False,
            text=True,
            capture_output=True,
        )
        if branch_check.returncode == 0:
            self._git(repo, ["checkout", source_branch])
            return

        self._git(repo, ["checkout", "-b", source_branch])
