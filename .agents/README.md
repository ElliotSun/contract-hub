# 🤖 ContractHub Agentic System & AI Skills

Welcome to the **ContractHub AI Agentic System**!

To guarantee high-quality code generation, secure data contract governance, and rigorous defensive coding, we provide built-in **AI Agent Skills** under the `.agents/skills/` directory.

## 🌟 What is this?
AI Coding Assistants (such as Google Gemini, Cursor, Claude, or GitHub Copilot) can dynamically load these skills to align their reasoning with ContractHub's core architectural guidelines.

## 📂 Active Skills
- [contracthub-system](skills/contracthub-system/SKILL.md): Core platform principles (e.g., Draft-based editing, immutable main contracts).
- [defensive-coding](skills/defensive-coding/SKILL.md): Strict exception handling, strict typing, and test-mocking rules.
- [devops-workflow](skills/devops-workflow/SKILL.md): GitOps automation, release preparation, and versioning rules.
- [draft-workflow](skills/draft-workflow/SKILL.md): Draft contract evolution and persistence logic.
- [governance-analysis](skills/governance/governance-analysis/SKILL.md): Semantic and breaking change merge rules.
- [lifecycle-policy](skills/governance/lifecycle-policy/SKILL.md): Deprecation and active contract gating principles.
- [llm-enricher](skills/llm-enricher/SKILL.md): Core prompts, metadata provenance rules, and Mocking policy for the LLM enrichment tools.
- [odcs-skills](skills/odcs-skills/SKILL.md): Open Data Contract Standard extensions and upstream alignment rules.
- [service-layer](skills/service-layer/SKILL.md): UI-independent service interfaces.

## 🛠️ How AI Assistants Use These Skills
If you are developing with an AI assistant, you can instruct it to:
> "Read the active agent skills in `.agents/skills/` before refactoring or implementing new modules."
