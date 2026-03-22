"""UI section renderers for the Streamlit editor."""

from __future__ import annotations

from typing import Any

import streamlit as st

from .analysis import field_governance_info_for
from .constants import LIFECYCLE_OPTIONS, QUALITY_SEVERITY_OPTIONS, QUALITY_TYPE_OPTIONS, TABLE_RULE_COLUMN
from .contract_model import (
    add_quality_rule,
    apply_field_detail,
    apply_quality_rows,
    apply_quick_field_rows,
    contract_api_version,
    contract_data_product,
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
    field_option_label,
    field_type,
    is_technical_editor_column,
    is_technical_property_key,
    quality_rows,
    quick_field_rows,
    schema_label,
    selected_schema_field_names,
    server_items,
    server_label,
    set_contract_description_part,
    set_contract_tags_list,
    schema_items,
)
from .helpers import (
    display_value,
    editor_dataframe,
    normalize_tags,
    render_data_editor,
    render_tag_badges,
    render_tags_editor,
    rows_from_dataframe,
    selectbox_index,
    tags_to_text,
    text_to_tags,
)
from .state import selected_schema
from .styles import section_title


def render_contract_section(contract: dict[str, Any]) -> None:
    """Render always-visible contract metadata."""
    section_title("Contract", "Business-facing contract context and descriptive metadata.")
    st.markdown("#### Core Info")
    core_row_1 = st.columns([1.1, 0.9, 0.8], gap="large")
    with core_row_1[0]:
        st.text_input(
            "Data Product",
            value=display_value(contract_data_product(contract)),
            key="editor_contract_data_product_primary_display",
            disabled=True,
        )
    with core_row_1[1]:
        st.text_input(
            "Version",
            value=display_value(contract_version(contract)),
            key="editor_contract_version_display",
            disabled=True,
        )
    with core_row_1[2]:
        st.text_input(
            "Status",
            value=display_value(contract_status(contract)),
            key="editor_contract_status_display",
            disabled=True,
        )

    core_row_2 = st.columns(3, gap="large")
    with core_row_2[0]:
        st.text_input(
            "Domain",
            value=display_value(str(contract.get("domain", "") or "")),
            key="editor_contract_domain_display",
            disabled=True,
        )
    with core_row_2[1]:
        st.text_input(
            "Tenant",
            value=display_value(contract_tenant(contract)),
            key="editor_contract_tenant_display",
            disabled=True,
        )
    with core_row_2[2]:
        st.text_input(
            "Contract Name",
            value=display_value(contract_name(contract)),
            key="editor_contract_name_display",
            disabled=True,
            help="Optional ODCS name. Many contracts use Data Product as the primary business identifier.",
        )

    edited_contract_tags = render_tags_editor(contract_tags(contract), state_prefix="editor_contract", label="Tags")

    st.markdown("#### Description")
    purpose_col, limitations_col, usage_col = st.columns(3, gap="large")
    with purpose_col:
        contract_purpose = st.text_area("Purpose", key="editor_contract_description_purpose_input", height=140)
    with limitations_col:
        contract_limitations = st.text_area(
            "Limitations",
            key="editor_contract_description_limitations_input",
            height=140,
        )
    with usage_col:
        contract_usage = st.text_area("Usage", key="editor_contract_description_usage_input", height=140)

    with st.expander("System Fields", expanded=False):
        system_col_1, system_col_2, system_col_3 = st.columns(3, gap="large")
        with system_col_1:
            st.text_input("apiVersion", value=contract_api_version(contract), key="editor_contract_api_version_input", disabled=True)
        with system_col_2:
            st.text_input("kind", value=contract_kind(contract), key="editor_contract_kind_input", disabled=True)
        with system_col_3:
            st.text_input("id", value=display_value(contract_id(contract)), key="editor_contract_id_display", disabled=True)

    set_contract_tags_list(contract, edited_contract_tags)
    set_contract_description_part(contract, "purpose", contract_purpose)
    set_contract_description_part(contract, "limitations", contract_limitations)
    set_contract_description_part(contract, "usage", contract_usage)


