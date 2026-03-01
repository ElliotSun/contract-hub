# ContractHub – Architecture Overview

## 1. Purpose

This document provides a complete architecture blueprint for ContractHub, the enterprise data contract platform.

It is designed for:

- Data engineers
- Platform teams
- Business stakeholders
- AI agents (Codex/ChatGPT)

---

## 2. System Overview

ContractHub is a modular, GitOps-driven platform for managing Open Data Contract Standard (ODCS) contracts.

It integrates with:

- Delta Lake (pure Python importer)
- SparkSQL pipelines
- Unity Catalog tables
- Great Expectations for data quality
- Streamlit for business UI
- Azure DevOps / Git for version control

**Goal:** Operationalize data contracts across pipelines and business workflows.

---

## 3. Module Map


ContractHub
├── importers/ # Data source -> Contract (ODCS)
│ ├── sql_importer.py # Parse SQL files into contract
│ ├── delta_importer.py # Read Delta tables (pure Python)
│ └── uc_importer.py # Read Unity Catalog tables/views
├── lifecycle/ # Merge & Governance
│ ├── merge_engine.py # Contract merge & breaking checks
│ ├── policy.py # Lifecycle rules (active/draft/deprecated)
│ └── helpers.py # Lifecycle utilities
├── quality/ # Contract -> GE expectations
│ ├── ge_exporter.py # Export GE test suites
│ └── validation.py # Validate data against GE
├── orchestrator/ # Workflow coordination
│ └── pipeline.py # Import → Merge → Export → PR
├── interfaces/ # User/Dev interaction
│ ├── cli.py # Engineer CLI
│ └── ui_streamlit.py # Business-facing Streamlit UI
├── devops/ # GitOps integration
│ ├── pr_creator.py # Auto PR creation
│ ├── ci_cd.py # Pipeline enforcement
│ └── audit.py # Metadata, lastMergeTs, actor
└── tests/ # Unit & integration tests


---

## 4. Data Flow


[SQL Folder / Delta Table / UC Catalog] --> Importers
│
▼
[Source Contract (ODCS)]
│
▼
[Lifecycle Merge Engine] <--> [Target Contract in Git]
│
▼
[Quality Layer: GE Suites]
│
▼
[Orchestration: Execute Pipelines]
│
▼
[DevOps Layer: PR / CI / Audit]
│
▼
[Business / Data Platform Notifications]


- **Key idea:** Importers are stateless; merge engine handles governance; exporters generate operational artifacts; orchestration coordinates everything; DevOps ensures GitOps discipline.

---

## 5. Contract Lifecycle Logic

| Layer      | Lifecycle Key       | Behavior |
|-----------|-------------------|---------|
| Contract  | status             | active / draft / deprecated; active enforces breaking checks |
| Schema    | lifecycleStatus    | draft / deprecated; draft allows updates; deprecated skips breaking checks |
| Field     | lifecycleStatus    | draft / deprecated; same as schema |
| Merge     | breaking checks    | Only active + non-draft/non-deprecated |
| Merge     | auto-deprecation   | Only active contracts; missing fields marked deprecated |

- **Note:** No automated rename handling; renames are manual in draft tables.

---

## 6. GitOps & DevOps Flow

1. Importer generates source contract  
2. Lifecycle engine compares with target  
3. Dry-run merge checks (optional in PR validation)  
4. Apply merge if checks pass  
5. Generate PR with:  
   - Diff summary  
   - Breaking changes report  
   - Deprecated fields report  
6. CI pipeline runs:  
   - Contract validation  
   - GE tests  
   - Fail if breaking changes for active contracts  
7. Merge PR → Update main contract  

- **Audit metadata:** lastMergeTs, lastMergeActor, lastMergeSource

---

## 7. Great Expectations Integration

- GE test suites are exported from contracts  
- Can be executed in Spark notebooks or Databricks jobs  
- Ensures contract-driven data quality  
- Supports automatic test regeneration after contract updates

---

## 8. Streamlit UI for Business

- Users can edit table/field descriptions  
- Add rules or notes  
- Submit → triggers auto PR back to Git  
- UI changes are **always synced with ODCS YAML** in Git

---

## 9. Coding & Design Guidelines

- Python 3.11  
- Modular design, type hints, testable  
- Importers are **pure Python**, no Spark runtime  
- Lifecycle rules strictly separated from importers  
- Reuse datacontract-cli for contract model and GE export  
- Follow GitOps practices: no direct commits to main branch

---

## 10. Recommended Repo Structure


contracthub/
│── project_context.md
│── ARCHITECTURE.md
│── README.md
│── contracthub/
│ ├── importers/
│ ├── lifecycle/
│ ├── quality/
│ ├── orchestrator/
│ ├── interfaces/
│ ├── devops/
│── tests/


- Skills and project context are at root  
- All code modules follow the modular map above

---

## 11. Next Steps

1. Implement Importer Layer (SQL / Delta / UC)  
2. Implement Lifecycle Merge Engine  
3. Integrate Great Expectations export  
4. Implement GitOps PR automation  
5. Develop Streamlit UI (business review)  
6. Run Phase 1 roadmap to reach MVP