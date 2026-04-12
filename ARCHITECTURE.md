# ContractHub Architecture

## Purpose

ContractHub is an ODCS-first contract governance platform.

The current implementation focuses on:

- canonical main contracts
- user-scoped drafts
- lifecycle governance analysis
- contract quality export
- deployment artifact export
- a Streamlit UI as one presentation layer

ContractHub is not a CRUD system. It is a change-driven system:

- edit -> save draft
- analyze -> compare draft vs main
- promote -> future GitOps workflow

## Current Runtime Layers

### 1. Core

Location:

- `contracthub/core/`

Responsibilities:

- load canonical ODCS contracts from supported storage
- validate ODCS contracts and quality rules
- normalize user drafts so business edits do not overwrite technical fields

Key modules:

- `contracthub/core/loader.py`
- `contracthub/core/validator.py`
- `contracthub/core/draft_normalizer.py`

### 2. Lifecycle Governance

Location:

- `contracthub/lifecycle/`

Responsibilities:

- analyze main vs source contract changes
- detect breaking changes
- determine auto-deprecations
- apply lifecycle-aware merges

Key modules:

- `contracthub/lifecycle/merge_engine.py`
- `contracthub/lifecycle/policy.py`

### 3. Utilities

Location:

- `contracthub/utils/`

Responsibilities:

- YAML file IO
- YAML string parse/dump through ODCS model definitions
- input normalization helpers

Key modules:

- `contracthub/utils/yaml_utils.py`
- `contracthub/utils/schema_utils.py`

### 4. Service Layer

Location:

- `contracthub/interfaces/streamlit/services/`

Responsibilities:

- serve as the only UI boundary into system logic
- read canonical contracts
- read and persist user drafts
- enforce edit permissions
- delegate governance analysis

Key modules:

- `contracthub/interfaces/streamlit/services/contract_service.py`
- `contracthub/interfaces/streamlit/services/governance_service.py`

### 5. Exporters

Location:

- `contracthub/exporters/`
- `contracthub/quality/`

Responsibilities:

- generate Great Expectations suites from ODCS contracts
- generate SQL deployment DDL
- add limited Databricks-specific constraint enhancement where supported

Key modules:

- `contracthub/quality/ge_exporter.py`
- `contracthub/exporters/sql_exporter.py`

### 6. Orchestration

Location:

- `contracthub/orchestrator/`

Responsibilities:

- coordinate non-interactive automation flows
- import -> merge -> validate -> export

Key module:

- `contracthub/orchestrator/pipeline.py`

### 7. Interfaces

Location:

- `contracthub/interfaces/`

Responsibilities:

- presentation only
- collect user input
- display governance results
- call service layer

Current interface:

- Streamlit single-page app in `contracthub/interfaces/streamlit/app.py`

## Current Contract Model

ContractHub currently assumes:

- Open Data Contract Standard (ODCS) is the single canonical contract representation
- `open_data_contract_standard.model.OpenDataContractStandard` is the canonical runtime model

The system may temporarily work with Python `dict` objects at boundaries, but normalization should converge back to ODCS objects or ODCS-shaped mappings.

## Root Contract Governance

At the top level of the contract, ContractHub currently treats these fields specially:

- `id`
  - immutable once the governed/main contract exists
  - importer-generated IDs are only used when a contract is first created outside ContractHub
- `version`
  - release-managed
  - must not change in the normal import/merge pipeline
  - technical source versions such as Delta table versions must not overwrite the governed contract version

Current behavior:

- `contracthub.lifecycle.merge_engine` preserves governed `id` and `version`
- `contracthub.lifecycle.policy` flags root `id` changes as `id_violation`
- `contracthub.lifecycle.policy` flags root version changes as `version_violation`
- `contracthub.orchestrator.pipeline` blocks on `id_violation` and `version_violation`

This means ContractHub currently supports:

- technical schema refresh through import/merge
- governed metadata preservation

It does not yet implement:

- automatic discovery of which contracts in a repo should be released together
- automatic git-tag lookup inside core/service layers

## Release Governance Direction

Current release-version governance is intentionally **per contract**, not per repo.