def render_schema_selector(contract: dict[str, Any], on_change: Any) -> None:
    """Render shared schema selection controls."""
    section_title("Schema", "Review table-level metadata and switch between schemas without leaving the editor.")
    schema_indexes = list(range(len(schema_items(contract))))
    if not schema_indexes:
        st.warning("No schemas defined in this contract.")
        return

    selector_col, metrics_col = st.columns([1.0, 1.2], gap="large")
    with selector_col:
        st.selectbox(
            "Select Schema",
            options=schema_indexes,
            format_func=lambda idx: schema_label(contract, idx),
            key="editor_selected_schema_index",
            on_change=on_change,
        )

    current_schema = selected_schema(contract)
    if current_schema is None:
        return

    field_rows = quick_field_rows(current_schema)
    with metrics_col:
        metric_1, metric_2, metric_3 = st.columns(3, gap="medium")
        with metric_1:
            st.metric("Fields", len(field_rows))
        with metric_2:
            st.metric("Active", sum(1 for row in field_rows if str(row.get("lifecycleStatus", "")).lower() == "active"))
        with metric_3:
            st.metric(
                "Deprecated",
                sum(1 for row in field_rows if str(row.get("lifecycleStatus", "")).lower() == "deprecated"),
            )


def render_schema_tab(contract: dict[str, Any]) -> None:
    """Render schema editing modes for the selected schema."""
    current_schema = selected_schema(contract)
    if current_schema is None:
        st.warning("No schema selected.")
        return

    schema_meta_col_1, schema_meta_col_2, schema_meta_col_3 = st.columns(3, gap="large")
    with schema_meta_col_1:
        schema_name = st.text_input("Schema Name", key="editor_schema_name_input")
    with schema_meta_col_2:
        business_name = st.text_input("Business Name", key="editor_schema_business_name_input")
    with schema_meta_col_3:
        tags = render_tags_editor(
            current_schema.get("tags"),
            state_prefix=f"editor_schema_{st.session_state.get('editor_selected_schema_index', 0)}",
            label="Tags",
        )
    description = st.text_area("Table Description", key="editor_schema_description_input", height=100)

    if schema_name != str(current_schema.get("name", "")):
        current_schema["name"] = schema_name
        st.session_state["editor_selected_schema_source"] = None
        st.rerun()
    if business_name != str(current_schema.get("businessName", "")):
        current_schema["businessName"] = business_name
    if description != str(current_schema.get("description", "") or ""):
        if description.strip():
            current_schema["description"] = description
        else:
            current_schema.pop("description", None)
    if tags != normalize_tags(current_schema.get("tags")):
        current_schema["tags"] = tags

    detail_mode = st.toggle("Detail Edit", key="editor_schema_detail_mode")

    if not detail_mode:
        quick_rows = quick_field_rows(current_schema)
        edited_df = render_data_editor(
            editor_dataframe(
                quick_rows,
                columns=[
                    "name",
                    "businessName",
                    "type",
                    "required",
                    "lifecycleStatus",
                    "description",
                    "__original_index",
                ],
            ),
            num_rows="fixed",
            width="stretch",
            hide_index=True,
            column_order=["name", "businessName", "type", "required", "lifecycleStatus", "description"],
            column_config={
                "name": st.column_config.TextColumn("name"),
                "businessName": st.column_config.TextColumn("business name"),
                "type": st.column_config.TextColumn("type"),
                "required": st.column_config.CheckboxColumn("required"),
                "lifecycleStatus": st.column_config.SelectboxColumn("lifecycleStatus", options=LIFECYCLE_OPTIONS),
                "description": st.column_config.TextColumn("description"),
                "__original_index": None,
            },
            disabled=[column for column in ["name", "type", "required"] if is_technical_editor_column(column)],
            key="editor_schema_table",
        )
        edited_rows = rows_from_dataframe(edited_df)
        if edited_rows != quick_rows:
            apply_quick_field_rows(current_schema, edited_rows)
        return

    fields = current_schema.get("properties", []) or []
    if not fields:
        st.caption("No fields in the selected schema.")
        return

    st.markdown("#### Field Detail")
    st.caption("Expand a field to review or edit business metadata while keeping technical schema details read-only.")
    for index, field_obj in enumerate(fields):
        with st.expander(_field_list_label(field_obj, index), expanded=False):
            _render_field_detail_form(current_schema, field_obj, index)


