# ContractHub Architecture

This skill defines the permanent architecture rules for the system.

These rules ALWAYS override task-level instructions.

------------------------------------------------
CORE PURPOSE

ContractHub is an enterprise data contract control plane.

------------------------------------------------
ARCHITECTURE PRINCIPLES

The system must follow strict layered architecture.

------------------------------------------------
1. IMPORT LAYER

Responsible ONLY for converting external sources into ODCS.

Rules:

- stateless
- idempotent
- NO merge logic
- NO governance logic
- NO CI/CD logic

------------------------------------------------
2. CORE CONTRACT MODEL

- ODCS YAML is the single canonical model
- No alternative representations allowed

------------------------------------------------
3. LIFECYCLE GOVERNANCE LAYER

Handles:

- breaking change detection
- lifecycle evaluation
- merge policy
- deprecation

Rules:

- ONLY place for lifecycle logic
- must not be implemented elsewhere

------------------------------------------------
4. EXPORT LAYER

- Converts contracts to artifacts (GE, CI, etc.)
- MUST NOT modify contracts

------------------------------------------------
5. ORCHESTRATION LAYER

- Coordinates workflows (import → merge → export → PR)
- MUST NOT contain business logic

------------------------------------------------
6. DEVOPS LAYER

- PR creation
- versioning
- audit metadata

------------------------------------------------
TECHNICAL CONSTRAINTS

- Python 3.11
- typed code
- modular design
- reusable components

------------------------------------------------
DESIGN GUARDRAILS

NEVER:

- put merge logic in importers
- mix governance with ingestion
- create monolithic modules

ALWAYS:

- separate responsibilities
- enforce clean boundaries

------------------------------------------------
GOAL

Ensure a scalable, maintainable, and extensible system architecture.