import pytest
from pathlib import Path

from contracthub.exporters.graph_exporter import GraphExporter

@pytest.fixture
def sample_graph_yaml() -> Path:
    fixture_path = Path("tests/fixtures/contracts/odcs/graph_sample.yaml")
    return fixture_path

def test_graph_exporter_nodes(sample_graph_yaml):
    nodes, edges = GraphExporter.from_yaml(sample_graph_yaml)

    assert len(nodes) == 10

    node_names = {n.name for n in nodes}
    assert "users" in node_names
    assert "orders" in node_names
    assert "loyalty_members" in node_names
    assert "user_products_junction" in node_names

def test_graph_exporter_edges(sample_graph_yaml):
    nodes, edges = GraphExporter.from_yaml(sample_graph_yaml)

    assert len(edges) == 9

    # Check explicit label
    edge1 = next(e for e in edges if e.label == "PLACED_BY")
    assert edge1.source == "orders"
    assert edge1.target == "users"
    assert edge1.is_junction_edge is False

    # Check junction edge marking
    edge2 = next(e for e in edges if e.target == "loyalty_members")
    assert edge2.source == "orders"
    assert edge2.label == "LOYALTY_MEMBERS" # fallback
    assert edge2.is_junction_edge is True

    # Check another fallback
    edge3 = next(e for e in edges if e.label == "PRODUCTS" and e.source == "orders")
    assert edge3.source == "orders"
    assert edge3.target == "products"
    assert edge3.is_junction_edge is False

    # Check schema level self reference
    edge4 = next(e for e in edges if e.source == "employees" and e.target == "employees")
    assert edge4.source == "employees"
    assert edge4.label == "EMPLOYEES"
