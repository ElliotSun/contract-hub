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
- `required_bump` is computed PER CONTRACT, not per repo
- feature -> main determines `required_bump` but does NOT change contract version
- release flow applies the explicit version/tag per contract after merge
- repo-level automation may batch many contracts, but it must orchestrate them as independent per-contract release units
- multi-contract release automation should use an explicit manifest because each contract may carry its own release tag/version

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
