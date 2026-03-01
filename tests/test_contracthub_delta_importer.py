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
        def __init__(self, _uri):
            self._uri = _uri

        def schema(self):
            return FakeSchema()

        def metadata(self):
            return FakeMetadata()

        @staticmethod
        def version():
            return 12

    monkeypatch.setattr(delta_importer, "DeltaTable", FakeDeltaTable)

    importer = delta_importer.DeltaTableImporter("s3://lake/silver/finance_transactions")
    contract = importer.import_contract()

    assert contract["name"] == "finance_transactions"
    assert contract["version"] == "12"
    assert contract["description"]["usage"] == "Finance transactions"
    assert contract["schema"][0]["id"] == "finance_transactions"
    assert contract["schema"][0]["properties"][0]["name"] == "id"
    assert contract["schema"][0]["properties"][0]["required"] is True
    assert contract["schema"][0]["properties"][0]["partitioned"] is True
    assert contract["schema"][0]["properties"][0]["partitionKeyPosition"] == 1
    assert contract["schema"][0]["properties"][1]["logicalType"] == "number"
    assert contract["schema"][0]["properties"][1]["logicalTypeOptions"] == {"precision": 10, "scale": 2}
    payload_field = next(item for item in contract["schema"][0]["properties"] if item["name"] == "payload")
    assert payload_field["logicalType"] == "object"
    assert payload_field["properties"][0]["name"] == "source"
    events_field = next(item for item in contract["schema"][0]["properties"] if item["name"] == "events")
    assert events_field["logicalType"] == "array"
    assert events_field["items"]["logicalType"] == "object"
    attributes_field = next(item for item in contract["schema"][0]["properties"] if item["name"] == "attributes")
    assert attributes_field["logicalType"] == "object"
    assert attributes_field["logicalTypeOptions"]["keyType"].lower().startswith("string")
