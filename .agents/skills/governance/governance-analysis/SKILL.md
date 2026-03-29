---
name: governance-analysis
description: Defines how contract changes are analyzed including breaking changes, deprecation, and merge decisions.
---

# Governance Analysis

Governance analysis determines whether a contract change is safe.

------------------------------------------------
INPUT

- MAIN contract
- DRAFT contract

------------------------------------------------
OUTPUT

- breaking changes
- deprecations
- merge decision
- change summary

------------------------------------------------
RULES

- Analysis MUST run before promotion
- Analysis SHOULD run during editing
- Results must be deterministic

------------------------------------------------
ENGINE

Use:

contracthub.lifecycle.merge_engine

------------------------------------------------
FORBIDDEN

- analyzing UI-only state
- skipping analysis before promotion

------------------------------------------------
GOAL

Provide deterministic and explainable contract evolution.