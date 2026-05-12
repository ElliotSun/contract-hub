"""Raw YAML apply/validate helpers for the editor."""

from __future__ import annotations

import streamlit as st

from .contract_model import parse_yaml_payload
from .state import (
    ensure_selected_field,
    ensure_selected_schema,
    sync_contract_inputs,
    sync_field_inputs,
    sync_schema_inputs,
)


def apply_raw_yaml(raw_yaml: str) -> None:
    """Apply unsafe raw YAML changes to the working contract."""
    if not raw_yaml.strip():
        st.session_state["editor_warning"] = "Contract YAML cannot be empty."
        return
    try:
        payload = parse_yaml_payload(raw_yaml)
    except Exception as exc:
        from contracthub.exceptions import ContractHubError

        error_message = (
            exc.message
            if isinstance(exc, ContractHubError) and hasattr(exc, "message")
            else str(exc)
        )
        st.session_state["editor_error"] = f"Failed to load YAML: {error_message}"
        return
    st.session_state["contract"] = payload
    st.session_state["editor_baseline_yaml"] = raw_yaml
    st.session_state["editor_raw_yaml"] = raw_yaml
    st.session_state["editor_notice"] = (
        "Unsafe YAML edits applied to the working contract."
    )
    st.session_state["editor_warning"] = None
    st.session_state["editor_error"] = None
    ensure_selected_schema(payload)
    ensure_selected_field(payload)
    sync_contract_inputs(payload, force=True)
    sync_schema_inputs(payload, force=True)
    sync_field_inputs(payload, force=True)
    st.rerun()


def validate_raw_yaml(raw_yaml: str) -> None:
    """Validate raw YAML without applying it."""
    if not raw_yaml.strip():
        st.session_state["editor_warning"] = "Contract YAML cannot be empty."
        return
    try:
        parse_yaml_payload(raw_yaml)
    except Exception as exc:
        from contracthub.exceptions import ContractHubError

        error_message = (
            exc.message
            if isinstance(exc, ContractHubError) and hasattr(exc, "message")
            else str(exc)
        )
        st.session_state["editor_error"] = f"Validation failed: {error_message}"
        return
    st.session_state["editor_notice"] = "Raw YAML is valid."
    st.session_state["editor_warning"] = None
    st.session_state["editor_error"] = None
