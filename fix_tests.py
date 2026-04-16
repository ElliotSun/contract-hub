import re

with open('tests/test_contracthub_delta_importer.py', 'r') as f:
    content = f.read()

# Instead of table.relationships, we should check table.properties[0].relationships (which is user_id -> actually 'id' column, let's fix the mock)
content = content.replace('configuration = {"contracthub.fk.user_id": "users.id", "other_conf": "val"}', 'configuration = {"contracthub.fk.id": "users.id", "other_conf": "val"}')

old_assert = """    assert table.relationships is not None
    assert len(table.relationships) == 1
    rel = table.relationships[0]
    assert getattr(rel, "type", None) == "foreign_key"
    assert getattr(rel, "from_", None) == "user_id" or getattr(rel, "from", None) == "user_id"
    assert getattr(rel, "to", None) == "users.id\""""

new_assert = """    # Check property-level relationship mapping
    id_field = next(item for item in table.properties if item.name == "id")
    assert id_field.relationships is not None
    assert len(id_field.relationships) == 1
    rel = id_field.relationships[0]
    assert getattr(rel, "type", None) == "foreignKey"
    assert getattr(rel, "from_", getattr(rel, "from", None)) is None  # Property level uses implicit from
    assert getattr(rel, "to", None) == "users.id\""""

if "id_field.relationships is not None" not in content:
    content = content.replace(old_assert, new_assert)

with open('tests/test_contracthub_delta_importer.py', 'w') as f:
    f.write(content)


with open('tests/test_contracthub_merge_engine.py', 'r') as f:
    content = f.read()

merge_test = """
from open_data_contract_standard.model import Relationship

def test_merge_engine_hard_overwrites_relationships():
    existing = OpenDataContractStandard(
        apiVersion="v3.1.0",
        kind="DataContract",
        version="1.0.0",
        id="orders",
        name="orders",
        status="active",
        schema=[
            SchemaObject(
                name="orders",
                relationships=[Relationship(type="foreignKey", to="users.id")],
                properties=[],
            )
        ],
    )

    source_missing = OpenDataContractStandard(
        apiVersion="v3.1.0",
        kind="DataContract",
        version="1.0.0",
        id="orders",
        name="orders",
        status="active",
        schema=[
            SchemaObject(
                name="orders",
                relationships=None,
                properties=[],
            )
        ],
    )

    merged = ContractMergeEngine().merge(base_contract=source_missing, business_contract=existing).contract
    assert merged.schema_[0].relationships is None

    source_new = OpenDataContractStandard(
        apiVersion="v3.1.0",
        kind="DataContract",
        version="1.0.0",
        id="orders",
        name="orders",
        status="active",
        schema=[
            SchemaObject(
                name="orders",
                relationships=[Relationship(type="foreignKey", to="products.id")],
                properties=[],
            )
        ],
    )

    merged = ContractMergeEngine().merge(base_contract=source_new, business_contract=existing).contract
    assert len(merged.schema_[0].relationships) == 1
    assert getattr(merged.schema_[0].relationships[0], "to", None) == "products.id"

"""
if "test_merge_engine_hard_overwrites_relationships" not in content:
    content += merge_test
    with open('tests/test_contracthub_merge_engine.py', 'w') as f:
        f.write(content)


# Update tests/test_contracthub_lifecycle_policy_readable.py
with open('tests/test_contracthub_lifecycle_policy_readable.py', 'r') as f:
    content_policy = f.read()

policy_test = """
def test_policy_flags_removed_relationship_in_active_contract(relationship_base_contract_model, relationship_target_contract_model):
    evaluation = evaluate_merge_policy(relationship_base_contract_model, relationship_target_contract_model)
    assert evaluation.valid is False
    assert any("Relationship 'foreignKey:orders.user_id->users.id' removed" in item.message for item in evaluation.breaking_changes)
"""

if "test_policy_flags_removed_relationship_in_active_contract" not in content_policy:
    content_policy += policy_test
    with open('tests/test_contracthub_lifecycle_policy_readable.py', 'w') as f:
        f.write(content_policy)
