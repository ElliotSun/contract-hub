"""ContractHub Agent Toolkit.

A framework-agnostic Tool SDK that wraps ContractHub's deterministic core
capabilities into a stable, typed API surface for use by AI agents.

Design principles:
- **Thin wrapper only**: no business logic lives here; all logic is in the
  underlying core, lifecycle, and exporter modules.
- **Uniform return type**: every tool returns ``ToolResult``, so agent
  frameworks never need to handle ContractHub-specific exception types.
- **Framework agnostic**: these are plain Python functions. Adapters for
  LangChain ``@tool``, LangGraph, CrewAI, or any other framework are the
  responsibility of the consumer (ContractHub-Agent), not this module.

Available tools
---------------
- ``load_contract``    – load an ODCS contract from a file path
- ``validate_contract`` – validate an ODCS contract against schema + quality rules
- ``analyze_changes``  – compare a base contract to a modified one, report breaking changes
- ``export_sql``       – generate Spark / Databricks DDL from a contract
- ``export_graph``     – generate a Cypher or JSON graph from a contract
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared return type
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ToolResult:
    """Uniform return envelope for all toolkit functions.

    Attributes
    ----------
    success:
        ``True`` when the tool completed without errors.
    data:
        Structured output produced by the tool on success.  The shape varies
        per tool and is documented in each function's docstring.
    error:
        Human-readable error message on failure.  ``None`` on success.
    """

    success: bool
    data: dict[str, Any] | str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Tool: load_contract
# ---------------------------------------------------------------------------


def load_contract(contract_path: str) -> ToolResult:
    """Load an ODCS contract from a file path and return its contents as a dict.

    Parameters
    ----------
    contract_path:
        Absolute or relative path to the ODCS YAML contract file.

    Returns
    -------
    ToolResult
        On success, ``data`` is a ``dict`` representation of the ODCS model.
        On failure, ``error`` describes the problem (file not found, parse
        error, etc.).

    Example agent usage::

        result = load_contract("contracts/orders.yaml")
        if result.success:
            contract_dict = result.data  # dict with ODCS fields
    """
    try:
        from contracthub.core.loader import load_contract as _load
        from contracthub.utils.schema_utils import contract_to_dict
    except ImportError as exc:
        return ToolResult(success=False, error=f"ContractHub import error: {exc}")

    try:
        odcs = _load(contract_path)
        data = contract_to_dict(odcs)
        return ToolResult(success=True, data=data)
    except FileNotFoundError:
        return ToolResult(
            success=False, error=f"Contract file not found: {contract_path}"
        )
    except Exception as exc:
        LOGGER.debug("load_contract failed for %s", contract_path, exc_info=True)
        return ToolResult(success=False, error=f"Failed to load contract: {exc}")


# ---------------------------------------------------------------------------
# Tool: validate_contract
# ---------------------------------------------------------------------------


def validate_contract(contract_path: str) -> ToolResult:
    """Validate an ODCS contract against the ContractHub schema + quality rules.

    Parameters
    ----------
    contract_path:
        Path to the ODCS YAML contract file to validate.

    Returns
    -------
    ToolResult
        On success (validation ran without crashing), ``data`` is::

            {
                "valid": bool,
                "issues": [
                    {"path": str, "message": str, "severity": str},
                    ...
                ]
            }

        ``success`` is ``True`` even when the contract itself is invalid — it
        reflects whether the *tool* ran successfully.  Check ``data["valid"]``
        to determine contract validity.
        On failure (e.g. the file cannot be read), ``success`` is ``False``.

    Example agent usage::

        result = validate_contract("contracts/orders.yaml")
        if result.success and not result.data["valid"]:
            issues = result.data["issues"]
            # feed issues back to self-correction loop
    """
    try:
        from contracthub.core.loader import load_contract as _load
        from contracthub.core.validator import ContractValidator
    except ImportError as exc:
        return ToolResult(success=False, error=f"ContractHub import error: {exc}")

    try:
        contract = _load(contract_path)
    except FileNotFoundError:
        return ToolResult(
            success=False, error=f"Contract file not found: {contract_path}"
        )
    except Exception as exc:
        LOGGER.debug("validate_contract: load failed for %s", contract_path, exc_info=True)
        return ToolResult(success=False, error=f"Failed to load contract: {exc}")

    try:
        report = ContractValidator().validate(contract)
        return ToolResult(
            success=True,
            data={
                "valid": report.valid,
                "issues": [
                    {
                        "path": issue.path,
                        "message": issue.message,
                        "severity": issue.severity,
                    }
                    for issue in report.issues
                ],
            },
        )
    except Exception as exc:
        LOGGER.debug("validate_contract: validation crashed for %s", contract_path, exc_info=True)
        return ToolResult(success=False, error=f"Validation engine error: {exc}")


# ---------------------------------------------------------------------------
# Tool: analyze_changes
# ---------------------------------------------------------------------------


def analyze_changes(
    base_contract_path: str,
    modified_contract_path: str,
) -> ToolResult:
    """Compare a base (existing/main) contract against a modified version.

    Runs the ContractHub lifecycle merge analysis to detect breaking changes,
    auto-deprecations, and merge conflicts between the two contracts.

    Parameters
    ----------
    base_contract_path:
        Path to the current/governed contract (the base, e.g. from ``contracts-main``).
    modified_contract_path:
        Path to the proposed/modified contract (e.g. a user draft or imported schema).

    Returns
    -------
    ToolResult
        On success, ``data`` is::

            {
                "breaking_changes": [
                    {"path": str, "message": str},
                    ...
                ],
                "merge_conflicts": [
                    {"path": str, "rule": str, "message": str},
                    ...
                ],
                "deprecated_schemas": [str, ...],
                "deprecated_properties": {"schema_id": [str, ...], ...},
                "id_violation": bool,
                "version_violation": bool,
                "policy_valid": bool,
            }

    Example agent usage::

        result = analyze_changes("contracts/orders.yaml", "drafts/orders.yaml")
        if result.success:
            breaking = result.data["breaking_changes"]
            # include in Proposal report for human review
    """
    try:
        from contracthub.core.loader import load_contract as _load
        from contracthub.lifecycle.merge_engine import ContractMergeEngine
        from contracthub.lifecycle.policy import evaluate_merge_policy
    except ImportError as exc:
        return ToolResult(success=False, error=f"ContractHub import error: {exc}")

    # Load both contracts
    try:
        base = _load(base_contract_path)
    except FileNotFoundError:
        return ToolResult(
            success=False,
            error=f"Base contract not found: {base_contract_path}",
        )
    except Exception as exc:
        return ToolResult(success=False, error=f"Failed to load base contract: {exc}")

    try:
        modified = _load(modified_contract_path)
    except FileNotFoundError:
        return ToolResult(
            success=False,
            error=f"Modified contract not found: {modified_contract_path}",
        )
    except Exception as exc:
        return ToolResult(
            success=False, error=f"Failed to load modified contract: {exc}"
        )

    # Run merge analysis (base = source/imported, modified = business/governed target)
    try:
        engine = ContractMergeEngine()
        analysis = engine.analyze(base_contract=modified, business_contract=base)
        merge_result = engine.merge(base_contract=modified, business_contract=base)
        policy = evaluate_merge_policy(base, merge_result.contract)
    except Exception as exc:
        LOGGER.debug("analyze_changes: engine error", exc_info=True)
        return ToolResult(success=False, error=f"Change analysis failed: {exc}")

    return ToolResult(
        success=True,
        data={
            "breaking_changes": [
                {"path": bc.path, "message": bc.message}
                for bc in policy.breaking_changes
            ],
            "merge_conflicts": [
                {
                    "path": c.path,
                    "rule": c.rule,
                    "message": c.message,
                }
                for c in analysis.conflicts
            ],
            "deprecated_schemas": sorted(analysis.deprecated_schemas),
            "deprecated_properties": {
                schema_id: sorted(props)
                for schema_id, props in analysis.deprecated_properties.items()
            },
            "id_violation": policy.id_violation,
            "version_violation": policy.version_violation,
            "policy_valid": policy.valid,
        },
    )


# ---------------------------------------------------------------------------
# Tool: export_sql
# ---------------------------------------------------------------------------


def export_sql(
    contract_path: str,
    *,
    sql_server_type: Literal["databricks", "spark", "postgres", "snowflake"] = "databricks",
    unity_catalog: str | None = None,
    unity_schema: str | None = None,
    use_physical_names: bool = True,
) -> ToolResult:
    """Generate SQL DDL from an ODCS contract.

    Parameters
    ----------
    contract_path:
        Path to the ODCS YAML contract.
    sql_server_type:
        Target SQL dialect.  Defaults to ``"databricks"``.
    unity_catalog:
        Optional Unity Catalog name (Databricks only).  Must be provided
        together with ``unity_schema``.
    unity_schema:
        Optional Unity Catalog schema name (Databricks only).
    use_physical_names:
        When ``True`` (default), column ``physicalName`` fields are used in
        the DDL instead of logical names.

    Returns
    -------
    ToolResult
        On success, ``data`` is::

            {"ddl": str}

        where ``ddl`` is the full SQL DDL string.

    Example agent usage::

        result = export_sql("contracts/orders.yaml", unity_catalog="prod", unity_schema="sales")
        if result.success:
            ddl = result.data["ddl"]
    """
    try:
        from contracthub.core.loader import load_contract as _load
        from contracthub.exporters.sql_exporter import SparkSqlContractExporter
    except ImportError as exc:
        return ToolResult(success=False, error=f"ContractHub import error: {exc}")

    try:
        contract = _load(contract_path)
    except FileNotFoundError:
        return ToolResult(
            success=False, error=f"Contract file not found: {contract_path}"
        )
    except Exception as exc:
        return ToolResult(success=False, error=f"Failed to load contract: {exc}")

    try:
        exporter = SparkSqlContractExporter()
        ddl = exporter.export_contract(
            contract,
            sql_server_type=sql_server_type,
            unity_catalog=unity_catalog,
            unity_schema=unity_schema,
            use_physical_names=use_physical_names,
        )
        return ToolResult(success=True, data={"ddl": ddl})
    except Exception as exc:
        LOGGER.debug("export_sql failed for %s", contract_path, exc_info=True)
        return ToolResult(success=False, error=f"SQL export failed: {exc}")


# ---------------------------------------------------------------------------
# Tool: export_graph
# ---------------------------------------------------------------------------


def export_graph(
    contract_path: str,
    *,
    output_format: Literal["cypher", "json"] = "json",
) -> ToolResult:
    """Export an ODCS contract as a graph (Cypher or JSON).

    The graph captures tables as nodes, columns as child nodes, and
    relationships (foreign keys / inferred joins) as edges.

    Parameters
    ----------
    contract_path:
        Path to the ODCS YAML contract.
    output_format:
        ``"cypher"`` to generate Neo4j Cypher CREATE statements, or
        ``"json"`` (default) for a ``{"nodes": [...], "edges": [...]}`` JSON.

    Returns
    -------
    ToolResult
        On success, ``data`` is::

            {"graph": str}   # the serialized graph string

    Example agent usage::

        result = export_graph("contracts/orders.yaml", output_format="json")
        if result.success:
            graph_json = result.data["graph"]
    """
    try:
        from contracthub.core.loader import load_contract as _load
        from contracthub.exporters.graph_exporter import GraphExporter
    except ImportError as exc:
        return ToolResult(success=False, error=f"ContractHub import error: {exc}")

    try:
        contract = _load(contract_path)
    except FileNotFoundError:
        return ToolResult(
            success=False, error=f"Contract file not found: {contract_path}"
        )
    except Exception as exc:
        return ToolResult(success=False, error=f"Failed to load contract: {exc}")

    try:
        exporter = GraphExporter()
        # GraphExporter uses export_args["format"] to select the serializer.
        # "graph" and "cypher" both route to CypherSerializer; "json" routes to JsonSerializer.
        export_args = {"format": output_format}
        graph_str = exporter.export(data_contract=contract, export_args=export_args)
        return ToolResult(success=True, data={"graph": graph_str})
    except Exception as exc:
        LOGGER.debug("export_graph failed for %s", contract_path, exc_info=True)
        return ToolResult(success=False, error=f"Graph export failed: {exc}")


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------

__all__ = [
    "ToolResult",
    "load_contract",
    "validate_contract",
    "analyze_changes",
    "export_sql",
    "export_graph",
]
