import logging
from dataclasses import dataclass, field
from typing import List, Dict, Set

from contracthub.exporters.graph_exporter import GraphNode, GraphEdge

logger = logging.getLogger(__name__)

class TopologyValidationError(Exception):
    """Exception raised when topology validation fails."""
    pass

@dataclass
class GraphValidationReport:
    is_valid: bool
    missing_inbound_edges: List[str] = field(default_factory=list)
    island_tables: List[str] = field(default_factory=list)

class TopologyValidator:
    def validate(self, nodes: List[GraphNode], edges: List[GraphEdge]) -> GraphValidationReport:
        report = GraphValidationReport(is_valid=True)

        column_nodes = {node.id: node for node in nodes if node.type == "Column"}
        table_nodes = {node.id: node for node in nodes if node.type == "Table"}

        # Track inbound HAS_COLUMN edges
        has_column_targets: Set[str] = set()

        # Track semantic table-to-table edges
        table_connections: Dict[str, int] = {node_id: 0 for node_id in table_nodes}

        for edge in edges:
            if edge.type == "HAS_COLUMN" or edge.label == "HAS_COLUMN":
                has_column_targets.add(edge.target)
            else:
                # Semantic table-to-table edge
                # Check that BOTH source and target are tables to count as a table-to-table connection
                if edge.source in table_nodes and edge.target in table_nodes:
                    table_connections[edge.source] += 1
                    table_connections[edge.target] += 1

        for col_id in column_nodes:
            if col_id not in has_column_targets:
                report.missing_inbound_edges.append(col_id)
                report.is_valid = False

        for table_id, count in table_connections.items():
            if count == 0:
                report.island_tables.append(table_id)
                logger.warning(f"Table node '{table_id}' is acting as an absolute island (zero semantic edges to other tables).")

        if not report.is_valid:
            raise TopologyValidationError(
                f"Graph topology validation failed. Missing inbound HAS_COLUMN edges for columns: {', '.join(report.missing_inbound_edges)}"
            )

        return report
