---
name: defensive-coding
description: Defines the strict coding standards, exception handling, and typing rules for Coding Agents modifying ContractHub. Apply this skill whenever writing new logic, refactoring core pipelines, or debugging integration issues.
---

# Defensive Coding & Agent Directives

## 1. Exception Handling
- **NEVER use bare `except Exception:` blocks** unless at the absolute top-level entrypoint logging boundary (e.g., catching uncaught errors right before the process exits).
- Always raise and catch domain-specific exceptions (e.g., `ContractHubError`, `ValidationError`, `MergeConflictError`) so that external DevOps systems and CI pipelines can properly classify the failure.
- When wrapping third-party exceptions (like `urllib.error.URLError` or `json.JSONDecodeError`), pass the originating exception up using the `raise NewError(...) from exc` syntax.

## 2. Typing & Pydantic
- All code MUST be fully statically typed using Python 3.11+ syntax (`|` union operators, `list[str]`, etc.).
- The `OpenDataContractStandard` Pydantic model must be used exclusively as the single source of truth across the architecture.
- Do NOT fall back to parsing or mutating configuration as raw `dict[str, Any]` inside core logic, parsers, or exporters. Avoid dictionary mappings unless strictly needed at the immediate edge/IO boundary.

## 3. Testing Policy
- Every new feature, logic update, or bug fix must be accompanied by relevant unit tests.
- **Strict Isolation:** When testing interactions with external APIs (like OpenAI for LLM enrichment) or external Cloud Storage (like Azure ADLS, Unity Catalog), you MUST heavily use `pytest-mock` or `unittest.mock.patch`.
- Do NOT allow the test suite to execute real HTTP requests, write to actual databases, or require unmocked credentials.

## 4. Upstream Adherence
- Stop and evaluate if upstream projects (e.g. `datacontract-cli`) already provide the feature you are implementing. Do not reinvent built-in validators, parsers, or linting processes.
