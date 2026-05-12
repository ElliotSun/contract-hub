"""Analysis helpers and result rendering for the editor."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st
from contracthub.interfaces.streamlit.services.contract_service import analyze_draft
from contracthub.lifecycle.merge_engine import MergeAnalysis, MergeConflict

from .constants import CHANGE_FILTER_OPTIONS
from .styles import section_title


def render_analysis_results() -> None:
    """Render governance analysis below the tabs when dialogs are unavailable."""
    result = st.session_state.get("editor_analysis_result")
    if not isinstance(result, dict):
        return

    st.divider()
    st.subheader("Analysis")
    render_analysis_body(result)


def render_analysis_body(result: dict[str, Any]) -> None:
    """Render the analysis result body."""
    if bool(result.get("allowed")):
        st.success("Merge Allowed")
    else:
        st.error("Merge Blocked")

    breaking_rows = result.get("breaking_changes", [])
    deprecation_rows = result.get("auto_deprecations", [])
    diff_rows = result.get("diff", [])

    metric_col_1, metric_col_2, metric_col_3 = st.columns(3, gap="large")
    with metric_col_1:
        st.metric("Breaking count", len(breaking_rows))
    with metric_col_2:
        st.metric("Deprecation count", len(deprecation_rows))
    with metric_col_3:
        st.metric("Total changes", len(diff_rows))

    if breaking_rows:
        section_title("Breaking Changes")
        st.error("Breaking Changes")
        st.dataframe(pd.DataFrame(breaking_rows), width="stretch", hide_index=True)

    if deprecation_rows:
        section_title("Auto-deprecations")
        st.warning("Auto-deprecations")
        st.dataframe(pd.DataFrame(deprecation_rows), width="stretch", hide_index=True)

    filter_col, _ = st.columns([0.35, 0.65], gap="large")
    with filter_col:
        filter_value = st.selectbox(
            "Filter changes", CHANGE_FILTER_OPTIONS, key="editor_analyze_filter"
        )

    filtered_diff_rows = filter_diff_rows(diff_rows, breaking_rows, filter_value)
    section_title("Changes Overview")

    if filtered_diff_rows:
        for row in filtered_diff_rows:
            change_type = str(row.get("change_type", "MODIFIED")).upper()
            field = row.get("field", "Unknown")
            detail = row.get("detail", "")

            if change_type == "ADDED":
                st.markdown(f"🟢 **ADDED**: `{field}` - {detail}")
            elif change_type in ("REMOVED", "DELETED"):
                st.markdown(f"🔴 **REMOVED**: `{field}` - {detail}")
            elif change_type == "DEPRECATED":
                st.markdown(f"🟡 **DEPRECATED**: `{field}` - {detail}")
            else:
                st.markdown(f"🔵 **CHANGED**: `{field}` - {detail}")
    else:
        st.info("No changes to display for the current filter.")

    with st.expander("Detailed Diff", expanded=False):
        st.json(result.get("diff", []))


def dialog_supported() -> bool:
    """Return True when the installed Streamlit version supports dialogs."""
    return hasattr(st, "dialog")


if hasattr(st, "dialog"):

    @st.dialog("Analysis Results")
    def render_analysis_dialog() -> None:
        """Render governance analysis in a dialog when supported."""
        result = st.session_state.get("editor_analysis_result")
        if not isinstance(result, dict):
            st.warning("No analysis result available.")
            return
        render_analysis_body(result)

else:

    def render_analysis_dialog() -> None:
        """Fallback dialog renderer when Streamlit dialogs are unavailable."""
        render_analysis_results()


def run_analysis(contract: dict[str, Any], user: Any) -> None:
    """Run governance analysis for the current draft against its main contract."""
    try:
        raw_result = analyze_draft(contract, user)
    except Exception as exc:
        from contracthub.exceptions import ContractHubError

        error_message = (
            exc.message
            if isinstance(exc, ContractHubError) and hasattr(exc, "message")
            else str(exc)
        )
        st.session_state["editor_error"] = f"Analysis failed: {error_message}"
        st.session_state["editor_warning"] = None
        return

    st.session_state["editor_analysis_result"] = normalize_analysis_result(raw_result)
    st.session_state["editor_warning"] = None
    st.session_state["editor_error"] = None


def normalize_analysis_result(raw_result: Any) -> dict[str, Any]:
    """Normalize governance output for editor display."""
    if isinstance(raw_result, dict) and {
        "diff",
        "breaking_changes",
        "auto_deprecations",
        "allowed",
    }.issubset(raw_result):
        return {
            "diff": list(raw_result.get("diff", []) or []),
            "breaking_changes": list(raw_result.get("breaking_changes", []) or []),
            "auto_deprecations": list(raw_result.get("auto_deprecations", []) or []),
            "allowed": bool(raw_result.get("allowed")),
        }

    if isinstance(raw_result, MergeAnalysis):
        breaking_changes = [
            _conflict_to_row(conflict) for conflict in raw_result.conflicts
        ]
        auto_deprecations: list[dict[str, Any]] = []
        for schema_name in sorted(raw_result.deprecated_schemas):
            auto_deprecations.append(
                {"field": schema_name, "action": "Mark as deprecated"}
            )
        for schema_name, property_names in sorted(
            raw_result.deprecated_properties.items()
        ):
            for property_name in sorted(property_names):
                auto_deprecations.append(
                    {
                        "field": f"{schema_name}.{property_name}",
                        "action": "Mark as deprecated",
                    }
                )

        diff_rows = [
            {"field": item["field"], "change_type": "MODIFIED", "detail": item["issue"]}
            for item in breaking_changes
        ] + [
            {
                "field": item["field"],
                "change_type": "DEPRECATED",
                "detail": item["action"],
            }
            for item in auto_deprecations
        ]
        return {
            "diff": diff_rows,
            "breaking_changes": breaking_changes,
            "auto_deprecations": auto_deprecations,
            "allowed": not breaking_changes,
        }

    breaking_changes = [
        {
            "field": compose_field_name(item),
            "issue": item.get("message")
            or item.get("rule")
            or "breaking change detected",
            "from": item.get("business_value"),
            "to": item.get("base_value"),
        }
        for item in raw_result.get("conflicts", []) or []
        if isinstance(item, dict)
    ]
    auto_deprecations: list[dict[str, Any]] = []
    for schema_name in raw_result.get("deprecated_schemas", []) or []:
        auto_deprecations.append({"field": schema_name, "action": "Mark as deprecated"})
    for schema_name, property_names in (
        raw_result.get("deprecated_properties", {}) or {}
    ).items():
        for property_name in property_names or []:
            auto_deprecations.append(
                {
                    "field": f"{schema_name}.{property_name}",
                    "action": "Mark as deprecated",
                }
            )

    diff_rows = [
        {"field": item["field"], "change_type": "MODIFIED", "detail": item["issue"]}
        for item in breaking_changes
    ] + [
        {"field": item["field"], "change_type": "DEPRECATED", "detail": item["action"]}
        for item in auto_deprecations
    ]
    return {
        "diff": diff_rows,
        "breaking_changes": breaking_changes,
        "auto_deprecations": auto_deprecations,
        "allowed": not breaking_changes,
    }


def filter_diff_rows(
    diff_rows: list[dict[str, Any]],
    breaking_changes: list[dict[str, Any]],
    filter_value: str,
) -> list[dict[str, Any]]:
    """Filter changes overview rows."""
    if filter_value == "ALL":
        return diff_rows
    if filter_value == "BREAKING":
        breaking_fields = {
            str(item.get("field", "")).strip() for item in breaking_changes
        }
        return [
            row
            for row in diff_rows
            if str(row.get("field", "")).strip() in breaking_fields
        ]
    return [
        row
        for row in diff_rows
        if str(row.get("change_type", "UNCHANGED")).strip().upper() == filter_value
    ]


def compose_field_name(item: dict[str, Any]) -> str:
    """Build a field reference from governance output."""
    schema_id = str(item.get("schema_id") or "").strip()
    property_name = str(item.get("property_name") or "").strip()
    if schema_id and property_name and property_name != "__contract__":
        return f"{schema_id}.{property_name}"
    if schema_id:
        return schema_id
    return property_name or "__unknown__"


def field_governance_info_for(
    schema_obj: dict[str, Any], field_obj: dict[str, Any]
) -> dict[str, str | None]:
    """Return governance indicators for a specific field."""
    result = st.session_state.get("editor_analysis_result")
    if not isinstance(result, dict):
        return {
            "breaking": None,
            "breaking_emoji": "",
            "deprecation": None,
            "deprecation_emoji": "",
        }

    field_name = str(field_obj.get("name", "")).strip()
    schema_name = str(schema_obj.get("name", "")).strip()
    field_ref = f"{schema_name}.{field_name}"

    breaking_message = None
    for item in result.get("breaking_changes", []) or []:
        if str(item.get("field", "")).strip() == field_ref:
            breaking_message = str(item.get("issue", "Breaking change detected"))
            break

    deprecation_message = None
    for item in result.get("auto_deprecations", []) or []:
        if str(item.get("field", "")).strip() == field_ref:
            deprecation_message = str(item.get("action", "Marked for deprecation"))
            break

    return {
        "breaking": breaking_message,
        "breaking_emoji": "🚨" if breaking_message else "",
        "deprecation": deprecation_message,
        "deprecation_emoji": "⚠️" if deprecation_message else "",
    }


def _conflict_to_row(conflict: MergeConflict) -> dict[str, Any]:
    """Normalize a merge conflict object for UI display."""
    return {
        "field": compose_field_name(
            {
                "schema_id": conflict.schema_id,
                "property_name": conflict.property_name,
            }
        ),
        "issue": conflict.message or conflict.rule or "breaking change detected",
        "from": conflict.business_value,
        "to": conflict.base_value,
    }