def _field_list_label(field_obj: dict[str, Any], index: int) -> str:
    """Render a compact field list label."""
    label = field_option_label(field_obj, index)
    business_name = str(field_obj.get("businessName", "") or "").strip()
    if business_name:
        return f"{label} | {business_name}"
    return label


def _render_field_detail_form(schema_obj: dict[str, Any], field_obj: dict[str, Any], index: int) -> None:
    """Render a clean per-field detail form inside an expander."""
    summary_col_1, summary_col_2, summary_col_3 = st.columns(3, gap="medium")
    with summary_col_1:
        st.text_input("Field Name", value=str(field_obj.get("name", "") or ""), disabled=True, key=f"editor_field_name_display_{index}")
    with summary_col_2:
        st.text_input("Type", value=field_type(field_obj), disabled=True, key=f"editor_field_type_display_{index}")
    with summary_col_3:
        st.text_input(
            "Lifecycle",
            value=field_lifecycle_status(field_obj) or "draft",
            disabled=True,
            key=f"editor_field_lifecycle_display_{index}",
        )

    with st.form(
        key=(
            f"editor_field_form_{st.session_state.get('editor_selected_schema_index', 0)}_"
            f"{index}"
        )
    ):
        detail_left, detail_right = st.columns([1.15, 0.85], gap="large")

        with detail_left:
            field_lifecycle = st.selectbox(
                "Lifecycle Status",
                LIFECYCLE_OPTIONS,
                index=selectbox_index(LIFECYCLE_OPTIONS, field_lifecycle_status(field_obj) or "draft"),
            )
            field_business_name = st.text_input("Business Name", value=str(field_obj.get("businessName", "") or ""))
            field_description = st.text_area(
                "Description",
                value=str(field_obj.get("description", "") or ""),
                height=150,
            )
            field_examples = st.text_area("Examples", value=field_examples_text(field_obj), height=110)
            field_tags = st.text_input(
                "Tags",
                value=tags_to_text(field_obj.get("tags")),
                help="Comma-separated field tags.",
            )
            render_tag_badges(normalize_tags(field_obj.get("tags")))
            field_classification = st.text_input(
                "Classification",
                value=str(field_obj.get("classification", "") or ""),
            )
            field_transform_description = st.text_area(
                "Transform Description",
                value=str(field_obj.get("transformDescription", "") or ""),
                height=100,
            )

        with detail_right:
            st.caption("Technical Fields")
            st.text_input("Name", value=str(field_obj.get("name", "") or ""), disabled=is_technical_property_key("name"))
            st.text_input("Type", value=field_type(field_obj), disabled=is_technical_editor_column("type"))
            st.checkbox(
                "Required",
                value=bool(field_obj.get("required", False)),
                disabled=is_technical_property_key("required"),
            )
            st.text_input("Physical Name", value=str(field_obj.get("physicalName", "") or ""), disabled=True)
            logical_type = str(field_obj.get("logicalType", "") or "")
            physical_type = str(field_obj.get("physicalType", "") or "")
            if logical_type:
                st.text_input("Logical Type", value=logical_type, disabled=True)
            if physical_type:
                st.text_input("Physical Type", value=physical_type, disabled=True)
            if field_obj.get("format") is not None:
                st.text_input("Format", value=str(field_obj.get("format", "") or ""), disabled=True)
            if field_obj.get("pattern") is not None:
                st.text_input("Pattern", value=str(field_obj.get("pattern", "") or ""), disabled=True)

            governance_info = field_governance_info_for(schema_obj, field_obj)
            st.caption("Governance Hints")
            st.write(f"Breaking: {'Yes' if governance_info['breaking'] else 'No'}")
            st.write(f"Deprecated: {'Yes' if governance_info['deprecation'] else 'No'}")

        if st.form_submit_button(f"Save {field_option_label(field_obj, index)}", width="stretch"):
            apply_field_detail(
                field_obj,
                lifecycle_status=field_lifecycle,
                business_name=field_business_name,
                description=field_description,
                examples_text=field_examples,
                tags_text=field_tags,
                classification=field_classification,
                transform_description=field_transform_description,
            )
            st.session_state["editor_notice"] = f"Field '{field_obj.get('name', '')}' changes saved."
            st.rerun()


