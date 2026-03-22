"""Generic Streamlit editor helpers."""

from __future__ import annotations

import warnings
from typing import Any

import pandas as pd
import streamlit as st

try:
    from streamlit_tags import st_tags
except ImportError:  # pragma: no cover - fallback until optional UI dependency is installed
    st_tags = None


def display_value(value: str) -> str:
    """Render a read-only contract field value without showing an empty widget."""
    normalized = str(value or "").strip()
    return normalized if normalized else "Not defined"


def tags_to_text(tags: Any) -> str:
    """Render tags as a comma-separated string."""
    return ", ".join(normalize_tags(tags))


def text_to_tags(value: str) -> list[str]:
    """Parse tags from a comma-separated string."""
    return normalize_tags(value.split(","))


def normalize_tags(tags: Any) -> list[str]:
    """Normalize tag values into a stable, de-duplicated list."""
    if not isinstance(tags, list):
        return []

    normalized_tags: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = str(tag).strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized_tags.append(normalized)
    return normalized_tags


def render_tag_badges(tags: list[str]) -> None:
    """Render tags as compact chip-like badges."""
    if not tags:
        st.caption("No tags defined.")
        return

    pill_html = "".join(
        f"<span style='display:inline-block;margin:0 0.35rem 0.35rem 0;padding:0.2rem 0.65rem;border:1px solid #E5E7EB;border-radius:999px;background:#FFFFFF;color:#374151;font-size:0.85rem;font-weight:600;'>{tag}</span>"
        for tag in tags
    )
    st.markdown(pill_html, unsafe_allow_html=True)


def render_tags_editor(tags: Any, *, state_prefix: str, label: str) -> list[str]:
    """Render tags using the dedicated Streamlit tag component."""
    current_tags = normalize_tags(tags)
    if st_tags is None:
        tag_text = st.text_input(
            label,
            value=tags_to_text(current_tags),
            key=f"{state_prefix}_tags_input",
            help="Comma-separated tags.",
        )
        normalized_tags = text_to_tags(tag_text)
    else:
        edited_tags = st_tags(
            label=label,
            text="Press enter to add tags",
            value=current_tags,
            suggestions=[],
            maxtags=-1,
            key=f"{state_prefix}_tags_input",
        )
        normalized_tags = normalize_tags(edited_tags)
    render_tag_badges(normalized_tags)
    return normalized_tags


def set_mapping_text(mapping: dict[str, Any], key: str, value: str) -> None:
    """Set or remove a string mapping field."""
    if value.strip():
        mapping[key] = value
    else:
        mapping.pop(key, None)


def rows_from_dataframe(frame: Any) -> list[dict[str, Any]]:
    """Convert a data editor result to rows."""
    if isinstance(frame, pd.DataFrame):
        return frame.to_dict(orient="records")
    if isinstance(frame, list):
        return [row for row in frame if isinstance(row, dict)]
    return []


def editor_dataframe(rows: list[dict[str, Any]], columns: list[str] | None = None) -> pd.DataFrame:
    """Create a stable dataframe for Streamlit editing."""
    frame = pd.DataFrame(rows)
    if columns:
        frame = frame.reindex(columns=columns)
    for column in frame.columns:
        if column == "required":
            frame[column] = frame[column].astype("boolean")
        elif column in {"__original_index", "__rule_index"}:
            frame[column] = frame[column].astype("Int64")
        else:
            frame[column] = frame[column].astype("string")
    return frame


def render_data_editor(data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
    """Render a data editor with warning suppression for Streamlit internals."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.",
            category=FutureWarning,
        )
        return st.data_editor(data, **kwargs)


def is_blank_quick_field_row(row: dict[str, Any]) -> bool:
    """Return True when a quick-edit row is effectively empty."""
    return not any(
        [
            str(row.get("name", "")).strip(),
            str(row.get("type", "")).strip(),
            str(row.get("description", "")).strip(),
            bool(row.get("required", False)),
        ]
    )


def is_blank_quality_row(row: dict[str, Any]) -> bool:
    """Return True when a quality row is effectively empty."""
    return not any(
        [
            str(row.get("rule_name", "")).strip(),
            str(row.get("condition", "")).strip(),
            str(row.get("column", "")).strip(),
        ]
    )


def rule_condition(rule: dict[str, Any]) -> tuple[str, str]:
    """Resolve a readable condition field for a quality rule."""
    for key in ("condition", "mustBe", "mustBeGreaterThan", "mustBeLessThan", "query", "rule"):
        if key in rule:
            value = rule.get(key)
            return key, "" if value is None else str(value)
    return "condition", ""


def optional_int(value: Any) -> int | None:
    """Convert a nullable dataframe value to an int."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def selectbox_index(options: list[str], value: str) -> int:
    """Return a stable selectbox index for a known value."""
    normalized = str(value or "").strip()
    try:
        return options.index(normalized)
    except ValueError:
        return 0
