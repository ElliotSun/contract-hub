---
name: contracthub-system
description: Defines the core operating model of ContractHub including draft-based editing, immutable main contracts, and change-driven workflows.
---

# ContractHub System Model

ContractHub is a **contract governance platform**, not a CRUD system.

------------------------------------------------
CORE PRINCIPLE

ContractHub is a CHANGE-DRIVEN system.

- Save = save draft
- Publish = promote draft

------------------------------------------------
SYSTEM LAYERS (RUNTIME MODEL)

1. MAIN CONTRACT
- Source of truth
- Immutable from UI

2. DRAFT CONTRACT
- User working copy
- All edits happen here

3. GOVERNANCE RESULT
- Produced by analysis
- Determines merge safety

------------------------------------------------
STRICT RULES

- UI must NEVER overwrite main contract
- Version must NOT change during editing
- All changes must go through draft
- Governance analysis is mandatory before promotion

------------------------------------------------
RELATION TO ARCHITECTURE

This model must be enforced by:

- service-layer (execution)
- governance-analysis (validation)
- devops-workflow (promotion)

------------------------------------------------
GOAL

Provide a Git-like workflow for safe contract evolution.