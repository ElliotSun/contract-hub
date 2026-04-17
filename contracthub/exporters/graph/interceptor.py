from typing import List

from open_data_contract_standard.model import OpenDataContractStandard
from contracthub.exporters.graph_exporter import GraphNode

class SovereigntyInterceptor:
    def intercept(self, contract: OpenDataContractStandard, nodes: List[GraphNode]) -> None:
        # Create a mapping of (table_name, column_name) to PII status from the contract
        pii_columns = set()

        def is_pii_val(val) -> bool:
            if val is True:
                return True
            if isinstance(val, str):
                v_lower = val.lower()
                # Consider it PII if explicitly true or classified as restricted/confidential/pii
                if 'pii' in v_lower or v_lower in ('true', '1', 'restricted', 'confidential'):
                    return True
            if isinstance(val, int) and val == 1:
                return True
            return False

        # Check models format (v2 legacy)
        models = getattr(contract, 'models', {})
        if models:
            for model_name, model_def in models.items():
                fields = getattr(model_def, 'fields', {})
                for field_name, field_def in fields.items():
                    is_pii = False

                    if hasattr(field_def, 'pii') and is_pii_val(getattr(field_def, 'pii')):
                        is_pii = True
                    elif hasattr(field_def, 'classification') and is_pii_val(getattr(field_def, 'classification')):
                        is_pii = True
                    elif hasattr(field_def, '__pydantic_extra__') and field_def.__pydantic_extra__:
                        if is_pii_val(field_def.__pydantic_extra__.get('pii')) or is_pii_val(field_def.__pydantic_extra__.get('classification')):
                            is_pii = True
                    if not is_pii and hasattr(field_def, 'tags'):
                        tags = getattr(field_def, 'tags', [])
                        if tags and any(str(t).lower() == 'pii' for t in tags):
                            is_pii = True

                    if is_pii:
                        pii_columns.add((model_name.lower(), field_name.lower()))

        # Check schema format (v3)
        for schema_obj in (contract.schema_ or []):
            table_name = getattr(schema_obj, 'name', None)
            if not table_name:
                continue

            for prop in (schema_obj.properties or []):
                prop_name = getattr(prop, 'name', None)
                if not prop_name:
                    continue

                is_pii = False

                # In ODCS v3, PII is denoted via classification or tags typically.
                if hasattr(prop, 'classification') and is_pii_val(getattr(prop, 'classification')):
                    is_pii = True

                # Also check pii field explicitly in case it's added via pydantic extras or old versions
                if not is_pii and hasattr(prop, 'pii') and is_pii_val(getattr(prop, 'pii')):
                    is_pii = True

                if not is_pii and getattr(prop, 'customProperties', []):
                    for cp in getattr(prop, 'customProperties', []):
                        cp_prop = getattr(cp, 'property', None) or (cp.get('property') if isinstance(cp, dict) else None)
                        cp_val = getattr(cp, 'value', None) or (cp.get('value') if isinstance(cp, dict) else None)
                        if str(cp_prop).lower() == 'pii' and is_pii_val(cp_val):
                            is_pii = True

                if not is_pii and hasattr(prop, '__pydantic_extra__') and prop.__pydantic_extra__:
                    if is_pii_val(prop.__pydantic_extra__.get('pii')) or is_pii_val(prop.__pydantic_extra__.get('classification')):
                        is_pii = True

                if not is_pii and hasattr(prop, 'model_dump'):
                    try:
                        d = prop.model_dump(exclude_unset=False, by_alias=True)
                        if is_pii_val(d.get('pii')) or is_pii_val(d.get('classification')):
                            is_pii = True
                        if d.get('tags') and any(str(t).lower() == 'pii' for t in d.get('tags', [])):
                            is_pii = True
                    except Exception:
                        pass

                if not is_pii and hasattr(prop, '__dict__'):
                    if is_pii_val(prop.__dict__.get('pii')) or is_pii_val(prop.__dict__.get('classification')):
                        is_pii = True
                    if prop.__dict__.get('tags') and any(str(t).lower() == 'pii' for t in prop.__dict__.get('tags', [])):
                        is_pii = True

                if not is_pii and getattr(prop, 'tags', []):
                    tags = getattr(prop, 'tags', [])
                    if tags and any(str(t).lower() == 'pii' for t in tags):
                        is_pii = True

                if is_pii:
                    pii_columns.add((table_name.lower(), prop_name.lower()))

        for node in nodes:
            if node.type == "Column":
                table_name = None
                column_name = None

                if node.properties:
                    # check schema.name and property.name as requested
                    table_name = node.properties.get("schema.name") or node.properties.get("table_name")
                    column_name = node.properties.get("property.name") or node.properties.get("name")

                if not table_name or not column_name:
                    parts = node.id.split('.')
                    if len(parts) >= 2:
                        table_name = parts[0]
                        column_name = parts[-1]
                    else:
                        continue

                if table_name and column_name:
                    if (table_name.lower(), column_name.lower()) in pii_columns:
                        if node.properties is None:
                            node.properties = {}
                        node.properties["example_value"] = "[REDACTED_PII]"
