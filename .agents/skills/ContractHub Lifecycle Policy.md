# ContractHub – Lifecycle Policy Skill (ODCS Contracts)

## 1. Skill Purpose

This skill enforces **lifecycle-aware merge governance** for ODCS contracts.  
It ensures that **merges respect contract, schema, and property lifecycle statuses** and that **breaking changes and auto-deprecations** are applied only when allowed.

---

## 2. Contract Status Gating

| Contract Status | Breaking Checks | Auto-Deprecation | Notes |
|-----------------|----------------|-----------------|-------|
| active          | ✅ Enforced     | ✅ Enforced      | Production contract. Strict governance. |
| proposed / draft / deprecated / retired | ❌ Skipped | ❌ Skipped | Non-production or decommissioned. Free evolution allowed. |

> Enforcement is done by the **Lifecycle Policy Engine** before Merge Engine applies updates.

---

## 3. Lifecycle Status Representation

Lifecycle state is tracked in `customProperties`:

- **SchemaObject**: `customProperties.lifecycleStatus` = `"draft"` | `"active"` | `"deprecated"` | `"retired"`  
- **SchemaProperty**: `customProperties.lifecycleStatus` = `"draft"` | `"active"` | `"deprecated"` | `"retired"`

> Optional metadata for deprecated fields:  
> - `deprecationDate`  
> - `tags += "deprecated"`  

---

## 4. Lifecycle Behavior

| Schema / Field Status | Breaking Checks | Auto-Deprecation | Merge Permissions |
|----------------------|----------------|-----------------|-----------------|
| draft                | ❌ Skip        | ❌ Skip         | Free evolution (add/update allowed) |
| deprecated           | ❌ Skip        | ❌ Skip         | Can merge but fields are excluded from breaking checks |
| active               | ✅ Enforce     | ✅ Apply        | Only additive + governed updates |

> Deprecated fields are **excluded from breaking change checks** but may still be merged.

---

## 5. Breaking Change Rules

Breaking checks apply **ONLY when**:

1. Contract is **active**  
2. SchemaObject is **not draft/deprecated**  
3. SchemaProperty is **not deprecated**

**Breaking conditions:**

- Logical type mismatch  
- Decimal precision reduction  
- Decimal scale reduction  
- Required tightening (`optional → required`)  
- Physical type change  

**Allowed exceptions:**  

- Decimal widening is **allowed**  
- Adding new optional fields is allowed

---

## 6. Auto Deprecation Rule

When contract is **active**:

1. Fields **present in target but missing in source** → mark as deprecated  
2. Update `customProperties.lifecycleStatus = "deprecated"`  
3. Optional: add `deprecationDate` and tag `"deprecated"`

> Fields that are already deprecated remain unchanged.

---

## 7. Merge Update Rules

When merging matching properties, **overwrite the following fields**:

- `physicalType`  
- `partition info`  
- `description`  
- `logicalTypeOptions`  
- `required`  
- `primaryKey`  
- `unique`  
- `customProperties`  

> Deterministic ordering and ODCS identity rules apply (name-based ordering for schema/properties/customProperties).

---

## 8. Merge Execution Model

**Phase 1: Analyze**

- Build contract diff  
- Detect breaking issues according to status gating  
- Identify fields for auto-deprecation

**Phase 2: Apply**

- Apply property updates  
- Append new fields  
- Apply deprecations  
- Ensure deterministic ordering for schema, properties, quality rules, and customProperties

---

## 9. Notes / Enforcement

- **Merge Engine**: handles structural merge & deterministic output  
- **Lifecycle Policy Engine**: enforces status-based checks & deprecations  
- **Version Validator**: ensures version bump is applied if breaking change occurs in `active` contract  
- **GitOps friendly**: all changes are tracked in Git, deterministic, auditable

---

## 10. Enhancements over previous skill

1. Explicitly tracks **active / draft / deprecated / retired** at schema and property levels  
2. Clear gating rules for **breaking checks and auto-deprecation**  
3. Adds **merge execution phases** for analyze + apply  
4. Integrates **deterministic merge** with ODCS identity  
5. Explicit optional metadata for deprecation (`deprecationDate`, `tags`)  
6. Better **GitOps / policy enforcement** alignment