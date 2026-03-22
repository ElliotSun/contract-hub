"""Session-state helpers for the Streamlit editor."""

from __future__ import annotations

from typing import Any

import streamlit as st

from contracthub.interfaces.streamlit.services.contract_service import load_sample_contract_yaml

from .contract_model import (
    contract_api_version,
    contract_data_product,
    contract_domain,
    contract_description_part,
    contract_id,
    contract_kind,
    contract_name,
    contract_status,
    contract_tags,
    contract_tenant,
    contract_version,
    field_examples_text,
    field_lifecycle_status,
    field_type,
    parse_yaml_payload,
    schema_items,
)
from .helpers import tags_to_text


def ensure_editor_state() -> None:
    """Initialize the editor state."""
    if "contract" not in st.session_state:
        sample_yaml = load_sample_contract_yaml()
        payload = parse_yaml_payload(sample_yaml)
        st.session_state["contract"] = payload
        st.session_state["editor_baseline_yaml"] = sample_yaml
        st.session_state["editor_raw_yaml"] = sample_yaml
        st.session_state["editor_notice"] = None
        st.session_state["editor_warning"] = None
        st.session_state["editor_error"] = None
        sync_contract_inputs(payload, force=True)

    contract = st.session_state.get("contract")
    if not isinstance(contract, dict):
        return

    if "editor_baseline_yaml" not in st.session_state:
        st.session_state["editor_baseline_yaml"] = load_sample_contract_yaml()
    if "editor_notice" not in st.session_state:
        st.session_state["editor_notice"] = None
    if "editor_warning" not in st.session_state:
        st.session_state["editor_warning"] = None
    if "editor_error" not in st.session_state:
        st.session_state["editor_error"] = None

    ensure_selected_schema(contract)
    ensure_selected_field(contract)
    sync_contract_inputs(contract)
    sync_schema_inputs(contract)
    sync_field_inputs(contract)


def reset_editor_state() -> None:
    """Reset the editor to the sample contract."""
    sample_yaml = load_sample_contract_yaml()
    payload = parse_yaml_payload(sample_yaml)
    st.session_state["contract"] = payload
    st.session_state["editor_baseline_yaml"] = sample_yaml
    st.session_state["editor_raw_yaml"] = sample_yaml
    st.session_state["editor_selected_schema_index"] = 0
    st.session_state["editor_selected_field_index"] = 0
    st.session_state["editor_analysis_result"] = None
    st.session_state["editor_notice"] = None
    st.session_state["editor_warning"] = None
    st.session_state["editor_error"] = None
    sync_contract_inputs(payload, force=True)
    sync_schema_inputs(payload, force=True)
    sync_field_inputs(payload, force=True)


def handle_schema_change() -> None:
    """Sync schema and field UI when the selected schema changes."""
    contract = st.session_state.get("contract")
    if not isinstance(contract, dict):
        return
    st.session_state["editor_selected_field_index"] = 0
    sync_schema_inputs(contract, force=True)
    sync_field_inputs(contract, force=True)


def handle_field_change() -> None:
    """Sync field UI when the selected field changes."""
    contract = st.session_state.get("contract")
    if not isinstance(contract, dict):
        return
    sync_field_inputs(contract, force=True)


def ensure_selected_schema(contract: dict[str, Any]) -> None:
    """Ensure the selected schema index is valid."""
    schema_count = len(schema_items(contract))
    selected_index = st.session_state.get("editor_selected_schema_index", 0)
    if not isinstance(selected_index, int) or selected_index < 0 or selected_index >= schema_count:
        st.session_state["editor_selected_schema_index"] = 0


def ensure_selected_field(contract: dict[str, Any]) -> None:
    """Ensure the selected field index is valid for the current schema."""
    current_schema = selected_schema(contract)
    if current_schema is None:
        st.session_state["editor_selected_field_index"] = 0
        return
    field_count = len(current_schema.get("properties", []) or [])
    selected_index = st.session_state.get("editor_selected_field_index", 0)
    if field_count == 0:
        st.session_state["editor_selected_field_index"] = 0
        return
    if not isinstance(selected_index, int) or selected_index < 0 or selected_index >= field_count:
        st.session_state["editor_selected_field_index"] = 0


def selected_schema(contract: dict[str, Any]) -> dict[str, Any] | None:
    """Return the currently selected schema."""
    all_schemas = schema_items(contract)
    if not all_schemas:
        return None
    return all_schemas[st.session_state.get("editor_selected_schema_index", 0)]


