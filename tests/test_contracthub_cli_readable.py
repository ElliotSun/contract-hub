from __future__ import annotations

import json
from typing import Any

from open_data_contract_standard.model import SchemaProperty

from contracthub.interfaces import cli
from contracthub.utils.yaml_utils import dump_yaml, load_yaml


def test_cli_import_supports_delta_table_alias(
    sample_odcs_model, tmp_path, monkeypatch
):
    captured: dict[str, Any] = {}

    def _fake_import_from_source(**kwargs):
        captured.update(kwargs)
        return sample_odcs_model.model_copy(deep=True)

    monkeypatch.setattr(
        "datacontract.data_contract.DataContract.import_from_source",
        _fake_import_from_source,
    )
    output_path = tmp_path / "out.yaml"
    monkeypatch.setattr(
        "sys.argv",
        [
            "contracthub",
            "import",
            "--format",
            "delta-table",
            "--source",
            "abfss://container@acct.dfs.core.windows.net/table_path",
            "--output",
            str(output_path),
        ],
    )

    exit_code = cli.main()

    assert exit_code == 0
    assert captured["format"] == "delta"


def test_cli_import_supports_delta_ddl_alias(sample_odcs_model, tmp_path, monkeypatch):
    captured: dict[str, Any] = {}

    def _fake_import_from_source(**kwargs):
        captured.update(kwargs)
        return sample_odcs_model.model_copy(deep=True)

    monkeypatch.setattr(
        "datacontract.data_contract.DataContract.import_from_source",
        _fake_import_from_source,
    )
    output_path = tmp_path / "out.yaml"
    monkeypatch.setattr(
        "sys.argv",
        [
            "contracthub",
            "import",
            "--format",
            "delta-ddl",
            "--source",
            str(tmp_path),
            "--output",
            str(output_path),
        ],
    )

    exit_code = cli.main()

    assert exit_code == 0
    assert captured["format"] == "delta-ddl"


def test_cli_import_uc_runs_unity_enrichment(
    sample_unity_contract_model, tmp_path, monkeypatch
):
    captured: dict[str, Any] = {}

    def _fake_import_from_source(**kwargs):
        captured["import_kwargs"] = kwargs
        return sample_unity_contract_model.model_copy(deep=True)

    def _fake_enrich(contract, **kwargs):  # noqa: ANN001
        captured["enrich_kwargs"] = kwargs
        return contract

    monkeypatch.setattr(
        "contracthub.importers.unity_importer.DataContract.import_from_source",
        _fake_import_from_source,
    )
    monkeypatch.setattr(
        "contracthub.importers.unity_importer.enrich_unity_contract_relationships",
        _fake_enrich,
    )
    output_path = tmp_path / "out.yaml"
    monkeypatch.setattr(
        "sys.argv",
        [
            "contracthub",
            "import",
            "--format",
            "uc",
            "--source",
            "main.silver.orders",
            "--workspace-url",
            "https://adb.example",
            "--token",
            "token",
            "--output",
            str(output_path),
        ],
    )

    exit_code = cli.main()

    assert exit_code == 0
    assert captured["import_kwargs"]["format"] == "unity"
    assert captured["import_kwargs"]["unity_table_full_name"] == ["main.silver.orders"]
    assert captured["enrich_kwargs"]["table_fqn"] == "main.silver.orders"
    assert captured["enrich_kwargs"]["workspace_url"] == "https://adb.example"
    assert captured["enrich_kwargs"]["token"] == "token"


def test_cli_release_classify_outputs_per_contract_required_bump(
    sample_odcs_model, tmp_path, capsys, monkeypatch
):
    base_contract = sample_odcs_model.model_copy(deep=True)
    candidate_contract = sample_odcs_model.model_copy(deep=True)
    assert candidate_contract.description is not None
    candidate_contract.description.usage = "Updated descriptive text only"

    base_path = dump_yaml(base_contract, tmp_path / "base.yaml")
    candidate_path = dump_yaml(candidate_contract, tmp_path / "candidate.yaml")

    monkeypatch.setattr(
        "sys.argv",
        [
            "contracthub",
            "release",
            "classify",
            "--base",
            str(base_path),
            "--candidate",
            str(candidate_path),
        ],
    )

    exit_code = cli.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["contractId"] == str(base_contract.id)
    assert payload["requiredBump"] == "none"
    assert payload["suggestedNextVersion"] == str(base_contract.version)
    assert payload["hasChanges"] is True


