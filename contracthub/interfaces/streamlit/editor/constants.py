"""Shared constants for the ContractHub Streamlit editor."""

from __future__ import annotations

TYPE_OPTIONS = ["string", "int", "bigint", "decimal", "boolean", "timestamp"]
LIFECYCLE_OPTIONS = ["draft", "active", "deprecated"]
CONTRACT_STATUS_OPTIONS = ["draft", "active", "deprecated", "retired"]
QUALITY_TYPE_OPTIONS = ["GE", "SQL"]
QUALITY_SEVERITY_OPTIONS = ["warning", "error"]
CHANGE_FILTER_OPTIONS = ["ALL", "BREAKING", "ADDED", "MODIFIED", "DEPRECATED"]
TABLE_RULE_COLUMN = "__table__"

# ODCS v3.1.0 treats typing, nullability, and nested structure as technical schema metadata.
TECHNICAL_PROPERTY_KEYS = {
    "name",
    "physicalName",
    "logicalType",
    "physicalType",
    "required",
    "items",
    "additionalProperties",
    "logicalTypeOptions",
    "format",
    "pattern",
}

# Business-facing metadata remains editable in the editor.
BUSINESS_PROPERTY_KEYS = {"businessName", "description", "examples", "tags"}
