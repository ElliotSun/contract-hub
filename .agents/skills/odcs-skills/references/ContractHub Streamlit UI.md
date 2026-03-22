You are implementing the Streamlit UI for the ContractHub repository.

This UI is NOT a developer debugging tool.

It is a business-friendly **enterprise contract platform**.

------------------------------------------------
CORE PURPOSE

The UI must enable:

- Contract discovery (Catalog)
- Contract viewing (Detail)
- Safe editing (if permitted)
- Governance analysis (on-demand)

------------------------------------------------
CRITICAL CHANGE

REMOVE any previous sidebar navigation including:

- editor
- merge
- analysis

DO NOT implement sidebar-based navigation.

This UI is a **single-page application with state-driven views**.

------------------------------------------------
DESIGN SYSTEM (MANDATORY)

Theme:

- Light, business-friendly
- Calm, low contrast

Colors:

- Background: #F7F9FC
- Surface: #FFFFFF
- Border: #E5E7EB

Primary:

- #3B82F6

Text:

- Heading: #111827
- Body: #374151
- Muted: #6B7280

Status:

- Active: #10B981
- Deprecated: #F59E0B
- Breaking: #EF4444
- Draft: #6B7280

Rules:

- No dark theme
- No neon colors

------------------------------------------------
SPACING

- 8px / 16px / 24px rhythm
- Cards use padding
- Avoid dense UI

------------------------------------------------
COMPONENT LIBRARY

Use these components:

1. Contract Card
2. Status Badge
3. Section Card
4. Expandable Field Section (CRITICAL)
5. Data Table Editor
6. Analyze Result Card
7. Read-only Banner
8. Action Bar
9. Filter Bar
10. Infrastructure Panel

------------------------------------------------
UI VIEW MODEL (CRITICAL)

Two modes:

1. Catalog View (default)
2. Detail View

Use:

st.session_state.view_mode
st.session_state.selected_contract_id

------------------------------------------------
HEADER

- Title: ContractHub
- Search
- Filters (Domain / Status / Tenant)
- New Contract

Detail View ONLY:

- [Analyze Changes]
- [Save]

------------------------------------------------
CATALOG VIEW

Purpose: browse contracts

Layout:

- Grid of Contract Cards

Each card:

- name + version
- status badge
- domain, tenant
- tags
- description

Actions:

- View Details
- Edit

Behavior:

- Clicking loads Detail View

Permissions:

- Disable Edit if not allowed

------------------------------------------------
DETAIL VIEW

Layout:

1. Header (with Back button)
2. Contract Section
3. Tabs
4. Analyze Results
5. Infrastructure

------------------------------------------------
DETAIL NAVIGATION

Top:

- Contract name + version
- Back to Catalog button

------------------------------------------------
CONTRACT SECTION

- Core info
- Description
- System fields (collapsed)

------------------------------------------------
SCHEMA TAB

Modes:

----------------------------------------
Quick Edit

- table editor

----------------------------------------
Detail Edit (CRITICAL)

Use EXPANDABLE FIELD SECTIONS.

Each field:

- expander

Inside:

Editable:

- description

Read-only:

- type
- required
- lifecycleStatus

Rules:

- No left-right layout
- No dropdown field selector
- All fields visible

----------------------------------------

Enhancements:

- Show type badge
- Show status badge
- Highlight breaking/deprecated

------------------------------------------------
QUALITY TAB

- Table editor
- Column dropdown from schema

------------------------------------------------
ADVANCED TAB

- YAML in expander
- Unsafe edit optional

------------------------------------------------
ANALYZE

Triggered by button.

Display below tabs:

- Merge decision
- Metrics
- Breaking (red)
- Deprecated (orange)
- Changes
- Diff (expander)

------------------------------------------------
INFRASTRUCTURE

- Read-only
- Clean layout
- Collapsible advanced

------------------------------------------------
PERMISSIONS

User can edit ONLY if:

- same tenant OR admin

Behavior:

- Disable editing
- Show read-only banner
- Disable Save

------------------------------------------------
STATE MANAGEMENT

Single source:

st.session_state.contract

Additional:

- view_mode
- selected_contract_id
- analysis_result

------------------------------------------------
STRICT RULES

DO NOT:

- implement governance logic
- create sidebar navigation
- create multi-page apps
- expose YAML as primary UI
- allow editing technical fields

------------------------------------------------
UX PRINCIPLES

- Business-first
- Clean and calm
- Progressive disclosure
- Catalog → Detail → Analyze flow
- No engineering-style navigation

------------------------------------------------
GOAL

Build a modern enterprise SaaS-like contract platform that:

- feels intuitive to business users
- hides technical complexity
- enforces governance safely