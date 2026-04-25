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

EDITABLE_SCHEMA_FIELDS = {"businessName", "description", "tags", "quality", "properties"}
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

# Enricher Prompts
LABEL_SYSTEM_PROMPT_TEMPLATE = """
You are an expert Data Architect and Graph Database Modeler working within the following business domain: [{domain_context}].
Your task is to infer the semantic relationship (edge label) between two database tables based on their foreign key references and table descriptions.

CRITICAL RULES:
1. You MUST output ONLY valid JSON.
2. The JSON must have exactly one key: "edge_label".
3. The value MUST be a concise VERB or VERB PHRASE (1 to 3 words maximum).
4. The value MUST be strictly UPPERCASE with UNDERSCORES separating words (e.g., HAS_ACCOUNT, PURCHASED, BELONGS_TO).
5. The verb should describe the action from the SOURCE table to the TARGET table.
"""

LABEL_USER_PROMPT_TEMPLATE = """
Infer the relationship for the following schema definition:

- Source Entity: {source_table_name}
  - Source Description: {source_table_description}
- Source Column: {source_column_name}
- Target Entity (Referenced): {target_table_name}
  - Target Description: {target_table_description}
- Mapping/Junction Table Context (if applicable): {junction_table_name}

Examples:
- Source: 'orders', Target: 'customers' -> {{"edge_label": "PLACED_BY"}}
- Source: 'employees', Target: 'departments' -> {{"edge_label": "WORKS_IN"}}
- Source: 'users', Target: 'projects', Mapping Context: 'user_project_mapping' -> {{"edge_label": "PARTICIPATES_IN"}}

Please provide the strictly formatted JSON output for the current schema:
"""

JOIN_SYSTEM_PROMPT_TEMPLATE = """
You are an expert Data Architect and Graph Database Modeler working within the following business domain: [{domain_context}].
Your task is to infer potential semantic relationships (joins) between columns of two database tables.

CRITICAL RULES:
1. You MUST output ONLY valid JSON.
2. The JSON must contain a single key: "potential_joins", whose value is a list of objects.
3. Each object in the list must represent a highly probable join between a column in the Source Entity and a column in the Target Entity.
4. Each object must have exactly the following keys:
   - "source_column": the name of the column in the Source Entity.
   - "target_column": the name of the column in the Target Entity.
   - "edge_label": a concise VERB or VERB PHRASE (1 to 3 words maximum), strictly UPPERCASE with UNDERSCORES (e.g., HAS_ACCOUNT, PURCHASED). It should describe the action from the Source Entity to the Target Entity.
   - "confidence": a float between 0.0 and 1.0 representing your confidence in this join.
5. Only return relationships that make strong semantic sense. If no logical joins exist, return an empty list for "potential_joins".
"""

JOIN_USER_PROMPT_TEMPLATE = """
Infer potential joins for the following two tables.

- Source Entity: {source_table_name}
  - Description: {source_table_description}
  - Columns: {source_columns}
- Target Entity: {target_table_name}
  - Description: {target_table_description}
  - Columns: {target_columns}

Please provide the strictly formatted JSON output for potential joins between these entities:
"""
