from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from open_data_contract_standard.model import CustomProperty, OpenDataContractStandard

from contracthub.importers.delta_importer import DeltaTableImporter
from contracthub.utils.schema_utils import contract_to_model


@dataclass(slots=True)
class UnityCatalogImporter:
    """Import ODCS contracts from Databricks Unity Catalog tables."""

    workspace_url: str
    token: str

    def import_contract(
        self,
        table_fqn: str,
        existing_contract: dict[str, Any] | None = None,
    ) -> OpenDataContractStandard:
        resolver = UCResolver(workspace_url=self.workspace_url, token=self.token)
        location = resolver.get_table_location(table_fqn)

        delta_importer = DeltaTableImporter(location)
        contract_dict = delta_importer.import_contract(existing_contract=existing_contract)

        table_name = table_fqn.split(".")[-1]
        contract_dict["name"] = table_name
        contract_dict["id"] = table_fqn.replace(".", "_").lower()

        schema_items = contract_dict.get("schema") or []
        if schema_items:
            schema_items[0]["name"] = table_name
            schema_items[0]["physicalName"] = table_fqn

        custom_properties = contract_dict.setdefault("customProperties", [])
        custom_properties.append(CustomProperty(property="contracthub.source", value="unity-catalog").model_dump())
        custom_properties.append(
            CustomProperty(property="contracthub.uc.tableFqn", value=table_fqn).model_dump()
        )
        custom_properties.append(
            CustomProperty(property="contracthub.uc.location", value=location).model_dump()
        )

        return contract_to_model(contract_dict)


class UCResolver:
    """Resolve Unity Catalog table names to underlying storage locations."""

    def __init__(self, workspace_url: str, token: str) -> None:
        self.workspace_url = workspace_url.rstrip("/")
        self.token = token
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_table_location(self, table_fqn: str) -> str:
        _validate_table_fqn(table_fqn)
        warehouse_id = os.getenv("DATABRICKS_SQL_WAREHOUSE_ID")
        if not warehouse_id:
            raise ValueError(
                "DATABRICKS_SQL_WAREHOUSE_ID is required to call Databricks SQL statement API."
            )

        statement_payload = {
            "statement": f"DESCRIBE DETAIL {table_fqn}",
            "warehouse_id": warehouse_id,
            "wait_timeout": "30s",
            "disposition": "INLINE",
        }
        self.logger.info("Resolving UC table location for %s", table_fqn)

        response = requests.post(
            f"{self.workspace_url}/api/2.0/sql/statements",
            headers=self._headers(),
            json=statement_payload,
            timeout=30,
        )
        _raise_for_status(response)
        payload = response.json()
        result_payload = self._await_result(payload)

        location = _extract_location_from_result(result_payload)
        if not location:
            raise RuntimeError(f"Could not resolve location for table {table_fqn}")
        return location

    def _await_result(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        status = (payload.get("status") or {}).get("state")
        statement_id = payload.get("statement_id")
        if status in {"SUCCEEDED"}:
            return payload

        if not statement_id:
            return payload

        while status in {"PENDING", "RUNNING"}:
            time.sleep(1.0)
            poll_response = requests.get(
                f"{self.workspace_url}/api/2.0/sql/statements/{statement_id}",
                headers=self._headers(),
                timeout=30,
            )
            _raise_for_status(poll_response)
            payload = poll_response.json()
            status = (payload.get("status") or {}).get("state")

        if status != "SUCCEEDED":
            raise RuntimeError(f"Databricks statement execution failed with state={status}")
        return payload

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }


def _validate_table_fqn(table_fqn: str) -> None:
    parts = [part.strip() for part in table_fqn.split(".")]
    if len(parts) != 3 or any(not part for part in parts):
        raise ValueError("table_fqn must be in format 'catalog.schema.table'")


def _raise_for_status(response: requests.Response) -> None:
    if response.ok:
        return
    try:
        details = response.json()
    except Exception:
        details = response.text
    raise RuntimeError(f"Databricks API request failed: status={response.status_code}, details={details}")


def _extract_location_from_result(payload: Dict[str, Any]) -> Optional[str]:
    result = payload.get("result") or {}
    rows = result.get("data_array") or []

    manifest = result.get("manifest") or {}
    schema_info = manifest.get("schema") or {}
    columns = schema_info.get("columns") or []
    location_idx = _location_column_index(columns)

    if location_idx is not None and rows:
        first_row = rows[0]
        if isinstance(first_row, list) and location_idx < len(first_row):
            value = first_row[location_idx]
            if isinstance(value, str) and value:
                return value

    for row in rows:
        if not isinstance(row, list):
            continue
        for value in row:
            if isinstance(value, str) and _looks_like_storage_uri(value):
                return value

    return None


def _location_column_index(columns: List[Dict[str, Any]]) -> Optional[int]:
    for idx, column in enumerate(columns):
        name = str(column.get("name") or "").lower()
        if name == "location":
            return idx
    return None


def _looks_like_storage_uri(value: str) -> bool:
    prefixes = ("dbfs:/", "s3://", "abfss://", "gs://", "file:/")
    return value.startswith(prefixes)
