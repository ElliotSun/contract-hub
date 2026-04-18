# ContractHub Refactoring Plan

This document outlines the detailed execution steps to address the three primary architectural and code quality issues identified in the audit report.

## 1. Delegate Validation to `datacontract-cli`

**Problem:** `contracthub/core/validator.py` reinstates ODCS structural validation (checking for schema names, property types, quality rule formatting, etc.) which duplicates the native validation present in `datacontract-cli` (which handles ODCS Pydantic models).

**Solution:**
- **Remove custom structural validation:** Deprecate `ContractValidator` in `contracthub/core/validator.py` and replace it with direct calls to `datacontract.lint.Linter` or the `DataContract` model's native `validate()` methods.
- **Implement Custom Checks as Extensions:** If ContractHub requires specific checks (e.g. strict enforcement that `quality` rules match specific environments), these should be implemented as light wrappers *after* the `datacontract-cli` validation passes, not replacing the base ODCS validation.
- **Update test suite:** Refactor `tests/test_contracthub_validator_readable.py` to ensure it targets only ContractHub's custom domain constraints, removing redundant structural tests that belong to the upstream `datacontract-cli` repository.

## 2. Formalize Custom Domain Exceptions

**Problem:** Scattered across the codebase (e.g., in `contracthub/core/loader.py`, `contracthub/interfaces/streamlit/app.py`, `contracthub/quality/ge_exporter.py`), exceptions are caught using a generic `except Exception as exc:` or standard built-ins (`ValueError`, `TypeError`). This prevents strict error handling in automated GitOps pipelines.

**Solution:**
- **Create a Custom Exception Hierarchy:** Introduce a new module `contracthub/exceptions.py`.
  - `ContractHubError(Exception)`: The base exception.
  - `ValidationError(ContractHubError)`: Raised when a contract fails governance or structure validation.
  - `MergeConflictError(ContractHubError)`: Raised by the merge engine when business and technical metadata fatally conflict.
  - `LifecycleError(ContractHubError)`: Raised for invalid promotion or deployment actions.
  - `StorageError(ContractHubError)`: Wraps Azure ADLS / file system / Unity Catalog connection errors.
- **Refactor try/except blocks:** Traverse the codebase and replace generic catches with specific handling. If wrapping external exceptions (like `JSONDecodeError` or `urllib.error.URLError`), raise the appropriate custom error via `raise CustomError("...") from exc`.

## 3. Refine Pydantic Operations (Eliminate Dict Fallbacks)

**Problem:** Although `OpenDataContractStandard` is the core model, areas like `contracthub/utils/schema_utils.py` and UI services (e.g., `contracthub/interfaces/streamlit/editor/raw_yaml.py`) sometimes fall back to manipulating data as generic dictionaries or raw YAML text, undermining the single source of truth.

**Solution:**
- **Enforce ODCS Models Everywhere:** Refactor functions taking `ContractInput = OpenDataContractStandard | dict[str, Any]` to strictly accept and return `OpenDataContractStandard`.
- **Remove Dict-conversion utility methods:** Functions like `contract_to_dict` should be replaced by native Pydantic `.model_dump(by_alias=True, exclude_none=True)` calls invoked directly by the serializers that strictly need it at the system boundaries.
- **Streamlit Service Isolation:** The Streamlit app must only receive `OpenDataContractStandard` objects from the service layer, and must map UI states to standard model fields rather than dictionary keys.