def selected_field(contract: dict[str, Any]) -> dict[str, Any] | None:
    """Return the currently selected field."""
    current_schema = selected_schema(contract)
    if current_schema is None:
        return None
    fields = current_schema.get("properties", []) or []
    if not fields:
        return None
    field_index = st.session_state.get("editor_selected_field_index", 0)
    if field_index >= len(fields):
        return None
    return fields[field_index]


def sync_contract_inputs(contract: dict[str, Any], *, force: bool = False) -> None:
    """Sync contract tab inputs from the working contract."""
    if force or "editor_contract_name_input" not in st.session_state:
        st.session_state["editor_contract_name_input"] = contract_name(contract)
    if force or "editor_contract_version_input" not in st.session_state:
        st.session_state["editor_contract_version_input"] = contract_version(contract)
    if force or "editor_contract_status_input" not in st.session_state:
        st.session_state["editor_contract_status_input"] = contract_status(contract) or "draft"
    if force or "editor_contract_domain_input" not in st.session_state:
        st.session_state["editor_contract_domain_input"] = contract_domain(contract)
    if force or "editor_contract_data_product_input" not in st.session_state:
        st.session_state["editor_contract_data_product_input"] = contract_data_product(contract)
    if force or "editor_contract_tenant_input" not in st.session_state:
        st.session_state["editor_contract_tenant_input"] = contract_tenant(contract)
    if force or "editor_contract_description_purpose_input" not in st.session_state:
        st.session_state["editor_contract_description_purpose_input"] = contract_description_part(contract, "purpose")
    if force or "editor_contract_description_limitations_input" not in st.session_state:
        st.session_state["editor_contract_description_limitations_input"] = contract_description_part(contract, "limitations")
    if force or "editor_contract_description_usage_input" not in st.session_state:
        st.session_state["editor_contract_description_usage_input"] = contract_description_part(contract, "usage")
    if force or "editor_contract_tags_input" not in st.session_state:
        st.session_state["editor_contract_tags_input"] = tags_to_text(contract_tags(contract))
    if force or "editor_contract_id_input" not in st.session_state:
        st.session_state["editor_contract_id_input"] = contract_id(contract)
    if force or "editor_contract_api_version_input" not in st.session_state:
        st.session_state["editor_contract_api_version_input"] = contract_api_version(contract)
    if force or "editor_contract_kind_input" not in st.session_state:
        st.session_state["editor_contract_kind_input"] = contract_kind(contract)


def sync_schema_inputs(contract: dict[str, Any], *, force: bool = False) -> None:
    """Sync selected-schema inputs from the working contract."""
    current_schema = selected_schema(contract)
    if current_schema is None:
        return
    selected_key = str(st.session_state.get("editor_selected_schema_index", 0))
    if not force and st.session_state.get("editor_selected_schema_source") == selected_key:
        return
    st.session_state["editor_schema_name_input"] = str(current_schema.get("name", ""))
    st.session_state["editor_schema_business_name_input"] = str(current_schema.get("businessName", ""))
    st.session_state["editor_schema_description_input"] = str(current_schema.get("description", "") or "")
    st.session_state["editor_schema_tags_input"] = tags_to_text(current_schema.get("tags"))
    st.session_state["editor_selected_schema_source"] = selected_key


def sync_field_inputs(contract: dict[str, Any], *, force: bool = False) -> None:
    """Sync selected-field detail inputs from the working contract."""
    current_field = selected_field(contract)
    selected_key = (
        f"{st.session_state.get('editor_selected_schema_index', 0)}:"
        f"{st.session_state.get('editor_selected_field_index', 0)}"
    )
    if current_field is None:
        return
    if not force and st.session_state.get("editor_selected_field_source") == selected_key:
        return
    st.session_state["editor_field_name_input"] = str(current_field.get("name", ""))
    st.session_state["editor_field_type_input"] = field_type(current_field)
    st.session_state["editor_field_required_input"] = bool(current_field.get("required", False))
    st.session_state["editor_field_lifecycle_input"] = field_lifecycle_status(current_field) or "draft"
    st.session_state["editor_field_business_name_input"] = str(current_field.get("businessName", ""))
    st.session_state["editor_field_description_input"] = str(current_field.get("description", "") or "")
    st.session_state["editor_field_examples_input"] = field_examples_text(current_field)
    st.session_state["editor_field_tags_input"] = tags_to_text(current_field.get("tags"))
    st.session_state["editor_field_classification_input"] = str(current_field.get("classification", "") or "")
    st.session_state["editor_field_transform_description_input"] = str(current_field.get("transformDescription", "") or "")
    st.session_state["editor_field_physical_name_input"] = str(current_field.get("physicalName", "") or "")
    st.session_state["editor_selected_field_source"] = selected_key