def render_quality_tab(contract: dict[str, Any]) -> None:
    """Render quality rules for the selected schema."""
    current_schema = selected_schema(contract)
    if current_schema is None:
        st.warning("No schema selected.")
        return

    section_title("Quality Rules", "Maintain business-facing validation rules for the selected schema.")

    left_col, right_col = st.columns([1.5, 0.6], gap="large")
    field_names = [name for name in selected_schema_field_names(current_schema) if name]
    column_options = [TABLE_RULE_COLUMN, *field_names]
    current_quality_rows = quality_rows(current_schema)

    with right_col:
        st.markdown("#### Actions")
        if st.button("Add Rule", width="stretch"):
            add_quality_rule(current_schema)
            st.rerun()
        st.caption("Table-level rules use `__table__`.")

    with left_col:
        edited_df = render_data_editor(
            editor_dataframe(
                current_quality_rows,
                columns=[
                    "rule_name",
                    "type",
                    "column",
                    "condition",
                    "severity",
                    "__scope",
                    "__rule_index",
                    "__property_name",
                    "__condition_key",
                ],
            ),
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_order=["rule_name", "type", "column", "condition", "severity"],
            column_config={
                "rule_name": st.column_config.TextColumn("rule_name", required=True),
                "type": st.column_config.SelectboxColumn("type", options=QUALITY_TYPE_OPTIONS),
                "column": st.column_config.SelectboxColumn("column", options=column_options, required=True),
                "condition": st.column_config.TextColumn("condition"),
                "severity": st.column_config.SelectboxColumn("severity", options=QUALITY_SEVERITY_OPTIONS),
                "__scope": None,
                "__rule_index": None,
                "__property_name": None,
                "__condition_key": None,
            },
            key="editor_quality_table",
        )

    edited_rows = rows_from_dataframe(edited_df)
    if edited_rows != current_quality_rows:
        apply_quality_rows(current_schema, edited_rows)


def render_infrastructure_section(contract: dict[str, Any]) -> None:
    """Render read-only infrastructure and data-access information."""
    section_title("Infrastructure / Data Access", "Read-only deployment and access details for the selected contract.")
    servers = server_items(contract)
    if not servers:
        st.caption("No server information defined.")
        return

    server_indexes = list(range(len(servers)))
    selected_server_index = st.selectbox(
        "Select Server",
        options=server_indexes,
        format_func=lambda idx: server_label(servers[idx]),
        key="editor_selected_server_index",
    )
    server = servers[selected_server_index]

    business_col_1, business_col_2 = st.columns(2, gap="large")
    with business_col_1:
        st.text_input("Server", value=str(server.get("server", "") or ""), disabled=True)
        st.text_input("Environment", value=str(server.get("environment", "") or ""), disabled=True)
    with business_col_2:
        st.text_area("Description", value=str(server.get("description", "") or ""), height=100, disabled=True)

    with st.expander("Advanced Server Details", expanded=False):
        advanced_col_1, advanced_col_2 = st.columns(2, gap="large")
        with advanced_col_1:
            st.text_input("Type", value=str(server.get("type", "") or ""), disabled=True)
            st.markdown("Roles")
            roles = server.get("roles", []) or []
            if roles:
                for role in roles:
                    st.write(f"- {role}")
            else:
                st.caption("No roles defined.")
        with advanced_col_2:
            st.markdown("Custom Properties")
            st.json(server.get("customProperties", []))


def render_advanced_tab(contract: dict[str, Any], on_apply_yaml: Any, on_validate_yaml: Any, generated_yaml: str) -> None:
    """Render raw YAML with optional unsafe editing."""
    section_title("Advanced", "Technical views live here so the main editor stays business-friendly.")

    with st.expander("Raw YAML", expanded=True):
        st.code(generated_yaml, language="yaml")

    unsafe_enabled = st.toggle("Enable Unsafe Edit", value=False, key="editor_enable_unsafe_edit")
    if not unsafe_enabled:
        st.session_state["editor_raw_yaml"] = generated_yaml
        return

    st.warning("Editing YAML directly may break governance rules.")
    raw_yaml = st.text_area("Raw YAML", key="editor_raw_yaml", height=320)
    action_col, validate_col = st.columns(2, gap="large")
    with action_col:
        if st.button("Apply YAML Changes", width="stretch"):
            on_apply_yaml(raw_yaml)
    with validate_col:
        if st.button("Validate YAML", width="stretch"):
            on_validate_yaml(raw_yaml)
