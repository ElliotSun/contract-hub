"""Single implementation for Unity Catalog contract imports.

This module consolidates the Unity import logic that was previously duplicated
in ``contracthub.interfaces.cli`` and ``contracthub.orchestrator.pipeline``.

Environment variable mutation is isolated inside a context manager so it cannot
leak into concurrent operations.
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Iterator

from datacontract.data_contract import DataContract
from open_data_contract_standard.model import OpenDataContractStandard

from contracthub.importers.unity_relationships import (
    enrich_unity_contract_relationships,
)
from contracthub.importers.unity_lineage import enrich_unity_lineage

LOGGER = logging.getLogger(__name__)


@contextlib.contextmanager
def _databricks_env(workspace_url: str, token: str) -> Iterator[None]:
    """Temporarily set Databricks env vars and restore them on exit.

    This context manager ensures the process-global environment is restored
    even when the import raises, preventing credential leaks across calls.
    """
    env_keys = (
        "DATACONTRACT_DATABRICKS_SERVER_HOSTNAME",
        "DATACONTRACT_DATABRICKS_TOKEN",
    )
    backup = {key: os.environ.get(key) for key in env_keys}
    os.environ["DATACONTRACT_DATABRICKS_SERVER_HOSTNAME"] = workspace_url
    os.environ["DATACONTRACT_DATABRICKS_TOKEN"] = token
    try:
        yield
    finally:
        for key, value in backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def import_unity_contract(
    *,
    table_fqn: str,
    workspace_url: str | None,
    token: str | None,
    sql_http_path: str | None = None,
    extract_lineage: bool = False,
) -> OpenDataContractStandard:
    """Import a Unity Catalog contract using datacontract-cli's unity importer.

    Raises ``ValueError`` when required credentials are missing.
    """
    if not workspace_url or not token:
        raise ValueError(
            "workspace_url and token are required for Unity Catalog imports"
        )

    LOGGER.info("Importing Unity Catalog contract: %s", table_fqn)
    with _databricks_env(workspace_url, token):
        imported = DataContract.import_from_source(
            format="unity",
            source=None,
            unity_table_full_name=[table_fqn],
        )
        enriched = enrich_unity_contract_relationships(
            imported,
            table_fqn=table_fqn,
            workspace_url=workspace_url,
            token=token,
        )
        if extract_lineage:
            enriched = enrich_unity_lineage(
                enriched,
                table_fqn=table_fqn,
                workspace_url=workspace_url,
                token=token,
                sql_http_path=sql_http_path,
            )
        return enriched
