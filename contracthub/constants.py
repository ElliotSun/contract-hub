"""Shared ContractHub constants.

This module is the single source of truth for editor, draft-normalization,
and exporter constants that are reused across layers.
"""

from __future__ import annotations

TYPE_OPTIONS = ["string", "int", "bigint", "decimal", "boolean", "timestamp"]
LIFECYCLE_OPTIONS = ["draft", "active", "deprecated"]
CONTRACT_STATUS_OPTIONS = ["draft", "active", "deprecated", "retired"]
QUALITY_TYPE_OPTIONS = ["GE", "SQL"]
QUALITY_SEVERITY_OPTIONS = ["warning", "error"]
CHANGE_FILTER_OPTIONS = ["ALL", "BREAKING", "ADDED", "MODIFIED", "DEPRECATED"]

TABLE_RULE_COLUMN = "__table__"
DEFAULT_QUALITY_TYPE = QUALITY_TYPE_OPTIONS[0]
DEFAULT_QUALITY_SEVERITY = QUALITY_SEVERITY_OPTIONS[0]

READ_ONLY_CONTRACT_FIELDS = (
    "apiVersion",
    "kind",
    "id",
    "name",
    "status",
    "domain",
    "dataProduct",
    "tenant",
    "servers",
)

EDITABLE_SCHEMA_FIELDS = {
    "businessName",
    "description",
    "tags",
    "quality",
    "properties",
}
EDITABLE_PROPERTY_FIELDS = {
    "businessName",
    "description",
    "examples",
    "tags",
    "classification",
    "transformDescription",
    "quality",
    "properties",
    "items",
}

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

BUSINESS_PROPERTY_KEYS = {"businessName", "description", "examples", "tags"}

UNITY_RELATIONSHIPS_IMPORTED_KEY = "contracthub.unity.relationshipsImported"
UNITY_RELATIONSHIPS_COUNT_KEY = "contracthub.unity.relationshipsCount"
UNITY_RELATIONSHIPS_REASON_KEY = "contracthub.unity.relationshipsReason"
UNITY_CONSTRAINT_NAME_KEY = "contracthub.unity.constraintName"

