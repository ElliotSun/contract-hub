from __future__ import annotations

from pathlib import Path

import yaml

import contracthub.interfaces.streamlit.services.contract_service as contract_service_module
from contracthub.interfaces.streamlit.services.contract_service import ContractService
from contracthub.interfaces.streamlit.services import governance_service
from contracthub.lifecycle.merge_engine import MergeAnalysis, MergeResult
from contracthub.utils.yaml_utils import dump_yaml, load_yaml


def test_contract_service_lists_contract_metadata_and_editability(sample_odcs_dict, tmp_path):
    contracts_dir = tmp_path / "contracts"
    first_contract = dict(sample_odcs_dict)
    first_contract["id"] = "seller-payments"
    first_contract["dataProduct"] = "seller payments"
    first_contract["tenant"] = "tenant-a"
    dump_yaml(first_contract, contracts_dir / "seller-payments.yaml")

    second_contract = dict(sample_odcs_dict)
    second_contract["id"] = "buyer-orders"
    second_contract["dataProduct"] = "buyer orders"
    second_contract["tenant"] = "tenant-b"
    second_contract["version"] = "2.0.0"
    dump_yaml(second_contract, contracts_dir / "buyer-orders.yaml")

    service = ContractService(contracts_dir=contracts_dir, drafts_dir=tmp_path / ".contracthub" / "drafts")

    contracts = service.list_contracts(user={"tenant": "tenant-a", "role": "editor"})

    assert [contract["id"] for contract in contracts] == ["buyer-orders", "seller-payments"]
    assert contracts[0]["editable"] is False
    assert contracts[1]["editable"] is True


def test_contract_service_list_contracts_uses_environment_configured_contract_root(sample_odcs_dict, tmp_path, monkeypatch):
    contracts_dir = tmp_path / "configured-contracts"

    configured_contract = dict(sample_odcs_dict)
    configured_contract["id"] = "configured-contract"
    configured_contract["dataProduct"] = "configured contract"
    configured_contract["tenant"] = "tenant-a"
    dump_yaml(configured_contract, contracts_dir / "configured-contract.yaml")

    monkeypatch.setenv("CONTRACTHUB_CONTRACTS_DIR", str(contracts_dir))

    contracts = contract_service_module.list_contracts(user={"tenant": "tenant-a", "role": "editor"})

    assert [contract["id"] for contract in contracts] == ["configured-contract"]


def test_contract_service_list_contracts_supports_adls2_contract_root(monkeypatch):
    monkeypatch.setattr(
        contract_service_module,
        "list_yaml_documents",
        lambda root: [
            "abfss://contracts@acct.dfs.core.windows.net/contracts/orders.yaml",
        ],
    )
    monkeypatch.setattr(
        contract_service_module,
        "load_yaml_metadata",
        lambda path, keys: {
            "id": "orders",
            "dataProduct": "seller payments",
            "version": "1.0.0",
            "status": "active",
            "tenant": "tenant-a",
        },
    )

    service = ContractService(contracts_dir="abfss://contracts@acct.dfs.core.windows.net/contracts")
    contracts = service.list_contracts(user={"tenant": "tenant-a", "role": "editor"})

    assert contracts == [
        {
            "id": "orders",
            "name": "seller payments",
            "version": "1.0.0",
            "status": "active",
            "tenant": "tenant-a",
            "editable": True,
        }
    ]


def test_contract_service_get_draft_returns_main_contract_when_no_draft_exists(sample_odcs_dict, tmp_path):
    contracts_dir = tmp_path / "contracts"
    main_contract = dict(sample_odcs_dict)
    main_contract["id"] = "seller-payments"
    main_contract["tenant"] = "tenant-a"
    dump_yaml(main_contract, contracts_dir / "seller-payments.yaml")

    service = ContractService(contracts_dir=contracts_dir, drafts_dir=tmp_path / ".contracthub" / "drafts")

    draft = service.get_draft("seller-payments", user={"tenant": "tenant-a", "role": "editor", "id": "alice"})

    assert draft["id"] == "seller-payments"
    assert draft["tenant"] == "tenant-a"
    assert not (tmp_path / ".contracthub" / "drafts" / "alice" / "seller-payments.yaml").exists()


