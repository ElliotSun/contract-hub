---
name: devops-workflow
description: Defines GitOps workflow for contract promotion including branch creation, pull requests, CI/CD, and versioning.
---

# DevOps Workflow

ContractHub follows a GitOps-based promotion model.

------------------------------------------------
FLOW

Draft → Promote → PR → CI/CD → Merge → Release

------------------------------------------------
RULES

- MAIN contract updated only via merge
- CI/CD validates contracts before merge
- version increment happens after merge

------------------------------------------------
FUTURE

- auto PR creation
- automated validation pipelines
- audit logs

------------------------------------------------
FORBIDDEN

- direct writes to main branch
- bypassing CI/CD

------------------------------------------------
GOAL

Ensure safe, auditable, and deterministic contract delivery.