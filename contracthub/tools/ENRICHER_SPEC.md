# ContractHub Enricher Specification

This document details the functionality, prompts, and behaviors of the `ContractEnricher` tool used in ContractHub.

The main purpose of the `ContractEnricher` is to leverage a Large Language Model (LLM) to infer semantic relationships between database tables.

## Context and Philosophy

In enterprise environments, explicit foreign keys are often missing from the physical database schema. The `ContractEnricher` bridges this gap by statically analyzing Open Data Contract Standard (ODCS) YAML configurations, iterating through entities (tables) and properties (columns), and prompting an LLM to predict missing relationships based on semantic context (table descriptions, column names).

These inferred relationships are written back directly into the ODCS contract under the corresponding property's `relationships` array, and enriched with `customProperties` to signify their provenance. This aligns directly with the `GraphExporter` behavior defined in `GRAPH_EXPORT_SPEC.md`.

## Workflows

### Potential Join Inference

To accurately and efficiently infer potential joins between tables that lack explicitly defined foreign keys, the `ContractEnricher` evaluates tables in pairs.

#### Pairing Strategy
* The enricher extracts all tables (`SchemaObject`) from the contract.
* It evaluates each pair of tables (e.g., Table A and Table B).
* Existing relationships (whether defined at the property level or the schema level) are respected. If a column already defines a relationship, it is **excluded** from the LLM prompt to prevent redundant or conflicting inferences.
* The columns of Table A and Table B that *do not* have existing relationships are gathered and sent to the LLM.

#### Prompt Engineering
The system prompt establishes the persona and strictly enforces a JSON output format. It uses a `temperature=0.2` to encourage deterministic but slightly creative association building.

**System Prompt Example:**
```text
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
```

**User Prompt Example:**
```text
Infer potential joins for the following two tables.

- Source Entity: orders
  - Description: Contains customer order records.
  - Columns: id, status, created_at, customer_id
- Target Entity: customers
  - Description: Contains customer profiles.
  - Columns: id, first_name, last_name, email

Please provide the strictly formatted JSON output for potential joins between these entities:
```

#### JSON Output Structure
The LLM is expected to return the inferred relationships in the following structure:
```json
{
  "potential_joins": [
    {
      "source_column": "customer_id",
      "target_column": "id",
      "edge_label": "PLACED_BY",
      "confidence": 0.95
    }
  ]
}
```

#### Updating the ODCS Model
When the LLM returns a valid `potential_join`, the `ContractEnricher` modifies the ODCS model as follows:
1. It locates the `source_column` in the Source Table.
2. It creates a new `Relationship` object in that column's `relationships` array.
3. The `to` attribute is set to `{Target Table Name}.{target_column}` (Short Reference Notation).
4. The following `customProperties` are appended to the `Relationship` to denote its provenance:
   - `graph_semantic.edge_label`: Set to the inferred `edge_label`.
   - `graph_semantic.provenance`: Strictly set to `"LLM_INFERRED"`.
   - `graph_semantic.confidence`: Set to the inferred `confidence` float.

The resulting ODCS YAML snippet will look like this:
```yaml
      relationships:
        - to: customers.id
          customProperties:
            - property: graph_semantic.edge_label
              value: PLACED_BY
            - property: graph_semantic.provenance
              value: LLM_INFERRED
            - property: graph_semantic.confidence
              value: 0.95
```

This perfectly aligns with downstream artifact generation (such as Cypher and JSON Graph Exports) which look for these exact fields.
