import pytest
from pathlib import Path
import json

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

from datacontract.data_contract import DataContract

def test_graph_exporter_cypher_from_yaml(sample_graph_yaml):
    contract = DataContract(data_contract_file=str(sample_graph_yaml))
    exporter = GraphExporter(export_format="graph")

    # Force the sdk to parse the contract (mimics CLI initialization)
    if contract.get_data_contract() is None:
        contract.get_data_contract() # Initialize cache

    contract_model = getattr(contract, "contract", getattr(contract, "_data_contract", contract.get_data_contract()))
    if contract_model is None:
        from contracthub.utils.schema_utils import contract_to_model
        contract_model = contract_to_model(sample_graph_yaml)

    result = exporter.export(data_contract=contract_model, export_args={"format": "cypher"})

    assert "CREATE" in result
    assert "MERGE" not in result

    # Simple check on one of the relationships and nodes to ensure proper format was achieved
    assert "[:PLACED_BY" in result
    # Check that self referencing mapping behaves properly within output sequence
    assert "[:EMPLOYEES" in result

def test_graph_exporter_json_from_yaml(sample_graph_yaml):
    contract = DataContract(data_contract_file=str(sample_graph_yaml))
    exporter = GraphExporter(export_format="graph")

    # Force the sdk to parse the contract (mimics CLI initialization)
    if contract.get_data_contract() is None:
        contract.get_data_contract() # Initialize cache

    contract_model = getattr(contract, "contract", getattr(contract, "_data_contract", contract.get_data_contract()))
    if contract_model is None:
        from contracthub.utils.schema_utils import contract_to_model
        contract_model = contract_to_model(sample_graph_yaml)

    result_str = exporter.export(data_contract=contract_model, export_args={"format": "json"})
    result = json.loads(result_str)

    assert "nodes" in result
    assert "edges" in result

    assert len(result["nodes"]) == 10
    assert len(result["edges"]) == 9

    # Assert zero indexing applies correctly
    ids = [n["id"] for n in result["nodes"]]
    assert min(ids) == 0
    assert max(ids) == 9

    # Assert mapping relationships
    placed_by_edge = next(e for e in result["edges"] if e["type"] == "PLACED_BY")
    assert placed_by_edge["source"] is not None
    assert placed_by_edge["target"] is not None
