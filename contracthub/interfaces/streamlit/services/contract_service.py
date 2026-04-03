"""Contract data access and persistence services for the UI layer.

This module is the service boundary between the UI and ContractHub system logic.
It coordinates:

- canonical contract reads
- user-scoped draft reads and writes
- shared validation
- permission enforcement for editable workflows

Why several APIs accept ``user``:
- ``user`` represents the current actor context, not UI session state.
- It is required when the service needs to answer "can this actor edit this
  contract?" or when a draft must be isolated per actor.
- The current actor context is used for:
  1. permission checks
  2. draft storage isolation

Current edit rule:
- ``admin`` may edit any contract
- non-admin users may edit only contracts in the same tenant

Draft storage is user-scoped so multiple users do not overwrite each other:
- ``.contracthub/drafts/{user}/{contract_id}.yaml``

API intent:
- ``list_contracts(user)``:
  read main-contract catalog metadata and compute ``editable`` for the actor
- ``get_contract(contract_id)``:
  read the canonical main contract only
- ``get_draft(contract_id, user)``:
  read the actor's draft or initialize it from the main contract
- ``save_draft(contract, user)``:
  validate and persist the actor's draft without modifying the main contract

Representation boundary:
- dicts are still returned to the UI because Streamlit session_state and data
  editors work naturally with mapping payloads
- inside the service, contract semantics should prefer ODCS models unless a
  plain metadata record is sufficient
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from open_data_contract_standard.model import OpenDataContractStandard

from contracthub.core.draft_normalizer import normalize_draft_contract
from contracthub.core import validator as contract_validator
from contracthub.interfaces.streamlit.services import governance_service
from contracthub.utils.schema_utils import contract_to_dict, contract_to_model
from contracthub.utils.yaml_utils import (
    dump_yaml,
    dump_yaml_text,
    list_yaml_documents,
    load_yaml,
    load_yaml_metadata,
    parse_yaml_text,
    read_yaml_text,
)


DEFAULT_CONTRACTS_DIR = Path("contracts")
DEFAULT_DRAFTS_DIR = Path(".contracthub/drafts")
DEFAULT_SAMPLE_CONTRACT_PATH = Path("sample_odcs.yaml")
ContractInput = OpenDataContractStandard | dict[str, Any]


@dataclass(slots=True)
class ContractService:
    """Coordinate canonical contract reads and draft-based editing flows.

    Storage scope:
    - Main contracts may be loaded from local paths, ADLS2 roots, or Databricks
      Unity Catalog volume paths via the shared YAML utilities.
    - Drafts remain local path writes under the configured draft directory.

    Service boundary:
    - This service resolves storage roots, reads YAML via `yaml_utils`,
      validates through the shared core validator, and enforces edit
      permissions before persisting drafts.
    - It does not implement storage-specific auth logic directly.

    User context:
    - `user` is required only for operations that need editability decisions
      or user-scoped draft persistence.
    - Read-only canonical contract lookup does not require `user`.
    """

    contracts_dir: Path | str | None = None
    drafts_dir: Path | str | None = None
    sample_contract_path: Path | str | None = None

    def __post_init__(self) -> None:
        configured_contracts_dir = self.contracts_dir or os.getenv("CONTRACTHUB_CONTRACTS_DIR")
        configured_drafts_dir = self.drafts_dir or os.getenv("CONTRACTHUB_DRAFTS_DIR")
        configured_sample_path = self.sample_contract_path or os.getenv("CONTRACTHUB_SAMPLE_CONTRACT_PATH")
        self.contracts_dir = str(configured_contracts_dir) if configured_contracts_dir else str(DEFAULT_CONTRACTS_DIR)
        self.drafts_dir = Path(configured_drafts_dir) if configured_drafts_dir else DEFAULT_DRAFTS_DIR
        self.sample_contract_path = str(configured_sample_path) if configured_sample_path else str(DEFAULT_SAMPLE_CONTRACT_PATH)

    def load_sample_contract_yaml(self) -> str:
        """Return the configured sample ODCS YAML text."""
        return read_yaml_text(self.sample_contract_path)

    def parse_contract_yaml(self, source_yaml: str) -> dict[str, Any]:
        """Parse YAML text into a contract mapping for UI/editor flows."""
        return parse_yaml_text(source_yaml)

    def serialize_contract_yaml(self, contract: ContractInput) -> str:
        """Serialize a contract back to YAML text."""
        return dump_yaml_text(contract_to_dict(contract))

    def list_contracts(self, user: Any) -> list[dict[str, Any]]:
        """Load lightweight contract metadata for the catalog.

        The contract root is configured at deployment time via service
        construction or environment variable.
        Supported roots follow the shared YAML utility contract:
        local filesystem paths, ADLS2 roots, and Databricks UC volume paths.

        `user` is required here because the catalog response includes
        actor-specific `editable` flags.
        """
        contracts: list[dict[str, Any]] = []
        for path in self._contract_paths():
            metadata = load_yaml_metadata(path, keys=["id", "dataProduct", "name", "version", "status", "tenant"])
            contract_id = metadata.get("id") or _path_contract_id(path)
            contract_record = {
                "id": contract_id,
                "name": metadata.get("dataProduct") or metadata.get("name") or contract_id,
                "version": metadata.get("version", ""),
                "status": metadata.get("status", ""),
                "tenant": metadata.get("tenant", ""),
            }
            contract_record["editable"] = _can_edit(user, contract_record)
            contracts.append(contract_record)
        return sorted(contracts, key=lambda item: str(item["name"]).lower())

    def get_contract(self, contract_id: str) -> dict[str, Any]:
        """Load and return the canonical main contract mapping.

        This method does not require `user` because it only reads the main
        contract and does not evaluate draft ownership.
        """
        return contract_to_dict(self._get_contract_model(contract_id))

    def get_draft(self, contract_id: str, user: Any) -> dict[str, Any]:
        """Load an existing draft or initialize one from the main contract.

        `user` is required for:
        - edit permission checks
        - resolving the user-scoped draft path
        """
        try:
            main_contract = self._get_contract_model(contract_id)
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise FileNotFoundError(f"Contract '{contract_id}' does not exist") from exc
        _ensure_can_edit(user, main_contract, contract_id)

        draft_path = self._get_draft_path(contract_id, user)
        if draft_path.exists():
            return contract_to_dict(contract_to_model(load_yaml(draft_path)))
        return contract_to_dict(main_contract)

    def save_draft(self, contract: ContractInput, user: Any) -> dict[str, Any]:
        """Validate and persist a user draft without modifying the main contract.

        `user` is required for:
        - edit permission checks
        - resolving the user-scoped draft path
        """
        draft_contract = contract_to_model(contract)
        contract_id = _contract_id(draft_contract)
        main_contract = self._get_contract_model(contract_id)
        _ensure_can_edit(user, main_contract, contract_id)

        normalized_draft = normalize_draft_contract(draft_contract, main_contract)
        self._validate_contract(normalized_draft)
        dump_yaml(normalized_draft, self._get_draft_path(contract_id, user))
        return normalized_draft

    def analyze_draft(self, contract: ContractInput, user: Any) -> Any:
        """Analyze a working draft against the canonical main contract."""
        draft_contract = contract_to_model(contract)
        contract_id = _contract_id(draft_contract)
        main_contract = self._get_contract_model(contract_id)
        _ensure_can_edit(user, main_contract, contract_id)

        normalized_draft = normalize_draft_contract(draft_contract, main_contract)
        return governance_service.analyze_contracts(contract_to_model(normalized_draft), main_contract)

    def _get_contract_path(self, contract_id: str) -> str:
        """Return the configured YAML path for a contract identifier.

        Main contracts are addressed by `{contract_id}.yaml` under the current
        contract root, which may be local or remote.
        """
        normalized_id = str(contract_id or "").strip()
        if not normalized_id:
            raise ValueError("Contract id is required")
        return _join_contract_root(self.contracts_dir, f"{normalized_id}.yaml")

    def _get_draft_path(self, contract_id: str, user: Any) -> Path:
        """Return the user-scoped draft path for a contract identifier."""
        normalized_id = str(contract_id or "").strip()
        if not normalized_id:
            raise ValueError("Contract id is required")
        return Path(self.drafts_dir) / _user_storage_key(user) / f"{normalized_id}.yaml"

    def _contract_paths(self) -> list[str]:
        """Return YAML contract paths from the configured storage root."""
        return list_yaml_documents(self.contracts_dir)

    def _get_contract_model(self, contract_id: str) -> OpenDataContractStandard:
        """Load and return the canonical main contract as an ODCS model."""
        return contract_to_model(load_yaml(self._get_contract_path(contract_id)))

    def _validate_contract(self, contract: ContractInput) -> None:
        """Validate a contract using the shared core validator."""
        report = contract_validator.validate(contract)
        if report.valid:
            return

        issues = "; ".join(f"{issue.path}: {issue.message}" for issue in report.issues)
        raise ValueError(f"Contract validation failed: {issues}")


def list_contracts(user: Any) -> list[dict[str, Any]]:
    """Convenience wrapper for catalog metadata lookup."""
    return ContractService().list_contracts(user)


def get_contract(contract_id: str) -> dict[str, Any]:
    """Convenience wrapper for full contract lookup."""
    return ContractService().get_contract(contract_id)


def get_draft(contract_id: str, user: Any) -> dict[str, Any]:
    """Convenience wrapper for draft lookup."""
    return ContractService().get_draft(contract_id, user)


def save_draft(contract: ContractInput, user: Any) -> dict[str, Any]:
    """Convenience wrapper for draft persistence."""
    return ContractService().save_draft(contract, user)


def analyze_draft(contract: ContractInput, user: Any) -> Any:
    """Convenience wrapper for draft governance analysis."""
    return ContractService().analyze_draft(contract, user)


def load_sample_contract_yaml() -> str:
    """Convenience wrapper for the configured sample ODCS YAML text."""
    return ContractService().load_sample_contract_yaml()


def parse_contract_yaml(source_yaml: str) -> dict[str, Any]:
    """Convenience wrapper for editor/service-safe YAML parsing."""
    return ContractService().parse_contract_yaml(source_yaml)


def serialize_contract_yaml(contract: ContractInput) -> str:
    """Convenience wrapper for editor/service-safe YAML serialization."""
    return ContractService().serialize_contract_yaml(contract)


def _contract_id(contract: OpenDataContractStandard | dict[str, Any]) -> str:
    """Resolve the canonical contract identifier used for file naming."""
    if isinstance(contract, OpenDataContractStandard):
        contract_id = str(contract.id or "").strip()
    else:
        contract_id = str(contract.get("id", "") or "").strip()
    if not contract_id:
        raise ValueError("Contract must define an id")
    return contract_id


def _path_contract_id(path: str) -> str:
    """Resolve the fallback contract id from a storage path."""
    return Path(path).stem if "://" not in path else path.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _join_contract_root(root: str | Path, file_name: str) -> str:
    """Join a contract root with a YAML file name across local and remote storage."""
    root_str = str(root).rstrip("/")
    if "://" in root_str:
        return f"{root_str}/{file_name}"
    return str(Path(root_str) / file_name)


def _user_value(user: Any, field: str) -> str:
    """Resolve a field from a user object or mapping."""
    if isinstance(user, dict):
        return str(user.get(field, "") or "")
    return str(getattr(user, field, "") or "")


def _can_edit(user: Any, contract: OpenDataContractStandard | dict[str, Any]) -> bool:
    """Return True when the user can edit the target contract."""
    if isinstance(contract, OpenDataContractStandard):
        contract_tenant = str(contract.tenant or "")
    else:
        contract_tenant = str(contract.get("tenant", "") or "")
    if _user_value(user, "role") == "admin":
        return True

    user_tenant = _user_value(user, "tenant").strip()
    contract_tenant = contract_tenant.strip()
    if not contract_tenant or not user_tenant:
        return False

    return contract_tenant == user_tenant


def _ensure_can_edit(user: Any, contract: OpenDataContractStandard | dict[str, Any], contract_id: str) -> None:
    """Raise when the user is not permitted to edit the target contract."""
    if not _can_edit(user, contract):
        raise PermissionError(f"User is not allowed to edit contract '{contract_id}'")


def _user_storage_key(user: Any) -> str:
    """Resolve a stable user-scoped draft storage key."""
    for field in ("id", "username", "email", "name", "tenant"):
        value = _user_value(user, field).strip()
        if value:
            return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)
    raise ValueError("User must provide an id, username, email, name, or tenant for draft storage")
