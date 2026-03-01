You are working on the ContractHub platform.

This skill defines the permanent architecture rules for the system.

These rules ALWAYS override task-level instructions.

CORE PURPOSE

ContractHub is an enterprise data contract control plane that manages Open Data Contract Standard (ODCS) contracts across:

Databricks Unity Catalog

Delta Lake

SparkSQL pipelines

Great Expectations validation

GitOps CI/CD workflows

ARCHITECTURE PRINCIPLES

The system must follow strict layered architecture:

1. Import Layer

Responsible ONLY for converting external sources into ODCS contracts.

Importers must:

Be stateless

Be idempotent

Contain NO merge logic

Contain NO governance rules

Contain NO CI/CD behavior

Importers only perform mapping:

External Metadata → ODCS Contract

2. Core Contract Model

ODCS YAML is the single canonical representation.

All modules must operate on this model.

No alternative internal schema representations are allowed.

3. Lifecycle Governance Layer

All contract lifecycle logic belongs exclusively to the governance engine.

This includes:

Breaking change detection

LifecycleStatus evaluation

Auto-deprecation rules

Merge policy enforcement

Importers must never implement lifecycle logic.

4. Export Layer

Exporters convert contracts into operational artifacts such as:

Great Expectations suites

CI validation configs

Exporters must not modify contracts.

5. Orchestration Layer

Orchestrators coordinate workflows:

Import → Merge → Export → PR

They must not contain business logic.

6. DevOps Layer

Handles Git integration:

PR creation

Version management

Audit metadata

TECHNICAL CONSTRAINTS

Python 3.11

Fully typed

Modular design

Testable components

Pure Python where possible

No Spark dependencies in importers

datacontract-cli must be reused

DESIGN GUARDRAILS

NEVER:

Put merge logic in importers

Reimplement datacontract-cli features

Mix governance logic with ingestion logic

Create monolithic modules

ALWAYS:

Separate responsibilities

Favor composable services

Maintain clean module boundaries

END OF SKILL