import json

import contracthub.importers.delta_importer as delta_importer


def test_delta_importer_builds_odcs_contract(monkeypatch):
    class FakeSchema:
        @staticmethod
        def json():
            return json.dumps(
                {
                    "type": "struct",
                    "fields": [
                        {"name": "id", "type": "long", "nullable": False, "metadata": {}},
                        {"name": "amount", "type": "decimal(10,2)", "nullable": True, "metadata": {}},
                        {
                            "name": "payload",
                            "type": {
                                "type": "struct",
                                "fields": [
                                    {"name": "source", "type": "string", "nullable": True, "metadata": {}}
                                ],
                            },
                            "nullable": True,
                            "metadata": {},
                        },
                        {"name": "events", "type": "array<struct<event_id:string,event_ts:timestamp>>", "nullable": True, "metadata": {}},
                        {"name": "attributes", "type": "map<string,string>", "nullable": True, "metadata": {}},
                    ],
                }
            )

    class FakeMetadata:
        description = "Finance transactions"
        configuration = {}
        partition_columns = ["id"]

    class FakeDeltaTable:
        def __init__(self, _uri, *, storage_options=None, **_kwargs):
            self._uri = _uri
            self._storage_options = storage_options

        def schema(self):
            return FakeSchema()

        def metadata(self):
            return FakeMetadata()

        @staticmethod
        def version():
            return 12

    monkeypatch.setattr(delta_importer, "DeltaTable", FakeDeltaTable)

    importer = delta_importer.DeltaTableImporter("delta")
    contract = importer.import_source("s3://lake/silver/finance_transactions", {})

    assert contract.name == "finance_transactions"
    assert contract.version == "12"
    assert contract.description is not None
    assert contract.description.usage == "Finance transactions"
    assert contract.schema_ is not None
    table = contract.schema_[0]
    assert table.id == "finance_transactions"
    assert table.properties is not None
    assert table.properties[0].name == "id"
    assert table.properties[0].required is True
    assert table.properties[0].partitioned is True
    assert table.properties[0].partitionKeyPosition == 1
    assert table.properties[1].logicalType == "number"
    assert table.properties[1].logicalTypeOptions == {"precision": 10, "scale": 2}
    payload_field = next(item for item in table.properties if item.name == "payload")
    assert payload_field.logicalType == "object"
    assert payload_field.properties is not None
    assert payload_field.properties[0].name == "source"
    events_field = next(item for item in table.properties if item.name == "events")
    assert events_field.logicalType == "array"
    assert events_field.items is not None
    assert events_field.items.logicalType == "object"
    attributes_field = next(item for item in table.properties if item.name == "attributes")
    assert attributes_field.logicalType == "object"
    assert attributes_field.logicalTypeOptions is not None
    assert str(attributes_field.logicalTypeOptions["keyType"]).lower().startswith("string")

    table_cp = {item.property: item.value for item in table.customProperties or []}
    assert table_cp["contracthub.delta.uri"] == "s3://lake/silver/finance_transactions"
    assert table_cp["contracthub.delta.version"] == "12"
    assert table_cp["contracthub.delta.partitionColumns"] == ["id"]


def test_delta_importer_supports_multiple_tables(monkeypatch):
    class FakeSchema:
        @staticmethod
        def json():
            return json.dumps(
                {
                    "type": "struct",
                    "fields": [
                        {"name": "id", "type": "long", "nullable": False, "metadata": {}},
                    ],
                }
            )

    class FakeMetadata:
        description = None
        configuration = {}
        partition_columns = []

    class FakeDeltaTable:
        def __init__(self, _uri, *, storage_options=None, **_kwargs):
            self._uri = _uri
            self._storage_options = storage_options

        def schema(self):
            return FakeSchema()

        def metadata(self):
            return FakeMetadata()

        @staticmethod
        def version():
            return 3

    monkeypatch.setattr(delta_importer, "DeltaTable", FakeDeltaTable)

    importer = delta_importer.DeltaTableImporter("delta")
    contract = importer.import_source(
        "s3://lake/silver/orders",
        {
            "table_uris": ["s3://lake/silver/payments"],
            "dataset_name": "finance_product",
        },
    )

    assert contract.name == "finance_product"
    assert contract.schema_ is not None
    assert len(contract.schema_) == 2
    table_names = {item.name for item in contract.schema_}
    assert table_names == {"orders", "payments"}
