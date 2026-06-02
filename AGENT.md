# 🤖 ContractHub AI Agent Guidelines

Welcome, AI Agent! You are working on **ContractHub**, an open-source, enterprise-level lifecycle governance platform for Open Data Contracts (ODCS).

To ensure high-quality and consistent code generation, please adhere to the following rules:

## 1. Architectural Alignment
ContractHub is a change-driven (not CRUD) system that enforces GitOps workflows, immutable main contracts, and user-scoped drafts.
- **Always read [`ARCHITECTURE.md`](./ARCHITECTURE.md)** before designing new features, adding state, or modifying core modules.

## 2. Load Your Skills
We maintain specialized instructions for you in the `.agents/skills/` directory. 
- **Always read [`.agents/README.md`](./.agents/README.md)** at the start of a session to understand the available skills.
- Load the specific `SKILL.md` file relevant to your current task (e.g., if you are touching UI, read the `streamlit-ui` skill; if touching validation, read `lifecycle-policy`).

## 3. Core Principles
1. **Defensive Coding**: All new code must be fully type-hinted and handle edge cases gracefully. Do not swallow exceptions silently.
2. **Configuration over Environment Variables**: Favor adding user configuration to `ConfigManager` (which resolves from `.contracthub.yaml`) rather than hardcoding `os.environ` reads, unless it's a dynamic CI runner variable.
3. **Preserve Main Contracts**: Canonical contracts in `contracts-main` or the base path should never be overwritten blindly. Use the `merge_engine`.

## 4. Agent Working Style
As an AI contributing to an enterprise-grade open-source project, your execution must be flawless and maintainable:
1. **Plan Before Code**: Always think through the architectural implications and edge cases before writing a single line of code. If a change is complex, propose an implementation plan to the user first.
2. **Make It Simple**: Strive for elegant, minimalist solutions. Avoid over-engineering, unnecessary abstractions, or introducing heavy external dependencies unless absolutely required.
3. **Double Check Your Work**: Never assume your code works on the first try. Always double-check your syntax, type hints, and logic. Where possible, write or run tests to verify your changes.

## 5. Testing
- If you modify business logic in `contracthub/core` or `contracthub/lifecycle`, you must ensure backward compatibility.
- Ensure that the CLI (`contracthub/interfaces/cli.py`) and TUI (`contracthub/tui/app.py`) are kept in sync when introducing new configuration parameters.
