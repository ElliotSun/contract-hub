import pytest
from pathlib import Path
import json

from contracthub.exporters.graph_exporter import GraphExporter
from datacontract.data_contract import DataContract

@pytest.fixture
def sample_graph_yaml() -> Path:
    fixture_path = Path("tests/fixtures/contracts/odcs/graph_sample.yaml")
    return fixture_path

def test_graph_exporter_nodes(sample_graph_yaml):
    nodes, edges = GraphExporter.from_yaml(sample_graph_yaml)

    # 10 tables + 20 columns = 30 nodes
    assert len(nodes) == 30

    node_names = {n.name for n in nodes}
    assert "users" in node_names
    assert "orders" in node_names
    assert "loyalty_members" in node_names
    assert "user_products_junction" in node_names
    assert "users.id" in node_names
    assert "users.email" in node_names

def test_graph_exporter_edges(sample_graph_yaml):
    nodes, edges = GraphExporter.from_yaml(sample_graph_yaml)

    # 9 table semantic edges + 20 HAS_COLUMN edges = 29 edges
    assert len(edges) == 29

    # Check explicit label (Table to Table)
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

    # Check HAS_COLUMN edges exist
    has_col_edges = [e for e in edges if e.label == "HAS_COLUMN"]
    assert len(has_col_edges) == 20
    user_id_col = next(e for e in has_col_edges if e.source == "users" and e.target == "users.id")
    assert user_id_col is not None

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
    assert "[:HAS_COLUMN" in result
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

    assert len(result["nodes"]) == 30
    assert len(result["edges"]) == 29

    # Assert zero indexing applies correctly
    ids = [n["id"] for n in result["nodes"]]
    assert min(ids) == 0
    assert max(ids) == 29

    # Assert mapping relationships
    placed_by_edge = next(e for e in result["edges"] if e["type"] == "PLACED_BY")
    assert placed_by_edge["source"] is not None
    assert placed_by_edge["target"] is not None
