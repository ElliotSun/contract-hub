from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from datacontract.export.exporter import ExportFormat
from datacontract.export.exporter_factory import exporter_factory
from open_data_contract_standard.model import OpenDataContractStandard

from contracthub.utils.schema_utils import contract_to_model

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class GreatExpectationsExporter:
    """Export ODCS contracts to Great Expectations suites via datacontract-cli."""

    def generate_suite(
        self,
        contract: OpenDataContractStandard | dict[str, Any] | str,
        *,
        schema_name: str = "all",
        suite_name: str | None = None,
    ) -> Any:
        model = contract_to_model(contract)
        return generate_expectation_suite(model, schema_name=schema_name, suite_name=suite_name)

    def export_to_path(
        self,
        contract: OpenDataContractStandard | dict[str, Any] | str,
        output_path: str,
        *,
        schema_name: str = "all",
        suite_name: str | None = None,
    ) -> Path:
        suite = self.generate_suite(contract, schema_name=schema_name, suite_name=suite_name)
        path = Path(output_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        if hasattr(suite, "to_json_dict"):
            payload = suite.to_json_dict()
        elif hasattr(suite, "to_dict"):
            payload = suite.to_dict()
        else:
            payload = _to_json_safe_dict(suite)

        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path


def generate_expectation_suite(
    contract: OpenDataContractStandard,
    schema_name: str = "all",
    suite_name: Optional[str] = None,
) -> Any:
    """Generate a Great Expectations ExpectationSuite using datacontract-cli exporter."""
    exporter = exporter_factory.create(ExportFormat.great_expectations)
    exported = exporter.export(
        data_contract=contract,
        schema_name=schema_name,
        server=None,
        sql_server_type="auto",
        export_args={"engine": "spark", "suite_name": suite_name},
    )
    suite_dict = json.loads(exported)
    return _suite_dict_to_expectation_suite(suite_dict)


def _suite_dict_to_expectation_suite(suite_dict: Dict[str, Any]) -> Any:
    ExpectationSuite, ExpectationConfiguration = _load_ge_suite_classes()

    suite_name = suite_dict.get("name") or "contracthub_suite"
    expectation_suite = _create_suite_object(ExpectationSuite, suite_name)

    for expectation in suite_dict.get("expectations", []):
        if not isinstance(expectation, dict):
            continue
        expectation_type = expectation.get("expectation_type") or expectation.get("type")
        if not expectation_type:
            continue

        config = ExpectationConfiguration(
            expectation_type=expectation_type,
            kwargs=expectation.get("kwargs", {}),
            meta=expectation.get("meta", {}),
        )
        _add_expectation(expectation_suite, config)

    return expectation_suite


def _create_suite_object(ExpectationSuite: Any, suite_name: str) -> Any:
    try:
        return ExpectationSuite(expectation_suite_name=suite_name)
    except TypeError:
        return ExpectationSuite(name=suite_name)


def _add_expectation(expectation_suite: Any, config: Any) -> None:
    if hasattr(expectation_suite, "add_expectation"):
        try:
            expectation_suite.add_expectation(expectation_configuration=config)
            return
        except TypeError:
            expectation_suite.add_expectation(config)
            return

    expectations = getattr(expectation_suite, "expectations", None)
    if isinstance(expectations, list):
        expectations.append(config)
        return
    raise TypeError("Unsupported ExpectationSuite object: cannot add expectations")


def _load_ge_suite_classes() -> tuple[Any, Any]:
    try:
        from great_expectations.core import ExpectationConfiguration, ExpectationSuite

        return ExpectationSuite, ExpectationConfiguration
    except Exception as first_exc:
        try:
            from great_expectations.core.expectation_configuration import ExpectationConfiguration
            from great_expectations.core.expectation_suite import ExpectationSuite

            return ExpectationSuite, ExpectationConfiguration
        except Exception as second_exc:
            try:
                from great_expectations.expectations.expectation_configuration import ExpectationConfiguration
                from great_expectations.core.expectation_suite import ExpectationSuite

                return ExpectationSuite, ExpectationConfiguration
            except Exception as third_exc:
                LOGGER.error(
                    "Great Expectations import failed: %s ; %s ; %s",
                    first_exc,
                    second_exc,
                    third_exc,
                )
                raise RuntimeError(
                    "great_expectations is required to generate expectation suites at runtime"
                ) from third_exc


def _to_json_safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return {k: v for k, v in vars(value).items() if not k.startswith("_")}
    return {"value": str(value)}
