## ContractHub

Enterprise Python library for Open Data Contract Standard (ODCS) workflows with GitOps automation.

## Architecture

```text
contracthub/
  core/
    draft_normalizer.py
    editor_contract.py
    loader.py
    validator.py
  exporters/
    sql_exporter.py
  lifecycle/
    merge_engine.py
    policy.py
    helpers.py
  quality/
    ge_exporter.py
    validation.py
    sql_exporter.py
  orchestrator/
    pipeline.py
  interfaces/
    cli.py
    streamlit/
      app.py
      editor/
      services/
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
contracthub release classify --base ./contracts/orders.main.yaml --candidate ./contracts/orders.feature.yaml
contracthub release prepare --base ./contracts/orders.main.yaml --candidate ./contracts/orders.release.yaml \
  --release-tag orders/v1.2.0 --output ./artifacts/orders.promoted.yaml
contracthub release create-pr --base ./contracts/orders.main.yaml --candidate ./contracts/orders.release.yaml \
  --release-tag orders/v1.2.0 --repo-path . --contract-path contracts/orders.yaml \
  --source-branch release/orders-v1.2.0 --target-branch release \
  --organization org --project proj --repository-id repo --pat-token $ADO_PAT --push
contracthub release classify-repo --base-root ./contracts-main --candidate-root ./contracts-feature
contracthub release build-manifest --base-root ./contracts-main --candidate-root ./contracts-feature \
  --output ./artifacts/release_manifest.json
contracthub release create-prs --manifest ./artifacts/release_manifest.json --repo-path . \
  --organization org --project proj --repository-id repo --pat-token $ADO_PAT --push
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

## Suggested CI Flow

### Feature -> Main

Use per-contract bump classification without changing contract versions:

```bash
contracthub release classify \
  --base ./contracts/orders.main.yaml \
  --candidate ./contracts/orders.feature.yaml
```

For multi-contract repos:

```bash
contracthub release classify-repo \
  --base-root ./contracts-main \
  --candidate-root ./contracts-feature
```

### Main -> Release

Build an editable per-contract manifest, review or adjust tags, then create
release PRs:

```bash
contracthub release build-manifest \
  --base-root ./contracts-main \
  --candidate-root ./contracts-release \
  --output ./artifacts/release_manifest.json

contracthub release create-prs \
  --manifest ./artifacts/release_manifest.json \
  --repo-path . \
  --organization org \
  --project proj \
  --repository-id repo \
  --pat-token $ADO_PAT \
  --push
```

The generated manifest is still per contract. Review it before creating PRs,
especially for:

- added contracts
- removed contracts
- contracts whose suggested release tag needs adjustment

## Notes

- Importers are pure Python and Spark-free.
- ContractHub registers custom importers (`delta`, `sql-folder`) into datacontract-cli's importer factory.
- Merge and lifecycle policy logic are isolated in `contracthub.lifecycle`.
- Root contract `id` is immutable after the governed contract exists.
- Root contract `version` is release-managed and is not updated by normal importer/merge runs.
- Technical source versions, including Delta table versions, are stored as technical metadata and do not overwrite contract `version`.
- Lifecycle policy explicitly flags root `id` and `version` changes, and the automation pipeline blocks on those violations.
- Required version bump is computed per contract, not per repo.
- `feature -> main` should classify the required bump for each changed contract.
- `main/release` is the path that applies an explicit release tag and updates contract `version`.
- Suggested next versions are always computed from the last released contract version plus the highest required bump since that release.
- Unreleased changes are not bump-chained. For example, `1.2.0 -> major change -> additive change` still suggests `2.0.0`, not `2.1.0`.
- If `required_bump` is `none`, the suggested next version stays at the current released version and the contract is skipped by default in batch release manifest generation.
- `release classify-repo` is a repo-level batching helper only; it does not make the repo a versioning unit.
- `release build-manifest` creates an editable per-contract JSON array for batch release PR automation.
- `release create-prs` expects an explicit per-contract manifest because each contract may have its own release tag/version.
- Draft normalization and editor-safe contract mutation helpers live in `contracthub.core`.
- Great Expectations suite generation uses datacontract-cli exporter APIs.
- Databricks/Spark SQL deployment DDL generation lives in `contracthub.exporters.sql_exporter`.
- Databricks-only quality constraint mapping is appended only when `sql_server_type="databricks"`.
- Great Expectations export follows a two-step validation boundary:
  - contract-level quality rule validation in `contracthub.core.validator`
  - GE-specific expectation preflight in `contracthub.quality.ge_exporter`
- Streamlit is a presentation layer and should call service-layer helpers under `contracthub/interfaces/streamlit/services/`.
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
