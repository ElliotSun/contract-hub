import contracthub.lifecycle.merge_engine as merge_engine
from contracthub.lifecycle.merge_engine import merge_contract


def test_merge_engine_preserves_business_metadata_and_flags_removed_columns():
    existing = {
        "id": "orders",
        "name": "orders",
        "schema": [
            {
                "name": "orders",
                "description": "Business curated order table",
                "quality": [{"type": "row_count", "mustBeGreaterThan": 0}],
                "properties": [
                    {
                        "name": "id",
                        "physicalType": "BIGINT",
                        "logicalType": "integer",
                        "description": "Business order id",
                        "quality": [{"type": "uniqueness"}],
                    },
                    {
                        "name": "legacy_col",
                        "physicalType": "STRING",
                        "logicalType": "string",
                    },
                ],
            }
        ],
    }

    imported = {
        "id": "orders",
        "name": "orders",
        "schema": [
            {
                "name": "orders",
                "properties": [
                    {"name": "id", "physicalType": "INT", "logicalType": "integer"},
                    {"name": "amount", "physicalType": "DECIMAL(10,2)", "logicalType": "number"},
                ],
            }
        ],
    }

    merged = merge_contract(existing=existing, imported=imported)
    merged_schema = merged["schema"][0]
    assert merged_schema["description"] == "Business curated order table"
    assert merged_schema["quality"] == [{"type": "row_count", "mustBeGreaterThan": 0}]

    merged_id = next(col for col in merged_schema["properties"] if col["name"] == "id")
    assert merged_id["physicalType"] == "INT"
    assert merged_id["description"] == "Business order id"
    assert merged_id["quality"] == [{"type": "uniqueness"}]

    merged_amount = next(col for col in merged_schema["properties"] if col["name"] == "amount")
    assert merged_amount["physicalType"] == "DECIMAL(10,2)"

    removed_col = next(col for col in merged_schema["properties"] if col["name"] == "legacy_col")
    assert removed_col["deprecated"] is True
    assert {"property": "contracthub.removed", "value": "true"} in removed_col["customProperties"]


def test_merge_engine_handles_schema_alias_and_existing_removed_flag():
    existing = {
        "schema_": [
            {
                "name": "tbl",
                "properties": [
                    {
                        "name": "obsolete",
                        "customProperties": [{"property": "contracthub.removed", "value": "true"}],
                    }
                ],
            }
        ]
    }
    imported = {"schema_": [{"name": "tbl", "properties": []}]}
    merged = merge_contract(existing, imported)
    removed = merged["schema_"][0]["properties"][0]
    assert removed["deprecated"] is True
    assert removed["customProperties"].count({"property": "contracthub.removed", "value": "true"}) == 1


def test_merge_engine_internal_helpers_cover_edge_paths():
    assert merge_engine._has_removed_flag([{"property": "contracthub.removed", "value": "TRUE"}]) is True  # noqa: SLF001


def test_merge_engine_preserves_top_level_description_and_handles_added_removed_schema_objects():
    existing = {
        "description": {"usage": "business desc"},
        "schema": [{"name": "legacy_table", "properties": []}],
    }
    imported = {"schema": [{"name": "new_table", "properties": []}]}
    merged = merge_contract(existing=existing, imported=imported)
    assert merged["description"] == {"usage": "business desc"}
    names = [s["name"] for s in merged["schema"]]
    assert "new_table" in names
    legacy_obj = next(s for s in merged["schema"] if s["name"] == "legacy_table")
    assert legacy_obj["deprecated"] is True
