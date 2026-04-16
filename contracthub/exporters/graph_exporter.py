from dataclasses import dataclass
from typing import List, Union, Dict, Any
from pathlib import Path

from open_data_contract_standard.model import OpenDataContractStandard
from contracthub.utils.schema_utils import contract_to_model
from datacontract.export.exporter import Exporter

@dataclass
class GraphNode:
    name: str

@dataclass
class GraphEdge:
    source: str
    target: str
    label: str
    is_junction_edge: bool = False

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

        for schema_obj in (data_contract.schema_ or []):
            if schema_name != "all" and schema_obj.name != schema_name:
                continue

            table_name = schema_obj.name

            nodes.append(GraphNode(name=table_name))

            # Extract edges from properties
            for prop in (schema_obj.properties or []):
                for rel in (prop.relationships or []):
                    # Target table extraction
                    target_table = None
                    to_field = getattr(rel, "from_", rel.to) if not rel.to else rel.to

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
                            if cp.value is True or str(cp.value).lower() == "true":
                                is_junction_edge = True

                    edges.append(GraphEdge(
                        source=table_name,
                        target=target_table,
                        label=edge_label,
                        is_junction_edge=is_junction_edge
                    ))

        return nodes, edges

    @classmethod
    def from_yaml(cls, file_path: Union[str, Path]) -> tuple[List[GraphNode], List[GraphEdge]]:
        contract = contract_to_model(file_path)
        exporter = cls()
        return exporter.export(data_contract=contract)