def test_contract_service_get_draft_prefers_saved_user_draft(sample_odcs_dict, tmp_path):
    contracts_dir = tmp_path / "contracts"
    drafts_dir = tmp_path / ".contracthub" / "drafts"
    main_contract = dict(sample_odcs_dict)
    main_contract["id"] = "seller-payments"
    main_contract["tenant"] = "tenant-a"
    dump_yaml(main_contract, contracts_dir / "seller-payments.yaml")

    saved_draft = dict(main_contract)
    saved_draft.setdefault("description", {})["purpose"] = "Edited draft purpose"
    dump_yaml(saved_draft, drafts_dir / "alice" / "seller-payments.yaml")

    service = ContractService(contracts_dir=contracts_dir, drafts_dir=drafts_dir)

    draft = service.get_draft("seller-payments", user={"tenant": "tenant-a", "role": "editor", "id": "alice"})

    assert draft["description"]["purpose"] == "Edited draft purpose"


def test_contract_service_save_draft_persists_draft_without_overwriting_main(sample_odcs_dict, tmp_path):
    contracts_dir = tmp_path / "contracts"
    drafts_dir = tmp_path / ".contracthub" / "drafts"
    main_contract = dict(sample_odcs_dict)
    main_contract["id"] = "seller-payments"
    main_contract["tenant"] = "tenant-a"
    main_contract.setdefault("description", {})["purpose"] = "Main purpose"
    dump_yaml(main_contract, contracts_dir / "seller-payments.yaml")

    draft = dict(main_contract)
    draft["description"]["purpose"] = "Draft purpose"

    service = ContractService(contracts_dir=contracts_dir, drafts_dir=drafts_dir)
    saved = service.save_draft(draft, user={"tenant": "tenant-a", "role": "editor", "id": "alice"})

    persisted_main = load_yaml(contracts_dir / "seller-payments.yaml")
    persisted_draft = load_yaml(drafts_dir / "alice" / "seller-payments.yaml")

    assert saved["description"]["purpose"] == "Draft purpose"
    assert persisted_main["description"]["purpose"] == "Main purpose"
    assert persisted_draft["description"]["purpose"] == "Draft purpose"


def test_contract_service_save_draft_rejects_unauthorized_user(sample_odcs_dict, tmp_path):
    contracts_dir = tmp_path / "contracts"
    main_contract = dict(sample_odcs_dict)
    main_contract["id"] = "seller-payments"
    main_contract["tenant"] = "tenant-a"
    dump_yaml(main_contract, contracts_dir / "seller-payments.yaml")

    service = ContractService(contracts_dir=contracts_dir, drafts_dir=tmp_path / ".contracthub" / "drafts")

    try:
        service.save_draft(main_contract, user={"tenant": "tenant-b", "role": "editor", "id": "bob"})
    except PermissionError as exc:
        assert "seller-payments" in str(exc)
    else:
        raise AssertionError("Expected save_draft to reject an unauthorized user")


def test_governance_service_analyze_delegates_to_merge_engine(sample_odcs_dict, sample_odcs_model, monkeypatch):
    source_yaml = yaml.safe_dump(sample_odcs_dict, sort_keys=False)
    target_yaml = yaml.safe_dump(sample_odcs_dict, sort_keys=False)
    expected = MergeAnalysis()
    captured: dict[str, object] = {}

    class FakeEngine:
        def _analyze_merge(self, *, target_model, source_model):
            captured["target"] = target_model
            captured["source"] = source_model
            return expected

    monkeypatch.setattr(governance_service, "_MERGE_ENGINE", FakeEngine())

    result = governance_service.analyze(source_yaml, target_yaml)

    assert result is expected
    assert captured["target"] == sample_odcs_model
    assert captured["source"] == sample_odcs_model


def test_governance_service_apply_delegates_to_merge_engine(sample_odcs_dict, sample_odcs_model, monkeypatch):
    source_yaml = yaml.safe_dump(sample_odcs_dict, sort_keys=False)
    target_yaml = yaml.safe_dump(sample_odcs_dict, sort_keys=False)
    expected = MergeResult(contract=sample_odcs_model, conflicts=[])
    captured: dict[str, object] = {}

    class FakeEngine:
        def merge(self, *, base_contract, business_contract):
            captured["base"] = base_contract
            captured["business"] = business_contract
            return expected

    monkeypatch.setattr(governance_service, "_MERGE_ENGINE", FakeEngine())

    result = governance_service.apply(source_yaml, target_yaml)

    assert result is expected
    assert captured["base"] == sample_odcs_model
    assert captured["business"] == sample_odcs_model
