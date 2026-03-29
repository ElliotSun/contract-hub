import re

import pytest

from contracthub.exporters.sql_exporter import export_contract_to_spark_sql


def test_export_contract_to_spark_sql_uses_physical_schema_names_from_sample():
    ddl = export_contract_to_spark_sql("sample_odcs.yaml")

    assert "CREATE OR REPLACE TABLE tbl_1" in ddl
    assert "CREATE OR REPLACE TABLE receivers_master" in ddl
    assert re.search(r"\btxn_ref_dt\s+date\b", ddl, flags=re.IGNORECASE)
    assert re.search(r"\brcvr_id\s+varchar\(18\)\s+primary key\b", ddl, flags=re.IGNORECASE)
    assert 'COMMENT "Provides core payment metrics"' in ddl
    assert " None" not in ddl


def test_export_contract_to_spark_sql_with_unity_catalog_prefix():
    ddl = export_contract_to_spark_sql(
        "sample_odcs.yaml",
        unity_catalog="main",
        unity_schema="silver",
    )

    assert "CREATE OR REPLACE TABLE main.silver.tbl_1" in ddl
    assert "CREATE OR REPLACE TABLE main.silver.receivers_master" in ddl


def test_export_contract_to_spark_sql_requires_both_unity_catalog_and_schema():
    with pytest.raises(ValueError, match="provided together"):
        export_contract_to_spark_sql("sample_odcs.yaml", unity_catalog="main")


def test_export_contract_to_spark_sql_appends_not_null_constraint_from_quality_rule():
    ddl = export_contract_to_spark_sql("sample_odcs.yaml")

    assert "ALTER TABLE tbl_1" in ddl
    assert "ALTER COLUMN rcvr_cntry_code SET NOT NULL" in ddl
