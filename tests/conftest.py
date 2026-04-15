from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from open_data_contract_standard.model import OpenDataContractStandard


def _fixture_contract_path(*parts: str) -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "contracts" / Path(*parts)


def _load_yaml_fixture(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _fixture_path(*parts: str) -> Path:
    return Path(__file__).resolve().parent / "fixtures" / Path(*parts)


@pytest.fixture
def sample_odcs_path() -> Path:
    return _fixture_contract_path("odcs", "full_sample.yaml")


@pytest.fixture
def sample_odcs_dict(sample_odcs_path: Path) -> dict[str, Any]:
    return _load_yaml_fixture(sample_odcs_path)


@pytest.fixture
def sample_odcs_model(sample_odcs_dict: dict[str, Any]) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_odcs_dict)


@pytest.fixture
def sample_spark_ddl_contract_path() -> Path:
    return _fixture_contract_path("spark_ddl", "imported_orders.yaml")


@pytest.fixture
def sample_spark_ddl_contract_dict(sample_spark_ddl_contract_path: Path) -> dict[str, Any]:
    return _load_yaml_fixture(sample_spark_ddl_contract_path)


@pytest.fixture
def sample_spark_ddl_contract_model(sample_spark_ddl_contract_dict: dict[str, Any]) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_spark_ddl_contract_dict)


@pytest.fixture
def sample_delta_rs_contract_path() -> Path:
    return _fixture_contract_path("delta_rs", "imported_orders.yaml")


@pytest.fixture
def sample_delta_rs_contract_dict(sample_delta_rs_contract_path: Path) -> dict[str, Any]:
    return _load_yaml_fixture(sample_delta_rs_contract_path)


@pytest.fixture
def sample_delta_rs_contract_model(sample_delta_rs_contract_dict: dict[str, Any]) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_delta_rs_contract_dict)


@pytest.fixture
def sample_unity_contract_path() -> Path:
    return _fixture_contract_path("unity", "governed_orders.yaml")


@pytest.fixture
def sample_unity_contract_dict(sample_unity_contract_path: Path) -> dict[str, Any]:
    return _load_yaml_fixture(sample_unity_contract_path)


@pytest.fixture
def sample_unity_contract_model(sample_unity_contract_dict: dict[str, Any]) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_unity_contract_dict)


@pytest.fixture
def sample_custom_ge_quality_contract_path() -> Path:
    return _fixture_contract_path("quality", "custom_ge_quality.yaml")


@pytest.fixture
def sample_custom_ge_quality_contract_dict(sample_custom_ge_quality_contract_path: Path) -> dict[str, Any]:
    return _load_yaml_fixture(sample_custom_ge_quality_contract_path)


@pytest.fixture
def sample_custom_ge_quality_contract_model(
    sample_custom_ge_quality_contract_dict: dict[str, Any]
) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_custom_ge_quality_contract_dict)


@pytest.fixture
def sample_temporal_types_contract_path() -> Path:
    return _fixture_contract_path("odcs", "temporal_and_scalar_types.yaml")


@pytest.fixture
def sample_temporal_types_contract_dict(sample_temporal_types_contract_path: Path) -> dict[str, Any]:
    return _load_yaml_fixture(sample_temporal_types_contract_path)


@pytest.fixture
def sample_temporal_types_contract_model(
    sample_temporal_types_contract_dict: dict[str, Any]
) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_temporal_types_contract_dict)


@pytest.fixture
def sample_nested_types_contract_path() -> Path:
    return _fixture_contract_path("odcs", "nested_types.yaml")


@pytest.fixture
def sample_nested_types_contract_dict(sample_nested_types_contract_path: Path) -> dict[str, Any]:
    return _load_yaml_fixture(sample_nested_types_contract_path)


@pytest.fixture
def sample_nested_types_contract_model(sample_nested_types_contract_dict: dict[str, Any]) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_nested_types_contract_dict)


@pytest.fixture
def sample_numeric_precision_contract_path() -> Path:
    return _fixture_contract_path("odcs", "numeric_precision.yaml")


@pytest.fixture
def sample_numeric_precision_contract_dict(sample_numeric_precision_contract_path: Path) -> dict[str, Any]:
    return _load_yaml_fixture(sample_numeric_precision_contract_path)


@pytest.fixture
def sample_numeric_precision_contract_model(
    sample_numeric_precision_contract_dict: dict[str, Any]
) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_numeric_precision_contract_dict)


@pytest.fixture
def sample_constraint_quality_contract_path() -> Path:
    return _fixture_contract_path("quality", "constraint_friendly_quality.yaml")


@pytest.fixture
def sample_constraint_quality_contract_dict(sample_constraint_quality_contract_path: Path) -> dict[str, Any]:
    return _load_yaml_fixture(sample_constraint_quality_contract_path)


@pytest.fixture
def sample_constraint_quality_contract_model(
    sample_constraint_quality_contract_dict: dict[str, Any]
) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_constraint_quality_contract_dict)


@pytest.fixture
def sample_enum_constraint_contract_path() -> Path:
    return _fixture_contract_path("odcs", "enum_and_constraint_types.yaml")


@pytest.fixture
def sample_enum_constraint_contract_dict(sample_enum_constraint_contract_path: Path) -> dict[str, Any]:
    return _load_yaml_fixture(sample_enum_constraint_contract_path)


@pytest.fixture
def sample_enum_constraint_contract_model(
    sample_enum_constraint_contract_dict: dict[str, Any]
) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_enum_constraint_contract_dict)


@pytest.fixture
def sample_type_narrowing_base_contract_path() -> Path:
    return _fixture_contract_path("lifecycle", "type_narrowing_base.yaml")


@pytest.fixture
def sample_type_narrowing_base_contract_dict(sample_type_narrowing_base_contract_path: Path) -> dict[str, Any]:
    return _load_yaml_fixture(sample_type_narrowing_base_contract_path)


@pytest.fixture
def sample_type_narrowing_base_contract_model(
    sample_type_narrowing_base_contract_dict: dict[str, Any]
) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_type_narrowing_base_contract_dict)


@pytest.fixture
def sample_type_narrowing_target_contract_path() -> Path:
    return _fixture_contract_path("lifecycle", "type_narrowing_target.yaml")


@pytest.fixture
def sample_type_narrowing_target_contract_dict(sample_type_narrowing_target_contract_path: Path) -> dict[str, Any]:
    return _load_yaml_fixture(sample_type_narrowing_target_contract_path)


@pytest.fixture
def sample_type_narrowing_target_contract_model(
    sample_type_narrowing_target_contract_dict: dict[str, Any]
) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(sample_type_narrowing_target_contract_dict)


@pytest.fixture
def spark_ddl_adls2_product_dir() -> Path:
    return _fixture_path("ddl", "spark", "adls2_product")


@pytest.fixture
def spark_ddl_finance_product_dir() -> Path:
    return _fixture_path("ddl", "spark", "finance_product")


@pytest.fixture
def spark_ddl_risk_product_dir() -> Path:
    return _fixture_path("ddl", "spark", "risk_product")


@pytest.fixture
def delta_finance_transactions_schema_path() -> Path:
    return _fixture_path("delta", "finance_transactions_schema.json")


@pytest.fixture
def delta_minimal_schema_path() -> Path:
    return _fixture_path("delta", "minimal_table_schema.json")


@pytest.fixture
def delta_orders_schema_path() -> Path:
    return _fixture_path("delta", "orders_schema.json")


@pytest.fixture
def spark_ddl_orders_product_dir() -> Path:
    return _fixture_path("ddl", "spark", "orders_product")
