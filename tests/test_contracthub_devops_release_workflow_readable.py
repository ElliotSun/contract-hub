from __future__ import annotations

import json

from contracthub.core.release import prepare_release_candidate
from contracthub.devops.pr_creator import AzureDevOpsConfig
from contracthub.devops.release_workflow import build_release_pr_plan, create_release_pull_request
from contracthub.interfaces import cli
from contracthub.utils.yaml_utils import dump_yaml, load_yaml


def test_build_release_pr_plan_uses_per_contract_defaults(sample_odcs_model):
    base = sample_odcs_model.model_copy(deep=True)
    candidate = sample_odcs_model.model_copy(deep=True)
    assert candidate.description is not None
    candidate.description.usage = "Updated descriptive text only"

    promotion = prepare_release_candidate(base, candidate, "orders/v1.1.1")
    plan = build_release_pr_plan(
        promotion=promotion,
        contract_repo_path="contracts/orders.yaml",
        source_branch="release/orders-v1.1.1",
        target_branch="release",
    )

    assert plan.contract_id == str(base.id)
    assert plan.target_version == "1.1.1"
    assert plan.commit_message == f"release({base.id}): prepare 1.1.1"
    assert "current version" in plan.description


def test_create_release_pull_request_writes_contract_and_calls_pr_creator(sample_odcs_model, tmp_path, monkeypatch):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    base = sample_odcs_model.model_copy(deep=True)
    candidate = sample_odcs_model.model_copy(deep=True)
    assert candidate.description is not None
    candidate.description.usage = "Updated descriptive text only"

    captured: dict[str, object] = {}

    def fake_create_update_pr(self, **kwargs):  # noqa: ANN001
        captured["kwargs"] = kwargs
        return {"pullRequestId": 42}

    monkeypatch.setattr("contracthub.devops.release_workflow.PullRequestCreator.create_update_pr", fake_create_update_pr)

    payload = create_release_pull_request(
        config=AzureDevOpsConfig(
            organization="org",
            project="proj",
            repository_id="repo",
            pat_token="token",
        ),
        repo_path=str(repo_path),
        contract_repo_path="contracts/orders.yaml",
        base_contract=base,
        candidate_contract=candidate,
        release_tag="orders/v1.1.1",
        source_branch="release/orders-v1.1.1",
        target_branch="release",
        push=True,
    )

    written = load_yaml(repo_path / "contracts/orders.yaml")
    assert payload["pullRequest"]["pullRequestId"] == 42
    assert payload["promotion"]["targetVersion"] == "1.1.1"
    assert written["version"] == "1.1.1"
    assert written["id"] == str(base.id)
    assert captured["kwargs"]["paths"] == ["contracts/orders.yaml"]  # type: ignore[index]
    assert captured["kwargs"]["push"] is True  # type: ignore[index]


def test_cli_release_create_pr_outputs_plan_and_pr_payload(sample_odcs_model, tmp_path, capsys, monkeypatch):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    base = sample_odcs_model.model_copy(deep=True)
    candidate = sample_odcs_model.model_copy(deep=True)
    assert candidate.description is not None
    candidate.description.usage = "Updated descriptive text only"

    base_path = dump_yaml(base, tmp_path / "base.yaml")
    candidate_path = dump_yaml(candidate, tmp_path / "candidate.yaml")

    monkeypatch.setattr(
        "contracthub.interfaces.cli.create_release_pull_request",
        lambda **kwargs: {
            "promotion": {"contractId": str(base.id), "targetVersion": "1.1.1"},
            "pullRequest": {"pullRequestId": 77},
        },
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "contracthub",
            "release",
            "create-pr",
            "--base",
            str(base_path),
            "--candidate",
            str(candidate_path),
            "--release-tag",
            "orders/v1.1.1",
            "--repo-path",
            str(repo_path),
            "--contract-path",
            "contracts/orders.yaml",
            "--source-branch",
            "release/orders-v1.1.1",
            "--target-branch",
            "release",
            "--organization",
            "org",
            "--project",
            "proj",
            "--repository-id",
            "repo",
            "--pat-token",
            "token",
        ],
    )

    exit_code = cli.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["pullRequest"]["pullRequestId"] == 77
    assert payload["promotion"]["targetVersion"] == "1.1.1"
    assert payload["plan"]["target_version"] == "1.1.1"
