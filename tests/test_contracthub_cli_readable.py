from __future__ import annotations

import json

from open_data_contract_standard.model import SchemaProperty

from contracthub.interfaces import cli
from contracthub.utils.yaml_utils import dump_yaml, load_yaml


def test_cli_release_classify_outputs_per_contract_required_bump(sample_odcs_model, tmp_path, capsys, monkeypatch):
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
    assert payload["hasChanges"] is True


def test_cli_release_prepare_outputs_promoted_contract(sample_odcs_model, tmp_path, capsys, monkeypatch):
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
