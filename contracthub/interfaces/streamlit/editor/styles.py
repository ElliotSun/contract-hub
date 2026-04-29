"""Shared visual styling for the ContractHub Streamlit UI."""

from __future__ import annotations

import streamlit as st


def inject_app_styles() -> None:
    """Apply the business-first light theme used by the Streamlit UI."""
    st.markdown(
        """
        <style>
        :root {
            --ch-bg: #F7F9FC;
            --ch-surface: #FFFFFF;
            --ch-border: #E5E7EB;
            --ch-primary: #3B82F6;
            --ch-primary-hover: #2563EB;
            --ch-heading: #111827;
            --ch-body: #374151;
            --ch-muted: #6B7280;
            --ch-active: #10B981;
            --ch-active-soft: #ECFDF5;
            --ch-deprecated: #F59E0B;
            --ch-deprecated-soft: #FFFBEB;
            --ch-breaking: #EF4444;
            --ch-breaking-soft: #FEF2F2;
            --ch-draft: #6B7280;
            --ch-draft-soft: #F3F4F6;
        }

        .stApp {
            background: var(--ch-bg);
            color: var(--ch-body);
        }

        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2.5rem;
        }

        h1, h2, h3, h4, h5, h6 {
            color: var(--ch-heading);
            letter-spacing: -0.01em;
        }

        p, label, .stCaption, .stMarkdown, .stText, .stMetric {
            color: var(--ch-body);
        }

        [data-testid="stTextInputRootElement"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stNumberInput"] input,
        [data-baseweb="select"] > div,
        [data-testid="stDateInputField"] input {
            background: var(--ch-surface);
            border: 1px solid var(--ch-border);
        }

        [data-testid="stTextInputRootElement"] input:focus,
        [data-testid="stTextArea"] textarea:focus,
        [data-testid="stNumberInput"] input:focus {
            border-color: var(--ch-primary);
            box-shadow: 0 0 0 1px var(--ch-primary);
        }

        .stButton > button {
            border-radius: 0.7rem;
            border: 1px solid var(--ch-border);
            background: var(--ch-surface);
            color: var(--ch-body);
            font-weight: 600;
            transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease;
        }

        .stButton > button:hover {
            border-color: var(--ch-primary);
            color: var(--ch-primary-hover);
            box-shadow: 0 6px 18px rgba(59, 130, 246, 0.08);
            transform: translateY(-1px);
        }

        [data-testid="stTabs"] button[role="tab"] {
            border-radius: 0.65rem 0.65rem 0 0;
            color: var(--ch-muted);
            font-weight: 600;
        }

        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            color: var(--ch-heading);
        }

        [data-testid="stMetric"] {
            background: var(--ch-surface);
            border: 1px solid var(--ch-border);
            border-radius: 0.9rem;
            padding: 0.8rem 0.95rem;
        }

        [data-testid="stExpander"] {
            background: var(--ch-surface);
            border: 1px solid var(--ch-border);
            border-radius: 0.9rem;
        }

        [data-testid="stDataFrame"],
        [data-testid="stDataEditor"] {
            background: var(--ch-surface);
            border-radius: 0.9rem;
        }

        .ch-section-title {
            color: var(--ch-heading);
            font-size: 1.05rem;
            font-weight: 700;
            margin: 0.1rem 0 0.75rem 0;
        }

        .ch-section-note {
            color: var(--ch-muted);
            font-size: 0.92rem;
            margin-top: -0.15rem;
            margin-bottom: 0.9rem;
        }

        .ch-status-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin: 0.2rem 0 0.5rem 0;
        }

        .ch-badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.22rem 0.62rem;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            border: 1px solid transparent;
        }

        .ch-badge-active {
            background: var(--ch-active-soft);
            color: #047857;
            border-color: #A7F3D0;
        }

        .ch-badge-deprecated {
            background: var(--ch-deprecated-soft);
            color: #B45309;
            border-color: #FDE68A;
        }

        .ch-badge-breaking {
            background: var(--ch-breaking-soft);
            color: #B91C1C;
            border-color: #FECACA;
        }

        .ch-badge-draft {
            background: var(--ch-draft-soft);
            color: #4B5563;
            border-color: #D1D5DB;
        }

        .ch-card-purpose {
            color: var(--ch-body);
            margin: 0.4rem 0 0.35rem 0;
            line-height: 1.45;
        }

        .ch-card-meta {
            color: var(--ch-muted);
            font-size: 0.9rem;
        }

        .ch-card-subtitle {
            color: var(--ch-muted);
            font-size: 0.95rem;
            font-weight: 600;
            margin-top: -0.25rem;
            margin-bottom: 0.45rem;
        }

        .ch-inline-label {
            color: var(--ch-muted);
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, note: str | None = None) -> None:
    """Render a styled section heading."""
    st.markdown(f"<div class='ch-section-title'>{title}</div>", unsafe_allow_html=True)
    if note:
        st.markdown(
            f"<div class='ch-section-note'>{note}</div>", unsafe_allow_html=True
        )


def status_badge_html(status: str, flags: list[str]) -> str:
    """Render semantic badges using the shared style system."""
    classes = {
        "active": "ch-badge ch-badge-active",
        "deprecated": "ch-badge ch-badge-deprecated",
        "breaking": "ch-badge ch-badge-breaking",
        "draft": "ch-badge ch-badge-draft",
        "retired": "ch-badge ch-badge-draft",
    }
    labels: list[tuple[str, str]] = []
    normalized_status = (status or "draft").lower()
    labels.append(
        (normalized_status, classes.get(normalized_status, "ch-badge ch-badge-draft"))
    )
    if "breaking" in flags:
        labels.append(("breaking", classes["breaking"]))
    if "deprecated" in flags and normalized_status != "deprecated":
        labels.append(("deprecated", classes["deprecated"]))

    badges = "".join(
        f"<span class='{css_class}'>{label}</span>" for label, css_class in labels
    )
    return f"<div class='ch-status-row'>{badges}</div>"


def catalog_badges_html(status: str, flags: list[str], tags: list[str]) -> str:
    """Render catalog status and tag badges in one compact section."""
    classes = {
        "active": "ch-badge ch-badge-active",
        "deprecated": "ch-badge ch-badge-deprecated",
        "breaking": "ch-badge ch-badge-breaking",
        "draft": "ch-badge ch-badge-draft",
        "retired": "ch-badge ch-badge-draft",
    }
    normalized_status = (status or "draft").lower()
    labels: list[tuple[str, str]] = [
        (normalized_status, classes.get(normalized_status, "ch-badge ch-badge-draft"))
    ]
    if "breaking" in flags:
        labels.append(("breaking", classes["breaking"]))
    if "deprecated" in flags and normalized_status != "deprecated":
        labels.append(("deprecated", classes["deprecated"]))

    badge_html = "".join(
        f"<span class='{css_class}'>{label}</span>" for label, css_class in labels
    )
    tag_html = "".join(
        f"<span class='ch-badge ch-badge-draft'>{tag}</span>" for tag in tags
    )
    return f"<div class='ch-status-row'>{badge_html}{tag_html}</div>"
