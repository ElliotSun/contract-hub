---
name: odcs-skills
description: Implement and review Open Data Contract Standard workflows in ContractHub. Use when importing schema metadata into ODCS, performing lifecycle-aware contract merges, enforcing deterministic GitOps-safe ordering, or exporting contract quality rules and metadata.
---

# ODCS Skills

## Overview

Use ODCS models as the single contract representation.
Prefer lifecycle-aware merge behavior: existing contract governs business context, imported contract contributes technical updates.

## Workflow

1. Normalize every input into `OpenDataContractStandard`.
2. Analyze lifecycle scope before applying updates.
3. Apply merge updates in deterministic identity order.
4. Merge lifecycle entities by identity instead of overwriting blindly.
5. Validate the merged result as ODCS.

## Lifecycle Rules

- Treat contract `status=active` as governed scope for breaking checks and auto-deprecation.
- Skip breaking checks and auto-deprecation for draft/deprecated contract scope.
- Treat schema/property identity as `name` only.
- Merge quality rules by `name`.
- Merge customProperties by `property`.
- Mark removed active entities as deprecated using lifecycle metadata.

## Breaking Change Rules

- Flag logical type mismatch.
- Flag physical type changes.
- For decimal types, flag precision reduction and scale reduction.
- Allow decimal widening.
- Flag required tightening (`optional -> required`).

## Deterministic Output

- Sort schemas by `name`.
- Sort properties by `name`.
- Sort quality rules by `name`.
- Sort customProperties by `property`.

## Design References

Load these references as needed:

- `references/ContractHub Lifecycle Policy.md`
  Use for lifecycle gating, merge policy checks, and deprecation rules.
- `references/ContractHub Architechture.md`
  Use for package/module boundaries and architecture alignment decisions.
- `references/ContractHub DevOps Workflow.md`
  Use for GitOps flow, CI/CD expectations, and delivery workflow constraints.

## Repository Pointers

- Use `sample_odcs.yaml` as baseline ODCS shape.
- Use `contracthub/lifecycle/merge_engine.py` as the lifecycle merge implementation.
