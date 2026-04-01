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
    st.session_state["editor_selected_schema_name"] = ""
    st.session_state["editor_selected_field_name"] = ""
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
    st.session_state["editor_selected_field_name"] = ""
    ensure_selected_field(contract)
    sync_schema_inputs(contract, force=True)
    sync_field_inputs(contract, force=True)


def handle_field_change() -> None:
    """Sync field UI when the selected field changes."""
    contract = st.session_state.get("contract")
    if not isinstance(contract, dict):
        return
    sync_field_inputs(contract, force=True)


def ensure_selected_schema(contract: dict[str, Any]) -> None:
    """Ensure the selected schema name is valid."""
    schemas = schema_items(contract)
    if not schemas:
        st.session_state["editor_selected_schema_name"] = ""
        return

    schema_names = [_schema_identity(schema, index) for index, schema in enumerate(schemas)]
    selected_name = str(st.session_state.get("editor_selected_schema_name", "") or "").strip()
    if selected_name not in schema_names:
        st.session_state["editor_selected_schema_name"] = schema_names[0]


def ensure_selected_field(contract: dict[str, Any]) -> None:
    """Ensure the selected field name is valid for the current schema."""
    current_schema = selected_schema(contract)
    if current_schema is None:
        st.session_state["editor_selected_field_name"] = ""
        return

    fields = current_schema.get("properties", []) or []
    field_names = [_field_identity(field, index) for index, field in enumerate(fields) if isinstance(field, dict)]
    if not field_names:
        st.session_state["editor_selected_field_name"] = ""
        return
    selected_name = str(st.session_state.get("editor_selected_field_name", "") or "").strip()
    if selected_name not in field_names:
        st.session_state["editor_selected_field_name"] = field_names[0]


def selected_schema(contract: dict[str, Any]) -> dict[str, Any] | None:
    """Return the currently selected schema."""
    all_schemas = schema_items(contract)
    if not all_schemas:
        return None
    selected_name = str(st.session_state.get("editor_selected_schema_name", "") or "").strip()
    for index, schema in enumerate(all_schemas):
        if _schema_identity(schema, index) == selected_name:
            return schema
    return all_schemas[0]


def selected_field(contract: dict[str, Any]) -> dict[str, Any] | None:
    """Return the currently selected field."""
    current_schema = selected_schema(contract)
    if current_schema is None:
        return None
    fields = current_schema.get("properties", []) or []
    if not fields:
        return None
    selected_name = str(st.session_state.get("editor_selected_field_name", "") or "").strip()
    for index, field in enumerate(fields):
        if isinstance(field, dict) and _field_identity(field, index) == selected_name:
            return field
    for field in fields:
        if isinstance(field, dict):
            return field
    return None


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
    selected_key = str(st.session_state.get("editor_selected_schema_name", "") or "")
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
        f"{st.session_state.get('editor_selected_schema_name', '')}:"
        f"{st.session_state.get('editor_selected_field_name', '')}"
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


def _schema_identity(schema: dict[str, Any], index: int) -> str:
    """Return the stable schema identity used by the editor."""
    name = str(schema.get("name", "") or "").strip()
    return name or f"schema_{index + 1}"


def _field_identity(field: dict[str, Any], index: int) -> str:
    """Return the stable field identity used by the editor."""
    name = str(field.get("name", "") or "").strip()
    return name or f"field_{index + 1}"
