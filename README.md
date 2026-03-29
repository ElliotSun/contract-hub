## ContractHub

Enterprise Python library for Open Data Contract Standard (ODCS) workflows with GitOps automation.

## Architecture

```text
contracthub/
  core/
    loader.py
    validator.py
  exporters/
    sql_exporter.py
  importers/
    delta_importer.py
    sql_importer.py
  lifecycle/
    merge_engine.py
    policy.py
    helpers.py
  quality/
    ge_exporter.py
    validation.py
  orchestrator/
    pipeline.py
  interfaces/
    cli.py
    ui_streamlit.py
  devops/
    pr_creator.py
    ci_cd.py
    audit.py
```

## Install

```bash
uv sync --extra dev
```

Azure-backed contract storage support:

```bash
uv sync --extra dev --extra azure
```

## CLI

```bash
contracthub import --type sql-folder --source ./sql/orders --output ./contracts/orders.yaml
contracthub import --type sql --source ./ddl/orders.sql --output ./contracts/orders.yaml
contracthub import --type delta --source abfss://container@acct.dfs.core.windows.net/orders \
  --tables abfss://container@acct.dfs.core.windows.net/payments \
  --output ./contracts/finance.yaml
contracthub import --type unity --source main.silver.orders --workspace-url https://adb.example --token $DATABRICKS_TOKEN \
  --output ./contracts/orders.yaml
contracthub merge --base ./generated.yaml --business ./contracts/orders.yaml --output ./contracts/orders.merged.yaml
contracthub export-ge --contract ./contracts/orders.yaml --output ./artifacts/orders_suite.json
contracthub create-pr --organization org --project proj --repository-id repo --pat-token $ADO_PAT \
  --repo-path . --source-branch contracthub/update-orders --target-branch main \
  --commit-message "Update orders contract" --title "Update orders contract" --description "Automated update"
```

## SDK Usage

```python
from datacontract.data_contract import DataContract
from contracthub.lifecycle import ContractMergeEngine
from contracthub.quality import GreatExpectationsExporter, run_contract_tests

contract = DataContract.import_from_source(format="sql-folder", source="./sql/orders")
merged = ContractMergeEngine().merge(contract, "./contracts/orders.yaml")
GreatExpectationsExporter().export_to_path(merged.contract, "./artifacts/orders_suite.json")
```

## Notes

- Importers are pure Python and Spark-free.
- ContractHub registers custom importers (`delta`, `sql-folder`) into datacontract-cli's importer factory.
- Merge and lifecycle policy logic are isolated in `contracthub.lifecycle`.
- Great Expectations suite generation uses datacontract-cli exporter APIs.
- Databricks/Spark SQL deployment DDL generation lives in `contracthub.exporters.sql_exporter`.
- Databricks-only quality constraint mapping is appended only when `sql_server_type="databricks"`.
- Great Expectations export follows a two-step validation boundary:
  - contract-level quality rule validation in `contracthub.core.validator`
  - GE-specific expectation preflight in `contracthub.quality.ge_exporter`
- Legacy packages `contracthub_importers` and `contracthub_enforcement` have been removed.
- Contract catalog storage currently supports:
  - local filesystem paths
  - ADLS2 paths (`abfs://`, `abfss://`, or `https://<account>.dfs.core.windows.net/...`)
  - Databricks Unity Catalog volume paths (`/Volumes/...`, `dbfs:/Volumes/...`)
- ADLS2 access is SDK-based and supports only:
  - `CONTRACTHUB_ADLS_BEARER_TOKEN`
  - `azure.identity.DefaultAzureCredential`
- SAS URL authentication is not supported.
- Unity Catalog external volumes are accessed as mounted paths and do not use separate ContractHub-managed cloud auth.
