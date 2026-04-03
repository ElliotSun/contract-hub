"""Generic Streamlit editor helpers."""

from __future__ import annotations

import warnings
from typing import Any

import pandas as pd
import streamlit as st
from contracthub.core.editor_rows import (
    is_blank_quality_row,
    is_blank_quick_field_row,
    optional_int,
    rule_condition,
    tags_to_text,
    text_to_tags,
)
from contracthub.core.editor_semantics import normalize_tags, set_mapping_text

try:
    from streamlit_tags import st_tags
except ImportError:  # pragma: no cover - fallback until optional UI dependency is installed
    st_tags = None


def display_value(value: str) -> str:
    """Render a read-only contract field value without showing an empty widget."""
    normalized = str(value or "").strip()
    return normalized if normalized else "Not defined"


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


def selectbox_index(options: list[str], value: str) -> int:
    """Return a stable selectbox index for a known value."""
    normalized = str(value or "").strip()
    try:
        return options.index(normalized)
    except ValueError:
        return 0
