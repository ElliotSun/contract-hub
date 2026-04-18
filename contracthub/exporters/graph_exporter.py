import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Union, Dict, Any
from pathlib import Path

from open_data_contract_standard.model import OpenDataContractStandard
from contracthub.utils.schema_utils import contract_to_model
from datacontract.export.exporter import Exporter

@dataclass
class GraphNode:
    name: str
    id: str = ""
    type: str = "Table"
    properties: Dict[str, Any] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}
        if not self.id:
            self.id = self.name

@dataclass
class GraphEdge:
    source: str
    target: str
    label: str
    is_junction_edge: bool = False
    type: str = ""
    properties: Dict[str, Any] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}
        if not self.type:
            self.type = self.label

class BaseSerializer(ABC):
    @abstractmethod
    def serialize(self, nodes: List[GraphNode], edges: List[GraphEdge]) -> str:
        pass


class CypherSerializer(BaseSerializer):
    def _format_properties(self, properties: Dict[str, Any]) -> str:
        if not properties:
            return ""

        formatted_props = []
        for k, v in properties.items():
            if isinstance(v, str):
                v_escaped = json.dumps(v)
                formatted_props.append(f"{k}: {v_escaped}")
            elif isinstance(v, bool):
                formatted_props.append(f"{k}: {'true' if v else 'false'}")
            elif isinstance(v, (dict, list)):
                v_str = json.dumps(v)
                v_escaped = json.dumps(v_str)
                formatted_props.append(f"{k}: {v_escaped}")
            elif v is None:
                continue
            else:
                formatted_props.append(f"{k}: {v}")

        if not formatted_props:
            return ""

        return " {" + ", ".join(formatted_props) + "}"

    def serialize(self, nodes: List[GraphNode], edges: List[GraphEdge]) -> str:
        statements = []
        node_aliases = {}
        for idx, node in enumerate(nodes):
            alias = f"n_{idx}"
            node_aliases[node.id] = alias

            props = node.properties.copy() if node.properties else {}
            if "id" not in props:
                props["id"] = node.id

            props_str = self._format_properties(props)
            statements.append(f"CREATE ({alias}:{node.type}{props_str})")

        for edge in edges:
            source_alias = node_aliases.get(edge.source)
            target_alias = node_aliases.get(edge.target)

            if not source_alias or not target_alias:
                continue

            props_str = self._format_properties(edge.properties)
            statements.append(f"CREATE ({source_alias})-[:{edge.type}{props_str}]->({target_alias})")

        return "\n".join(statements)


class JsonSerializer(BaseSerializer):
    def serialize(self, nodes: List[GraphNode], edges: List[GraphEdge]) -> str:
        id_map = {}
        out_nodes = []

        for idx, node in enumerate(nodes):
            id_map[node.id] = idx

            props = node.properties.copy() if node.properties else {}

            out_node = {
                "id": idx,
                "original_id": node.id,
                "type": node.type,
                "properties": props
            }
            out_nodes.append(out_node)

        out_edges = []
        for edge in edges:
            source_idx = id_map.get(edge.source)
            target_idx = id_map.get(edge.target)

            if source_idx is None or target_idx is None:
                continue

            props = edge.properties.copy() if edge.properties else {}

            out_edge = {
                "source": source_idx,
                "target": target_idx,
                "type": edge.type,
                "properties": props
            }
            out_edges.append(out_edge)

        result = {
            "nodes": out_nodes,
            "edges": out_edges
        }

        return json.dumps(result, indent=2)


