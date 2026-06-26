import yaml

import re

import pytest

from contracthub.exporters.sql_exporter import export_contract_to_spark_sql


def test_export_contract_to_spark_sql_uses_physical_schema_names_from_sample():
    ddl = export_contract_to_spark_sql("examples/sample_odcs.yaml")

    assert "CREATE OR REPLACE TABLE tbl_1" in ddl
    assert "CREATE OR REPLACE TABLE receivers_master" in ddl
    assert re.search(r"\btxn_ref_dt\s+date\b", ddl, flags=re.IGNORECASE)
    assert re.search(
        r"\brcvr_id\s+varchar\(18\)\s+primary key\b", ddl, flags=re.IGNORECASE
    )
    assert 'COMMENT "Provides core payment metrics"' in ddl
    assert " None" not in ddl


def test_export_contract_to_spark_sql_with_unity_catalog_prefix():
    ddl = export_contract_to_spark_sql(
        "examples/sample_odcs.yaml",
        unity_catalog="main",
        unity_schema="silver",
    )

    assert "CREATE OR REPLACE TABLE main.silver.tbl_1" in ddl
    assert "CREATE OR REPLACE TABLE main.silver.receivers_master" in ddl


def test_export_contract_to_spark_sql_requires_both_unity_catalog_and_schema():
    with pytest.raises(ValueError, match="provided together"):
        export_contract_to_spark_sql("examples/sample_odcs.yaml", unity_catalog="main")


def test_export_contract_to_spark_sql_appends_not_null_constraint_from_quality_rule():
    ddl = export_contract_to_spark_sql("examples/sample_odcs.yaml")

    assert "ALTER TABLE tbl_1" in ddl
    assert "ALTER COLUMN rcvr_cntry_code SET NOT NULL" in ddl


def test_export_contract_to_spark_sql_supports_temporal_and_scalar_fixture(
    sample_temporal_types_contract_path,
):
    ddl = export_contract_to_spark_sql(sample_temporal_types_contract_path)

    assert "CREATE OR REPLACE TABLE temporal_events" in ddl
    assert re.search(r"\bbusiness_date\s+DATE\s+not null\b", ddl, flags=re.IGNORECASE)
    assert re.search(r"\bevent_ts\s+TIMESTAMP\s+not null\b", ddl, flags=re.IGNORECASE)
    assert re.search(r"\bevent_ts_ntz\s+TIMESTAMP_NTZ\b", ddl, flags=re.IGNORECASE)
    assert re.search(r"\bis_active\s+BOOLEAN\s+not null\b", ddl, flags=re.IGNORECASE)
    assert re.search(r"\braw_payload\s+BINARY\b", ddl, flags=re.IGNORECASE)


def test_export_contract_to_spark_sql_supports_nested_fixture(
    sample_nested_types_contract_path,
):
    ddl = export_contract_to_spark_sql(sample_nested_types_contract_path)

    assert "CREATE OR REPLACE TABLE nested_payloads" in ddl
    assert "payload STRUCT" in ddl
    assert "events ARRAY<STRUCT<event_id: STRING, event_ts: TIMESTAMP>>" in ddl
    assert "attributes MAP<STRING, ARRAY<STRUCT<k: STRING, v: STRING>>>" in ddl


def test_export_contract_to_spark_sql_with_external_location():
    with open("examples/sample_odcs.yaml", "r") as f:
        contract = yaml.safe_load(f)

    # Inject the custom property into the first schema object
    if "schema" in contract and len(contract["schema"]) > 0:
        contract["schema"][0]["customProperties"] = [
            {"property": "contracthub.table.location", "value": "s3://my-bucket/path/"}
        ]

    # 1. databricks mode
    ddl_databricks = export_contract_to_spark_sql(
        contract, sql_server_type="databricks"
    )
    assert "LOCATION 's3://my-bucket/path/'" in ddl_databricks
    assert "CREATE OR REPLACE TABLE tbl_1" in ddl_databricks

    # 2. spark mode
    ddl_spark = export_contract_to_spark_sql(contract, sql_server_type="spark")
    assert "LOCATION 's3://my-bucket/path/'" in ddl_spark
    assert "CREATE TABLE tbl_1" in ddl_spark

    # 3. postgres mode (should not inject location)
    ddl_postgres = export_contract_to_spark_sql(contract, sql_server_type="postgres")
    assert "LOCATION 's3://my-bucket/path/'" not in ddl_postgres
