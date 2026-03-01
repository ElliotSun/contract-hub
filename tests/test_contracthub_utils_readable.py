from __future__ import annotations

from pathlib import Path

import pytest

from contracthub.utils.schema_utils import contract_to_dict, contract_to_model, ensure_schema_key
from contracthub.utils.yaml_utils import dump_yaml, load_yaml


def test_yaml_utils_can_load_and_dump_sample_contract(sample_odcs_dict, tmp_path):
    output_path = dump_yaml(sample_odcs_dict, tmp_path / "roundtrip.yaml")
    reloaded = load_yaml(output_path)

    assert output_path.exists()
    assert reloaded["id"] == sample_odcs_dict["id"]
    assert len(reloaded["schema"]) == len(sample_odcs_dict["schema"])


def test_yaml_utils_rejects_non_mapping_yaml(tmp_path):
    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text("- not-a-mapping", encoding="utf-8")

    with pytest.raises(ValueError, match="mapping object"):
        load_yaml(invalid_yaml)


def test_schema_utils_convert_sample_contract_between_input_types(sample_odcs_dict, sample_odcs_path):
    model_from_dict = contract_to_model(sample_odcs_dict)
    model_from_path = contract_to_model(sample_odcs_path)
    model_from_string_path = contract_to_model(str(sample_odcs_path))
    dict_from_model = contract_to_dict(model_from_dict)

    assert model_from_dict.id == sample_odcs_dict["id"]
    assert model_from_path.id == sample_odcs_dict["id"]
    assert model_from_string_path.id == sample_odcs_dict["id"]
    assert dict_from_model["id"] == sample_odcs_dict["id"]


def test_schema_utils_rejects_unsupported_input_type():
    with pytest.raises(TypeError, match="Unsupported contract input type"):
        contract_to_model(12345)  # type: ignore[arg-type]


def test_schema_utils_ensure_schema_key_handles_schema_alias_and_missing_key():
    assert ensure_schema_key({"schema": []}) == "schema"
    assert ensure_schema_key({"schema_": []}) == "schema_"

    payload = {}
    key = ensure_schema_key(payload)
    assert key == "schema"
    assert payload["schema"] == []