This supports both:

- one-contract-per-repo setups
- centralized repos containing many governed contracts

Current intended flow:

1. `feature -> main`
   - validate and analyze one changed contract
   - compute `required_bump` for that contract
   - do **not** change contract `version`
2. `main -> release`
   - re-evaluate the release candidate for that contract
   - apply an explicit `release_tag`
   - update contract `version` through the release path only

Current bump rules:

- `none`
  - descriptive-only metadata changes
- `minor`
  - additive or non-breaking structural changes
  - newly introduced schema/property deprecations
- `major`
  - lifecycle-breaking changes

Current release tooling:

- `contracthub release classify`
  - compute `required_bump` for one contract
- `contracthub release prepare`
  - prepare one promoted contract candidate with an explicit `release_tag`
- `contracthub release create-pr`
  - create one release PR for one contract

## Repo-Level Release Orchestration

Some repositories contain multiple governed contracts. ContractHub supports
repo-level release orchestration helpers, but these helpers do **not** change
the versioning unit.

Current repo-level commands:

- `contracthub release classify-repo`
  - compare two contract roots
  - report per-contract statuses such as `changed`, `unchanged`, `added`, and `removed`
  - report `required_bump` for changed contracts only
- `contracthub release build-manifest`
  - generate an editable JSON array of per-contract release tasks
  - suggest release tags and source branches from each contract's current version and `required_bump`
- `contracthub release create-prs`
  - consume an explicit batch manifest
  - run independent per-contract release preparation and PR creation

Important rule:

- the repository is a batching boundary only
- each contract still owns its own identity, version, release tag, and release decision

Recommended repo-level flow:

1. `contracthub release classify-repo`
   - inspect changed contracts
2. `contracthub release build-manifest`
   - generate an editable per-contract release task list
3. review and adjust the manifest
   - especially release tags and branch names
4. `contracthub release create-prs`
   - create one PR per contract release task

## Draft Workflow

Current draft workflow:

1. load main contract
2. load existing draft or initialize draft from main
3. edit draft
4. analyze draft vs main
5. save draft
6. promote later through GitOps workflow

Important rules:

- UI must not overwrite the main contract
- draft persists independently
- service layer validates before saving draft
- service layer preserves non-editable contract/schema/property fields from the main contract

Draft storage:

- `.contracthub/drafts/{user}/{contract_id}.yaml`

## Storage Support

Current canonical contract roots support:

- local filesystem paths
- ADLS2 paths
- Databricks Unity Catalog mounted volume paths

ADLS2 authentication currently supports:

- `CONTRACTHUB_ADLS_BEARER_TOKEN`
- `azure.identity.DefaultAzureCredential`

SAS URL authentication is intentionally not supported.

## Quality and Export Boundaries

### Contract validation

`contracthub/core/validator.py` validates:

- ODCS structure
- quality rule completeness
- ODCS quality type semantics

### GE export

`contracthub/quality/ge_exporter.py`:

- delegates suite generation to datacontract-cli
- performs GE-specific preflight on exported expectation configs
- does not execute runtime validation

### SQL export

`contracthub/exporters/sql_exporter.py`:

- delegates base SQL generation to datacontract-cli
- appends Databricks-only constraints for a limited supported subset of ODCS quality rules

Current supported Databricks mappings:

- `nullValues mustBe 0` -> `SET NOT NULL`
- `invalidValues + validValues` -> `CHECK IN (...)`
- `invalidValues + pattern` -> `CHECK RLIKE ...`

Precedence:

- schema `required=True` is emitted first by datacontract-cli as `NOT NULL`
- ContractHub does not emit duplicate nullability constraints

## Current Design Principles

- main contract is canonical and immutable from the UI path
- service layer is the only boundary between UI and system logic
- lifecycle logic belongs in the lifecycle layer
- ODCS is the canonical contract model
- datacontract-cli is reused where possible instead of reimplemented

## Known Next Steps

- formalize draft promotion flow
- continue reducing UI-specific logic that still lives near editor helpers
- keep converging helper logic toward ODCS model-driven behavior