class GraphExporter(Exporter):
    def __init__(self, export_format: str = "graph"):
        super().__init__(export_format)

    def export(
        self,
        data_contract: OpenDataContractStandard,
        schema_name: str = "all",
        server: str = "",
        sql_server_type: str = "",
        export_args: Dict[str, Any] = None,
    ) -> tuple[List[GraphNode], List[GraphEdge]]:
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []

        def is_truthy(val) -> bool:
            if val is True:
                return True
            if isinstance(val, str) and val.lower() in ('true', '1'):
                return True
            if isinstance(val, int) and val == 1:
                return True
            return False

        for schema_obj in (data_contract.schema_ or []):
            if schema_name != "all" and schema_obj.name != schema_name:
                continue

            table_name = schema_obj.name

            # Add Table Node
            table_props = {}
            if schema_obj.description:
                table_props["description"] = schema_obj.description

            nodes.append(GraphNode(name=table_name, type="Table", properties=table_props))

            # Add Column Nodes and Edges
            for prop in (schema_obj.properties or []):
                col_id = f"{table_name}.{prop.name}"

                # Determine is_pii
                is_pii = False

                # ODCS officially supports `classification` (e.g. pii, restricted) and `tags`
                if prop.classification is not None:
                    cls_val = str(prop.classification).lower()
                    if 'pii' in cls_val or cls_val in ('restricted', 'confidential'):
                        is_pii = True

                if not is_pii and prop.tags:
                    if any(str(t).lower() == 'pii' for t in prop.tags):
                        is_pii = True

                # Custom Properties fallback for extensions
                if not is_pii and prop.customProperties:
                    for cp in prop.customProperties:
                        cp_prop = cp.property or (cp.get('property') if isinstance(cp, dict) else None)
                        cp_val = cp.value or (cp.get('value') if isinstance(cp, dict) else None)
                        if str(cp_prop).lower() == 'pii' and is_truthy(cp_val):
                            is_pii = True

                # Determine is_primary_key
                is_pk = False
                if prop.primaryKey is not None and is_truthy(prop.primaryKey):
                    is_pk = True

                # Determine logicalType
                logical_type = prop.logicalType

                # Example Value
                example_val = None
                if prop.examples and len(prop.examples) > 0:
                    example_val = prop.examples[0]

                col_props = {
                    "logicalType": logical_type,
                    "is_pii": is_pii,
                    "is_primary_key": is_pk,
                }
                if prop.description:
                    col_props["description"] = prop.description
                if prop.required is not None:
                    col_props["is_not_null"] = prop.required
                if prop.tags:
                    col_props["tags"] = prop.tags
                if example_val is not None:
                    col_props["example_value"] = str(example_val)

                nodes.append(GraphNode(name=col_id, id=col_id, type="Column", properties=col_props))

                # HAS_COLUMN edge
                edges.append(GraphEdge(source=table_name, target=col_id, label="HAS_COLUMN"))

            # Extract edges from relationships (schema and property level)
            rels = []
            rels.extend(schema_obj.relationships or [])
            for prop in (schema_obj.properties or []):
                rels.extend(prop.relationships or [])

            for rel in rels:
                # Target table extraction
                target_table = None
                to_field = rel.to
                if not to_field:
                    to_field = getattr(rel, "from_", None)

                if isinstance(to_field, str):
                    parts = to_field.split('.')
                    if len(parts) > 1:
                        target_table = parts[0]
                    else:
                        target_table = to_field
                elif isinstance(to_field, list) and len(to_field) > 0:
                    parts = to_field[0].split('.')
                    if len(parts) > 1:
                        target_table = parts[0]
                    else:
                        target_table = to_field[0]

                if not target_table:
                    continue

                # Semantic Edge Label and Junction Edge extraction
                edge_label = target_table.upper()
                is_junction_edge = False

                for cp in (rel.customProperties or []):
                    if cp.property == "graph_semantic.edge_label":
                        if isinstance(cp.value, str) and cp.value.strip():
                            edge_label = cp.value
                    elif cp.property == "graph_export.is_junction_edge":
                        if is_truthy(cp.value):
                            is_junction_edge = True

                edges.append(GraphEdge(
                    source=table_name,
                    target=target_table,
                    label=edge_label,
                    is_junction_edge=is_junction_edge
                ))

        actual_format = "graph"
        if export_args and "format" in export_args:
            actual_format = export_args["format"]

        if actual_format == "cypher":
            return CypherSerializer().serialize(nodes, edges)
        elif actual_format == "json":
            return JsonSerializer().serialize(nodes, edges)

        return nodes, edges

    @classmethod
    def from_yaml(cls, file_path: Union[str, Path], export_args: Dict[str, Any] = None) -> Union[tuple[List[GraphNode], List[GraphEdge]], str]:
        contract = contract_to_model(file_path)
        exporter = cls()
        return exporter.export(data_contract=contract, export_args=export_args)
