import pytest
from pathlib import Path
from contracthub.exporters.builder import InMemoryGraphBuilder
from open_data_contract_standard.model import OpenDataContractStandard

@pytest.fixture
def sample_graph_yaml_path() -> Path:
    return Path("tests/fixtures/contracts/odcs/graph_sample.yaml")

def test_in_memory_graph_builder(sample_graph_yaml_path):
    import networkx as nx
    from contracthub.utils.schema_utils import contract_to_model

    contract: OpenDataContractStandard = contract_to_model(sample_graph_yaml_path)

    # Store original state for validation
    original_schema_len = len(contract.schema_ or [])

    builder = InMemoryGraphBuilder(contract)
    graph = builder.build()

    # Verify graph type
    assert isinstance(graph, nx.MultiDiGraph)

    # Verify nodes: users, loyalty_members, products, orders should be present, user_products_junction should NOT
    nodes = list(graph.nodes)
    assert len(nodes) == 4
    assert "users" in nodes
    assert "loyalty_members" in nodes
    assert "products" in nodes
    assert "orders" in nodes
    assert "user_products_junction" not in nodes

    # Verify regular edges
    # orders -> users (PLACED_BY)
    edge_data_users = graph.get_edge_data("orders", "users")
    assert edge_data_users is not None
    assert edge_data_users[0]["label"] == "PLACED_BY"
    assert edge_data_users[0]["is_junction_edge"] is False

    # orders -> products (PRODUCTS fallback)
    edge_data_prods = graph.get_edge_data("orders", "products")
    assert edge_data_prods is not None
    assert edge_data_prods[0]["label"] == "PRODUCTS"
    assert edge_data_prods[0]["is_junction_edge"] is False

    # products -> orders (HAS_ORDER, because of is_source=true)
    edge_data_prods_rev = graph.get_edge_data("products", "orders")
    assert edge_data_prods_rev is not None
    assert edge_data_prods_rev[0]["label"] == "HAS_ORDER"
    assert edge_data_prods_rev[0]["is_junction_edge"] is False

    # Verify junction edge
    # users -> products (PURCHASED)
    edge_data_junc = graph.get_edge_data("users", "products")
    assert edge_data_junc is not None
    assert edge_data_junc[0]["label"] == "PURCHASED"
    assert edge_data_junc[0]["is_junction_edge"] is True
    assert edge_data_junc[0]["active"] == "boolean"
    assert edge_data_junc[0]["score"] == "float"

    # Verify ODCS model is unmodified
    assert len(contract.schema_ or []) == original_schema_len

def test_builder_raises_on_invalid_input():
    with pytest.raises(ValueError):
        InMemoryGraphBuilder({"version": "1.0.0"})
