from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml
from open_data_contract_standard.model import OpenDataContractStandard


@pytest.fixture
def sample_odcs_path() -> Path:
    return Path(__file__).resolve().parents[1] / "sample_odcs.yaml"


@pytest.fixture
def sample_odcs_dict(sample_odcs_path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(sample_odcs_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


@pytest.fixture
def sample_odcs_copy(sample_odcs_dict: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(sample_odcs_dict)


@pytest.fixture
def sample_odcs_model(sample_odcs_dict: dict[str, Any]) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_odcs_dict)
