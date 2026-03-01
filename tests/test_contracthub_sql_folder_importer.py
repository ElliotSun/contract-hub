from contracthub.importers.sql_importer import SQLFolderImporter


def test_sql_folder_importer_parses_real_sparksql_external_table_ddl(tmp_path):
    product_dir = tmp_path / "adls2_product"
    product_dir.mkdir()

    (product_dir / "orders_external.sql").write_text(
        """
        CREATE EXTERNAL TABLE orders_external (
          id BIGINT NOT NULL COMMENT 'Order id',
          amount DECIMAL(18,2),
          is_active BOOLEAN,
          event_date DATE,
          event_ts TIMESTAMP,
          payload STRUCT<
            source: STRING,
            metrics: STRUCT<count: INT, score: DOUBLE>,
            labels: MAP<STRING, STRING>
          >,
          events ARRAY<STRUCT<event_id: STRING, event_ts: TIMESTAMP>>,
          attributes MAP<STRING, ARRAY<STRUCT<k: STRING, v: STRING>>>,
          raw BINARY
        )
        USING DELTA
        LOCATION 'abfss://silver@mydatalake.dfs.core.windows.net/orders_external';
        """,
        encoding="utf-8",
    )

    importer = SQLFolderImporter(str(product_dir))
    contract = importer.import_contract()

    assert contract["name"] == "adls2_product"
    assert len(contract["schema"]) == 1

    table = contract["schema"][0]
    assert table["id"] == "orders_external"
    assert table["name"] == "orders_external"
    assert table["physicalType"] == "external-table"
    table_props = {item["property"]: item["value"] for item in table.get("customProperties", [])}
    assert table_props["contracthub.table.external"] == "true"
    assert table_props["contracthub.table.format"] == "DELTA"
    assert table_props["contracthub.table.location"].startswith("abfss://silver@")

    id_field = next(item for item in table["properties"] if item["name"] == "id")
    assert id_field["id"] == "id"
    assert id_field["physicalType"].lower().startswith("bigint")
    assert id_field["required"] is True
    assert id_field["description"] == "Order id"

    amount_field = next(item for item in table["properties"] if item["name"] == "amount")
    assert amount_field["logicalTypeOptions"] == {"precision": 18, "scale": 2}

    payload_field = next(item for item in table["properties"] if item["name"] == "payload")
    assert payload_field["logicalType"] == "object"
    nested_names = {item["name"] for item in payload_field.get("properties", [])}
    assert nested_names == {"source", "metrics", "labels"}
    events_field = next(item for item in table["properties"] if item["name"] == "events")
    assert events_field["logicalType"] == "array"
    assert events_field["items"]["logicalType"] == "object"
    attributes_field = next(item for item in table["properties"] if item["name"] == "attributes")
    assert attributes_field["logicalType"] == "object"
    assert attributes_field["items"]["logicalType"] == "array"


def test_sql_folder_importer_multiple_files_generate_one_contract_with_all_tables(tmp_path):
    product_dir = tmp_path / "finance_product"
    product_dir.mkdir()

    (product_dir / "accounts.sql").write_text(
        """
        CREATE TABLE accounts (
          account_id STRING NOT NULL,
          opened_at TIMESTAMP
        );
        """,
        encoding="utf-8",
    )
    (product_dir / "transactions.sql").write_text(
        """
        CREATE TABLE transactions (
          txn_id STRING NOT NULL,
          account_id STRING NOT NULL,
          amount DECIMAL(10,2)
        );
        """,
        encoding="utf-8",
    )
    (product_dir / "balances.sql").write_text(
        """
        CREATE TABLE balances (
          account_id STRING NOT NULL,
          balance DECIMAL(18,2)
        );
        """,
        encoding="utf-8",
    )

    importer = SQLFolderImporter(str(product_dir))
    contract = importer.import_contract()

    # One import call should produce one ODCS contract containing all table schemas.
    assert contract["name"] == "finance_product"
    assert contract["id"] == "finance_product"
    assert len(contract["schema"]) == 3

    table_names = {item["name"] for item in contract["schema"]}
    assert table_names == {"accounts", "transactions", "balances"}


def test_sql_folder_importer_extracts_primary_key_unique_and_partition_metadata(tmp_path):
    product_dir = tmp_path / "risk_product"
    product_dir.mkdir()

    (product_dir / "events.sql").write_text(
        """
        CREATE TABLE events (
          event_id STRING NOT NULL,
          event_date DATE,
          source STRING,
          CONSTRAINT pk_events PRIMARY KEY (event_id),
          CONSTRAINT uq_events UNIQUE (source)
        )
        USING DELTA
        COMMENT 'Event fact table'
        PARTITIONED BY (event_date);
        """,
        encoding="utf-8",
    )

    contract = SQLFolderImporter(str(product_dir)).import_contract()
    table = contract["schema"][0]

    assert table["description"] == "Event fact table"
    fields = {item["name"]: item for item in table["properties"]}
    assert fields["event_id"]["primaryKey"] is True
    assert fields["event_id"]["primaryKeyPosition"] == 1
    assert fields["source"]["unique"] is True
    assert fields["event_date"]["partitioned"] is True
    assert fields["event_date"]["partitionKeyPosition"] == 1