def test_cli_release_prepare_outputs_promoted_contract(
    sample_odcs_model, tmp_path, capsys, monkeypatch
):
    base_contract = sample_odcs_model.model_copy(deep=True)
    candidate_contract = sample_odcs_model.model_copy(deep=True)
    assert candidate_contract.schema_ is not None
    assert candidate_contract.schema_[0].properties is not None
    candidate_contract.schema_[0].properties.append(
        SchemaProperty(
            id="new_optional_column",
            name="new_optional_column",
            physicalName="new_optional_column",
            logicalType="string",
            physicalType="STRING",
            required=False,
        )
    )

    base_path = dump_yaml(base_contract, tmp_path / "base.yaml")
    candidate_path = dump_yaml(candidate_contract, tmp_path / "candidate.yaml")
    output_path = tmp_path / "promoted.yaml"

    monkeypatch.setattr(
        "sys.argv",
        [
            "contracthub",
            "release",
            "prepare",
            "--base",
            str(base_path),
            "--candidate",
            str(candidate_path),
            "--release-tag",
            "orders/v1.2.0",
            "--output",
            str(output_path),
        ],
    )

    exit_code = cli.main()
    payload = json.loads(capsys.readouterr().out)
    promoted = load_yaml(output_path)

    assert exit_code == 0
    assert payload["requiredBump"] == "minor"
    assert payload["actualBump"] == "minor"
    assert payload["targetVersion"] == "1.2.0"
    assert promoted["version"] == "1.2.0"
    assert promoted["id"] == str(base_contract.id)


def test_cli_release_classify_repo_outputs_per_contract_results(
    sample_odcs_model, tmp_path, capsys, monkeypatch
):
    base_root = tmp_path / "base"
    candidate_root = tmp_path / "candidate"
    unchanged = sample_odcs_model.model_copy(deep=True)
    changed = sample_odcs_model.model_copy(deep=True)
    assert changed.description is not None
    changed.description.usage = "Updated descriptive text only"

    dump_yaml(unchanged, base_root / "unchanged.yaml")
    dump_yaml(unchanged, candidate_root / "unchanged.yaml")
    dump_yaml(sample_odcs_model, base_root / "changed.yaml")
    dump_yaml(changed, candidate_root / "changed.yaml")

    monkeypatch.setattr(
        "sys.argv",
        [
            "contracthub",
            "release",
            "classify-repo",
            "--base-root",
            str(base_root),
            "--candidate-root",
            str(candidate_root),
        ],
    )

    exit_code = cli.main()
    payload = json.loads(capsys.readouterr().out)
    by_path = {item["contract_repo_path"]: item for item in payload["contracts"]}

    assert exit_code == 0
    assert by_path["unchanged.yaml"]["status"] == "unchanged"
    assert by_path["changed.yaml"]["status"] == "changed"
    assert by_path["changed.yaml"]["suggested_release_version"] is None


def test_cli_release_create_prs_outputs_batch_payload(
    sample_odcs_model, tmp_path, capsys, monkeypatch
):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    base_contract = sample_odcs_model.model_copy(deep=True)
    candidate_contract = sample_odcs_model.model_copy(deep=True)
    assert candidate_contract.description is not None
    candidate_contract.description.usage = "Updated descriptive text only"

    base_path = dump_yaml(base_contract, tmp_path / "base.yaml")
    candidate_path = dump_yaml(candidate_contract, tmp_path / "candidate.yaml")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "base": str(base_path),
                    "candidate": str(candidate_path),
                    "contract_path": "contracts/orders.yaml",
                    "release_tag": "orders/v1.1.1",
                    "source_branch": "release/orders-v1.1.1",
                    "target_branch": "release",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "contracthub.devops.release_workflow.create_release_pull_requests_from_manifest",
        lambda **kwargs: [
            {
                "promotion": {
                    "contractId": str(base_contract.id),
                    "targetVersion": "1.1.1",
                },
                "pullRequest": {"pullRequestId": 88},
            }
        ],
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "contracthub",
            "release",
            "create-prs",
            "--manifest",
            str(manifest_path),
            "--repo-path",
            str(repo_path),
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
    assert payload["results"][0]["pullRequest"]["pullRequestId"] == 88
    assert payload["tasks"][0]["release_tag"] == "orders/v1.1.1"


def test_cli_release_build_manifest_writes_json_array_and_summary(
    sample_odcs_model, tmp_path, capsys, monkeypatch
):
    base_root = tmp_path / "base"
    candidate_root = tmp_path / "candidate"
    output_path = tmp_path / "release_manifest.json"

    docs_only = sample_odcs_model.model_copy(deep=True)
    assert docs_only.description is not None
    docs_only.description.usage = "Updated descriptive text only"

    additive = sample_odcs_model.model_copy(deep=True)
    assert additive.schema_ is not None
    assert additive.schema_[0].properties is not None
    additive.schema_[0].properties.append(
        SchemaProperty(
            name="new_optional_column",
            logicalType="string",
            physicalType="STRING",
            required=False,
        )
    )

    dump_yaml(sample_odcs_model, base_root / "orders.yaml")
    dump_yaml(docs_only, candidate_root / "orders.yaml")
    dump_yaml(sample_odcs_model, base_root / "payments.yaml")
    dump_yaml(additive, candidate_root / "payments.yaml")

    monkeypatch.setattr(
        "sys.argv",
        [
            "contracthub",
            "release",
            "build-manifest",
            "--base-root",
            str(base_root),
            "--candidate-root",
            str(candidate_root),
            "--output",
            str(output_path),
        ],
    )

    exit_code = cli.main()
    payload = json.loads(capsys.readouterr().out)
    manifest = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["output"] == str(output_path.resolve())
    assert payload["tasks"][0]["contract_path"] == "payments.yaml"
    assert payload["skipped"][0]["contract_repo_path"] == "orders.yaml"
    assert manifest[0]["release_tag"].endswith("/v1.2.0")
