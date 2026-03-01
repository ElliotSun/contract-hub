from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from datacontract.export.exporter import ExportFormat
from datacontract.export.exporter_factory import exporter_factory
from open_data_contract_standard.model import (
    CustomProperty,
    OpenDataContractStandard,
    SchemaProperty,
    Server,
)

ContractInput = Union[OpenDataContractStandard, Dict[str, Any], str, Path]


class SparkSqlContractExporter:
    """SDK-style exporter for Spark/Unity table DDL generation.

    This exporter delegates SQL generation to datacontract-cli's SQL exporter
    and applies a small compatibility layer:
    - Uses physical names for table/column DDL when available.
    - Bridges ODCS `physicalType` into exporter config expected by datacontract.
    - Supports Unity Catalog prefixing through temporary databricks server config.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def export_contract(
        self,
        contract: ContractInput,
        *,
        unity_catalog: Optional[str] = None,
        unity_schema: Optional[str] = None,
        unity_server_name: str = "contracthub_target",
        use_physical_names: bool = True,
    ) -> str:
        if bool(unity_catalog) != bool(unity_schema):
            raise ValueError("unity_catalog and unity_schema must be provided together")

        contract_model = _load_contract_model(contract)
        prepared_contract = _prepare_for_sql_export(
            contract_model,
            use_physical_names=use_physical_names,
        )

        export_args: Dict[str, Any] = {}
        if unity_catalog and unity_schema:
            _upsert_unity_server(
                prepared_contract,
                server_name=unity_server_name,
                catalog=unity_catalog,
                schema_name=unity_schema,
            )
            export_args["server"] = unity_server_name
        else:
            # Avoid inheriting non-databricks servers (e.g., postgres) for Spark DDL generation.
            prepared_contract.servers = None

        exporter = exporter_factory.create(ExportFormat.sql)
        return exporter.export(
            data_contract=prepared_contract,
            schema_name="all",
            server=None,
            sql_server_type="databricks",
            export_args=export_args,
        )


def export_contract_to_spark_sql(
    contract: ContractInput,
    *,
    unity_catalog: Optional[str] = None,
    unity_schema: Optional[str] = None,
    unity_server_name: str = "contracthub_target",
    use_physical_names: bool = True,
) -> str:
    exporter = SparkSqlContractExporter()
    return exporter.export_contract(
        contract=contract,
        unity_catalog=unity_catalog,
        unity_schema=unity_schema,
        unity_server_name=unity_server_name,
        use_physical_names=use_physical_names,
    )


def _load_contract_model(contract: ContractInput) -> OpenDataContractStandard:
    if isinstance(contract, OpenDataContractStandard):
        return OpenDataContractStandard.model_validate(contract.model_dump(by_alias=True, exclude_none=True))

    if isinstance(contract, dict):
        return OpenDataContractStandard.model_validate(deepcopy(contract))

    path = Path(contract).expanduser().resolve()
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Contract file must contain a YAML mapping object")
    return OpenDataContractStandard.model_validate(payload)


def _prepare_for_sql_export(
    contract: OpenDataContractStandard,
    *,
    use_physical_names: bool,
) -> OpenDataContractStandard:
    prepared = OpenDataContractStandard.model_validate(contract.model_dump(by_alias=True, exclude_none=True))

    for schema_obj in prepared.schema_ or []:
        if use_physical_names and schema_obj.physicalName:
            schema_obj.name = schema_obj.physicalName

        for prop in _iter_schema_properties(schema_obj.properties or []):
            if use_physical_names and prop.physicalName:
                prop.name = prop.physicalName
            _ensure_physical_type_custom_property(prop)

    return prepared


def _iter_schema_properties(properties: list[SchemaProperty]) -> list[SchemaProperty]:
    visited: list[SchemaProperty] = []
    stack = list(properties)
    while stack:
        item = stack.pop()
        visited.append(item)
        if item.properties:
            stack.extend(item.properties)
        if item.items is not None:
            stack.append(item.items)
    return visited


def _ensure_physical_type_custom_property(prop: SchemaProperty) -> None:
    if not prop.physicalType:
        return
    existing = prop.customProperties or []
    if any(cp.property == "physicalType" for cp in existing):
        return
    existing.append(CustomProperty(property="physicalType", value=prop.physicalType))
    prop.customProperties = existing


def _upsert_unity_server(
    contract: OpenDataContractStandard,
    *,
    server_name: str,
    catalog: str,
    schema_name: str,
) -> None:
    servers = list(contract.servers or [])
    replacement = Server(
        **{
            "server": server_name,
            "type": "databricks",
            "catalog": catalog,
            "schema": schema_name,
        }
    )

    replaced = False
    for idx, server in enumerate(servers):
        if server.server == server_name:
            servers[idx] = replacement
            replaced = True
            break

    if not replaced:
        servers.append(replacement)
    contract.servers = servers
