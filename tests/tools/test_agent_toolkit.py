"""Unit tests for contracthub.tools.agent_toolkit.

All tests mock the underlying ContractHub core modules to keep this suite
fast and independent of filesystem / LLM / Spark dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from contracthub.tools.agent_toolkit import (
    ToolResult,
    analyze_changes,
    export_graph,
    export_sql,
    load_contract,
    validate_contract,
)

# Path to a real fixture contract for smoke-path tests
FIXTURE_CONTRACT = str(
    Path(__file__).resolve().parents[1] / "fixtures" / "contracts" / "odcs" / "full_sample.yaml"
)
NONEXISTENT_PATH = "/tmp/contracthub_does_not_exist_xyz.yaml"


# ---------------------------------------------------------------------------
# ToolResult
# ---------------------------------------------------------------------------


class TestToolResult:
    def test_success_result(self) -> None:
        r = ToolResult(success=True, data={"key": "value"})
        assert r.success is True
        assert r.data == {"key": "value"}
        assert r.error is None

    def test_failure_result(self) -> None:
        r = ToolResult(success=False, error="something went wrong")
        assert r.success is False
        assert r.error == "something went wrong"
        assert r.data is None


# ---------------------------------------------------------------------------
# load_contract
# ---------------------------------------------------------------------------


class TestLoadContract:
    def test_success(self) -> None:
        result = load_contract(FIXTURE_CONTRACT)
        assert result.success is True
        assert isinstance(result.data, dict)
        assert result.error is None

    def test_file_not_found(self) -> None:
        result = load_contract(NONEXISTENT_PATH)
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error.lower() or "no such" in result.error.lower()

    def test_load_exception_returns_failure(self) -> None:
        with patch(
            "contracthub.core.loader.load_contract",
            side_effect=RuntimeError("parse error"),
        ):
            result = load_contract(FIXTURE_CONTRACT)
            assert result.success is False
            assert result.error is not None



# ---------------------------------------------------------------------------
# validate_contract
# ---------------------------------------------------------------------------


class TestValidateContract:
    def test_valid_contract(self) -> None:
        result = validate_contract(FIXTURE_CONTRACT)
        assert result.success is True
        assert isinstance(result.data, dict)
        assert "valid" in result.data
        assert "issues" in result.data
        assert isinstance(result.data["issues"], list)

    def test_file_not_found(self) -> None:
        result = validate_contract(NONEXISTENT_PATH)
        assert result.success is False
        assert result.error is not None

    def test_invalid_contract_returns_issues(self) -> None:
        """A contract with bad quality rules should still succeed as a tool call
        but report valid=False with issues."""
        mock_issue = MagicMock()
        mock_issue.path = "schema[0].quality"
        mock_issue.message = "missing required field"
        mock_issue.severity = "error"

        mock_report = MagicMock()
        mock_report.valid = False
        mock_report.issues = [mock_issue]

        mock_odcs = MagicMock()

        with patch("contracthub.core.loader.load_contract", return_value=mock_odcs):
            with patch(
                "contracthub.core.validator.ContractValidator.validate",
                return_value=mock_report,
            ):
                result = validate_contract(FIXTURE_CONTRACT)

        assert result.success is True  # tool ran OK
        assert result.data["valid"] is False
        assert len(result.data["issues"]) == 1
        assert result.data["issues"][0]["severity"] == "error"

    def test_validator_crash_returns_failure(self) -> None:
        mock_odcs = MagicMock()
        with patch("contracthub.core.loader.load_contract", return_value=mock_odcs):
            with patch(
                "contracthub.core.validator.ContractValidator.validate",
                side_effect=RuntimeError("validator exploded"),
            ):
                result = validate_contract(FIXTURE_CONTRACT)
        assert result.success is False
        assert "Validation engine error" in result.error


# ---------------------------------------------------------------------------
# analyze_changes
# ---------------------------------------------------------------------------


class TestAnalyzeChanges:
    def test_base_not_found(self) -> None:
        result = analyze_changes(NONEXISTENT_PATH, FIXTURE_CONTRACT)
        assert result.success is False
        assert "Base contract not found" in result.error

    def test_modified_not_found(self) -> None:
        result = analyze_changes(FIXTURE_CONTRACT, NONEXISTENT_PATH)
        assert result.success is False
        assert "Modified contract not found" in result.error

    def test_success_no_breaking_changes(self) -> None:
        """Comparing a contract to itself should produce no breaking changes."""
        result = analyze_changes(FIXTURE_CONTRACT, FIXTURE_CONTRACT)
        assert result.success is True, result.error
        data = result.data
        assert isinstance(data["breaking_changes"], list)
        assert isinstance(data["merge_conflicts"], list)
        assert isinstance(data["deprecated_schemas"], list)
        assert isinstance(data["deprecated_properties"], dict)
        assert isinstance(data["id_violation"], bool)
        assert isinstance(data["version_violation"], bool)
        assert isinstance(data["policy_valid"], bool)

    def test_engine_crash_returns_failure(self) -> None:
        mock_odcs = MagicMock()
        with patch("contracthub.core.loader.load_contract", return_value=mock_odcs):
            with patch(
                "contracthub.lifecycle.merge_engine.ContractMergeEngine.analyze",
                side_effect=RuntimeError("engine blew up"),
            ):
                result = analyze_changes(FIXTURE_CONTRACT, FIXTURE_CONTRACT)
        assert result.success is False
        assert "Change analysis failed" in result.error


# ---------------------------------------------------------------------------
# export_sql
# ---------------------------------------------------------------------------


class TestExportSql:
    def test_success(self) -> None:
        result = export_sql(FIXTURE_CONTRACT, sql_server_type="databricks")
        assert result.success is True
        assert "ddl" in result.data
        assert isinstance(result.data["ddl"], str)
        assert len(result.data["ddl"]) > 0

    def test_file_not_found(self) -> None:
        result = export_sql(NONEXISTENT_PATH)
        assert result.success is False
        assert result.error is not None

    def test_exporter_crash_returns_failure(self) -> None:
        mock_odcs = MagicMock()
        with patch("contracthub.core.loader.load_contract", return_value=mock_odcs):
            with patch(
                "contracthub.exporters.sql_exporter.SparkSqlContractExporter.export_contract",
                side_effect=RuntimeError("DDL generation failed"),
            ):
                result = export_sql(FIXTURE_CONTRACT)
        assert result.success is False
        assert "SQL export failed" in result.error


# ---------------------------------------------------------------------------
# export_graph
# ---------------------------------------------------------------------------


class TestExportGraph:
    def test_success_json(self) -> None:
        result = export_graph(FIXTURE_CONTRACT, output_format="json")
        assert result.success is True
        assert "graph" in result.data
        assert isinstance(result.data["graph"], str)
        # Should be valid JSON
        import json
        parsed = json.loads(result.data["graph"])
        assert "nodes" in parsed or "edges" in parsed

    def test_success_cypher(self) -> None:
        result = export_graph(FIXTURE_CONTRACT, output_format="cypher")
        assert result.success is True
        assert "graph" in result.data
        assert isinstance(result.data["graph"], str)

    def test_file_not_found(self) -> None:
        result = export_graph(NONEXISTENT_PATH)
        assert result.success is False
        assert result.error is not None

    def test_exporter_crash_returns_failure(self) -> None:
        mock_odcs = MagicMock()
        with patch("contracthub.core.loader.load_contract", return_value=mock_odcs):
            with patch(
                "contracthub.exporters.graph_exporter.GraphExporter.export",
                side_effect=RuntimeError("graph export crashed"),
            ):
                result = export_graph(FIXTURE_CONTRACT)
        assert result.success is False
        assert "Graph export failed" in result.error
