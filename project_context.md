# ContractHub – Project Context

## 1. Project Overview

ContractHub is an enterprise-grade Data Contract orchestration framework designed to integrate data contracts directly into business workflows.

It extends the open-source datacontract-cli ecosystem by adding:

- Automated contract generation from SQL, Delta Lake, and Unity Catalog
- Contract lifecycle orchestration
- Great Expectations test generation
- GitOps integration with automated PR workflows
- Business-facing UI for contract editing

The goal is to make data contracts **operational**, not just documentation.

---

## 2. Core Philosophy

ContractHub follows these principles:

### Business-Integrated Contracts
Contracts are not owned only by data engineers.
They must be editable and reviewable by business stakeholders.

### Git as Source of Truth
All contracts live as YAML in Git.
No runtime metadata stores.

### Automation First
Everything should be auto-generated where possible:
- schema extraction
- expectation generation
- contract merging

### Python-Native
Avoid Spark runtime dependencies where possible.
Prefer pure Python solutions (Delta Lake, SQL parsing).

---

## 3. Key Architectural Layers

### 3.1 Import Layer (Discovery)

Responsible for generating contracts from data sources.

Supports:

- Spark SQL parsing from project folders
- Delta Lake metadata inspection (pure Python)
- Unity Catalog table discovery
- Contract merging workflows

Key design decisions:

- Folder name = Data Product Name
- SQL files define table structure
- Delta Lake replaces Spark importer runtime

---

### 3.2 Contract Lifecycle Layer

Handles contract evolution:

- Versioning
- Diff detection
- Merge automation
- PR generation

Business edits via UI must always result in:

Business Change → YAML Update → Auto PR → Git Review

---

### 3.3 Quality Layer

Integrates contract validation into data pipelines.

Uses datacontract-cli exporter to:

- Generate Great Expectations suites
- Integrate into Spark notebooks
- Enable runtime data quality checks

---

### 3.4 Orchestration Layer

Coordinates the end-to-end workflow:

Import → Merge → Validate → Export → PR → Notify

This is the “brain” of ContractHub.

---

### 3.5 Interface Layer

Provides human interaction surfaces:

- Streamlit UI for business users
- CLI for engineers
- GitHub Actions for automation

---

## 4. Relationship to datacontract-cli

ContractHub does NOT replace datacontract-cli.

It acts as an orchestration extension:

datacontract-cli provides:
- Contract models
- Import/export interfaces
- Validation engine

ContractHub provides:
- Enterprise workflow orchestration
- Automation pipelines
- Git integration
- UI layer

---

## 5. Major Functional Capabilities

### Import Capabilities

- Parse SparkSQL from folder
- Generate contract from Delta Lake tables
- Import Unity Catalog metadata

### Contract Management

- Merge contracts automatically
- Detect breaking changes
- Generate PRs for updates

### Data Quality Integration

- Generate Great Expectations suites
- Sync expectations with contracts

### Business Workflow Integration

- Allow contract editing through UI
- Automatically sync changes to Git

---

## 6. Target Users

### Data Engineers
- Generate contracts automatically
- Integrate validation into pipelines

### Data Platform Teams
- Govern contract lifecycle
- Enforce standards

### Business Stakeholders
- Review schemas
- Propose changes

---

## 7. Long-Term Vision

ContractHub aims to become:

"The GitOps platform for enterprise data contracts."

Future directions:

- CI/CD integration for contracts
- Impact analysis automation
- Data lineage integration
- Cross-platform catalog synchronization

---

## 8. Current Development Status

This is an early-stage greenfield project.

Key priorities:

1. Build Importer Framework
2. Implement Delta Lake importer
3. Add SQL folder importer
4. Integrate Great Expectations export
5. Implement contract merge logic
6. Build Git PR automation
7. Develop Streamlit UI

---

## 9. Technology Stack

Primary language:
Python

Key libraries:
- datacontract-cli
- deltalake
- sqlglot
- pydantic
- great_expectations

Interfaces:
- CLI
- Streamlit UI
- GitHub Actions

---

## 10. Naming

Project name:
ContractHub

Possible module naming pattern:

contracthub.importers
contracthub.lifecycle
contracthub.quality
contracthub.orchestrator
contracthub.interfaces

---

END OF CONTEXT