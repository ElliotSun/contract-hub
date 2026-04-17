import pytest
import logging
from contracthub.utils.schema_utils import contract_to_model

from contracthub.exporters.graph_exporter import GraphNode, GraphEdge
from contracthub.exporters.graph.validator import TopologyValidator, TopologyValidationError
from contracthub.exporters.graph.interceptor import SovereigntyInterceptor

def test_topology_validator_success():
    validator = TopologyValidator()
    nodes = [
        GraphNode(name="users", type="Table"),
        GraphNode(name="users.id", id="users.id", type="Column")
    ]
    edges = [
        GraphEdge(source="users", target="users.id", label="HAS_COLUMN")
    ]

    report = validator.validate(nodes, edges)
    assert report.is_valid is True
    assert len(report.missing_inbound_edges) == 0

def test_topology_validator_missing_inbound_edge():
    validator = TopologyValidator()
    nodes = [
        GraphNode(name="users", type="Table"),
        GraphNode(name="users.id", id="users.id", type="Column")
    ]
    edges = []  # No HAS_COLUMN edge

    with pytest.raises(TopologyValidationError) as exc:
        validator.validate(nodes, edges)

    assert "users.id" in str(exc.value)

def test_topology_validator_island_table(caplog):
    validator = TopologyValidator()
    nodes = [
        GraphNode(name="users", id="users", type="Table"),
        GraphNode(name="users.id", id="users.id", type="Column"),
        GraphNode(name="orders", id="orders", type="Table"),
    ]
    edges = [
        GraphEdge(source="users", target="users.id", label="HAS_COLUMN"),
    ]

    with caplog.at_level(logging.WARNING):
        report = validator.validate(nodes, edges)

    assert report.is_valid is True  # Islands are warnings, not errors
    assert "users" in report.island_tables
    assert "orders" in report.island_tables
    assert "absolute island" in caplog.text

def test_sovereignty_interceptor(tmp_path):
    yaml_content = """
kind: DataContract
apiVersion: v3.1.0
id: my-contract
status: active
name: test
version: 1.0.0
schema:
  - name: users
    properties:
      - name: id
        logicalType: string
        customProperties:
          - property: pii
            value: false
      - name: email
        logicalType: string
        customProperties:
          - property: pii
            value: true
"""
    yaml_file = tmp_path / "contract.yaml"
    yaml_file.write_text(yaml_content)

    contract = contract_to_model(str(yaml_file))

    nodes = [
        GraphNode(name="users.id", id="users.id", type="Column", properties={"example_value": "123"}),
        GraphNode(name="users.email", id="users.email", type="Column", properties={"example_value": "test@example.com"}),
    ]

    interceptor = SovereigntyInterceptor()
    interceptor.intercept(contract, nodes)

    # Check that ID was not redacted
    assert nodes[0].properties["example_value"] == "123"

    # Check that Email WAS redacted
    assert nodes[1].properties["example_value"] == "[REDACTED_PII]"

def test_sovereignty_interceptor_schema_format(tmp_path):
    yaml_content = """
kind: DataContract
apiVersion: v3.1.0
id: my-contract
status: active
name: test
version: 1.0.0
schema:
  - name: users
    properties:
      - name: id
        logicalType: string
        classification: public
      - name: email
        logicalType: string
        classification: pii
"""
    yaml_file = tmp_path / "contract.yaml"
    yaml_file.write_text(yaml_content)

    contract = contract_to_model(str(yaml_file))

    nodes = [
        GraphNode(name="users.id", id="users.id", type="Column", properties={"example_value": "123"}),
        GraphNode(name="users.email", id="users.email", type="Column", properties={"example_value": "test@example.com"}),
    ]

    interceptor = SovereigntyInterceptor()
    interceptor.intercept(contract, nodes)

    # Check that ID was not redacted
    assert nodes[0].properties["example_value"] == "123"

    # Check that Email WAS redacted
    assert nodes[1].properties["example_value"] == "[REDACTED_PII]"
