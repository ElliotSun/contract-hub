from __future__ import annotations


import pytest
import yaml

import contracthub.interfaces.streamlit.services.contract_service as contract_service_module
from contracthub.interfaces.streamlit.services.contract_service import (
    ContractService,
    analyze_draft,
    parse_contract_yaml,
    serialize_contract_yaml,
)
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


def test_contract_service_save_draft_preserves_read_only_contract_fields_from_main(sample_odcs_dict, tmp_path):
    contracts_dir = tmp_path / "contracts"
    drafts_dir = tmp_path / ".contracthub" / "drafts"
    main_contract = dict(sample_odcs_dict)
    main_contract["id"] = "seller-payments"
    main_contract["tenant"] = "tenant-a"
    main_contract["status"] = "active"
    main_contract["domain"] = "seller"
    main_contract["dataProduct"] = "seller payments"
    main_contract["name"] = "seller_payments_contract"
    main_contract["apiVersion"] = "v3.1.0"
    main_contract["kind"] = "DataContract"
    main_contract["servers"] = [{"server": "main-server", "type": "postgres"}]
    main_contract.setdefault("description", {})["purpose"] = "Main purpose"
    dump_yaml(main_contract, contracts_dir / "seller-payments.yaml")

    draft = dict(main_contract)
    draft["status"] = "deprecated"
    draft["domain"] = "buyer"
    draft["dataProduct"] = "buyer payments"
    draft["tenant"] = "tenant-b"
    draft["name"] = "overwritten_name"
    draft["apiVersion"] = "v9.9.9"
    draft["kind"] = "SomethingElse"
    draft["servers"] = [{"server": "draft-server", "type": "databricks"}]
    draft["description"]["purpose"] = "Draft purpose"

    service = ContractService(contracts_dir=contracts_dir, drafts_dir=drafts_dir)
    saved = service.save_draft(draft, user={"tenant": "tenant-a", "role": "editor", "id": "alice"})

    assert saved["status"] == "active"
    assert saved["domain"] == "seller"
    assert saved["dataProduct"] == "seller payments"
    assert saved["tenant"] == "tenant-a"
    assert saved["name"] == "seller_payments_contract"
    assert saved["apiVersion"] == "v3.1.0"
    assert saved["kind"] == "DataContract"
    assert saved["servers"] == [{"server": "main-server", "type": "postgres"}]
    assert saved["description"]["purpose"] == "Draft purpose"

    persisted_draft = load_yaml(drafts_dir / "alice" / "seller-payments.yaml")
    assert persisted_draft["status"] == "active"
    assert persisted_draft["domain"] == "seller"
    assert persisted_draft["dataProduct"] == "seller payments"
    assert persisted_draft["description"]["purpose"] == "Draft purpose"


def test_contract_service_save_draft_preserves_schema_and_property_technical_fields(sample_odcs_dict, tmp_path):
    contracts_dir = tmp_path / "contracts"
    drafts_dir = tmp_path / ".contracthub" / "drafts"
    main_contract = dict(sample_odcs_dict)
    main_contract["id"] = "seller-payments"
    main_contract["tenant"] = "tenant-a"
    main_contract["schema"][0]["name"] = "payments"
    main_contract["schema"][0]["businessName"] = "Payments"
    main_contract["schema"][0]["description"] = "Main schema description"
    main_contract["schema"][0]["tags"] = ["finance"]
    main_contract["schema"][0]["quality"] = [{"name": "row_count", "metric": "rowCount", "mustBeGreaterThan": 0}]
    main_contract["schema"][0]["properties"][0]["name"] = "payment_id"
    main_contract["schema"][0]["properties"][0]["logicalType"] = "string"
    main_contract["schema"][0]["properties"][0]["required"] = False
    main_contract["schema"][0]["properties"][0]["businessName"] = "Payment Id"
    main_contract["schema"][0]["properties"][0]["description"] = "Main field description"
    dump_yaml(main_contract, contracts_dir / "seller-payments.yaml")

    draft = yaml.safe_load(yaml.safe_dump(main_contract, sort_keys=False))
    draft["schema"][0]["businessName"] = "Edited Payments"
    draft["schema"][0]["description"] = "Edited schema description"
    draft["schema"][0]["tags"] = ["edited"]
    draft["schema"][0]["quality"] = [{"name": "schema_rule", "metric": "rowCount", "mustBeGreaterThan": 1}]
    draft["schema"][0]["properties"][0]["logicalType"] = "int"
    draft["schema"][0]["properties"][0]["required"] = True
    draft["schema"][0]["properties"][0]["businessName"] = "Edited Payment Id"
    draft["schema"][0]["properties"][0]["description"] = "Edited field description"
    draft["schema"][0]["properties"][0]["quality"] = [{"name": "field_rule", "metric": "nullValues", "mustBe": 0}]

    service = ContractService(contracts_dir=contracts_dir, drafts_dir=drafts_dir)
    saved = service.save_draft(draft, user={"tenant": "tenant-a", "role": "editor", "id": "alice"})

    saved_schema = saved["schema"][0]
    saved_field = saved_schema["properties"][0]

    assert saved_schema["name"] == "payments"
    assert saved_schema["businessName"] == "Edited Payments"
    assert saved_schema["description"] == "Edited schema description"
    assert saved_schema["tags"] == ["edited"]
    assert saved_schema["quality"] == [{"name": "schema_rule", "metric": "rowCount", "mustBeGreaterThan": 1}]

    assert saved_field["name"] == "payment_id"
    assert saved_field["logicalType"] == "string"
    assert saved_field["required"] is False
    assert saved_field["businessName"] == "Edited Payment Id"
    assert saved_field["description"] == "Edited field description"
    assert saved_field["quality"] == [{"name": "field_rule", "metric": "nullValues", "mustBe": 0}]


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


def test_contract_service_rejects_non_admin_edit_when_contract_tenant_is_missing(sample_odcs_dict, tmp_path):
    contracts_dir = tmp_path / "contracts"
    main_contract = dict(sample_odcs_dict)
    main_contract["id"] = "seller-payments"
    main_contract.pop("tenant", None)
    dump_yaml(main_contract, contracts_dir / "seller-payments.yaml")

    service = ContractService(contracts_dir=contracts_dir, drafts_dir=tmp_path / ".contracthub" / "drafts")

    with pytest.raises(PermissionError, match="seller-payments"):
        service.get_draft("seller-payments", user={"tenant": "tenant-a", "role": "editor", "id": "alice"})


def test_contract_service_allows_admin_edit_when_contract_tenant_is_missing(sample_odcs_dict, tmp_path):
    contracts_dir = tmp_path / "contracts"
    main_contract = dict(sample_odcs_dict)
    main_contract["id"] = "seller-payments"
    main_contract.pop("tenant", None)
    dump_yaml(main_contract, contracts_dir / "seller-payments.yaml")

    service = ContractService(contracts_dir=contracts_dir, drafts_dir=tmp_path / ".contracthub" / "drafts")

    draft = service.get_draft("seller-payments", user={"tenant": "", "role": "admin", "id": "alice"})
    assert draft["id"] == "seller-payments"


def test_contract_service_list_contracts_marks_tenantless_contract_as_not_editable_for_non_admin(
    sample_odcs_dict, tmp_path
):
    contracts_dir = tmp_path / "contracts"
    contract = dict(sample_odcs_dict)
    contract["id"] = "tenantless-contract"
    contract["dataProduct"] = "tenantless contract"
    contract.pop("tenant", None)
    dump_yaml(contract, contracts_dir / "tenantless-contract.yaml")

    service = ContractService(contracts_dir=contracts_dir, drafts_dir=tmp_path / ".contracthub" / "drafts")
    contracts = service.list_contracts(user={"tenant": "tenant-a", "role": "editor"})

    assert contracts == [
        {
            "id": "tenantless-contract",
            "name": "tenantless contract",
            "version": str(contract["version"]),
            "status": str(contract["status"]),
            "tenant": "",
            "editable": False,
        }
    ]


def test_contract_service_save_draft_preserves_technical_fields_after_schema_and_property_reordering(
    sample_odcs_dict, tmp_path
):
    contracts_dir = tmp_path / "contracts"
    drafts_dir = tmp_path / ".contracthub" / "drafts"
    main_contract = yaml.safe_load(yaml.safe_dump(sample_odcs_dict, sort_keys=False))
    main_contract["id"] = "seller-payments"
    main_contract["tenant"] = "tenant-a"
    main_contract["schema"] = [
        {
            "name": "payments",
            "businessName": "Payments",
            "properties": [
                {"name": "payment_id", "logicalType": "string", "required": True, "businessName": "Payment Id"},
                {"name": "amount", "logicalType": "decimal", "required": False, "businessName": "Amount"},
            ],
        },
        {
            "name": "settlements",
            "businessName": "Settlements",
            "properties": [
                {"name": "settlement_id", "logicalType": "string", "required": True, "businessName": "Settlement Id"},
            ],
        },
    ]
    dump_yaml(main_contract, contracts_dir / "seller-payments.yaml")

    draft = yaml.safe_load(yaml.safe_dump(main_contract, sort_keys=False))
    draft["schema"] = [draft["schema"][1], draft["schema"][0]]
    draft["schema"][1]["properties"] = [draft["schema"][1]["properties"][1], draft["schema"][1]["properties"][0]]
    draft["schema"][1]["businessName"] = "Edited Payments"
    draft["schema"][1]["properties"][0]["businessName"] = "Edited Amount"
    draft["schema"][1]["properties"][0]["logicalType"] = "string"
    draft["schema"][1]["properties"][1]["businessName"] = "Edited Payment Id"
    draft["schema"][1]["properties"][1]["required"] = False

    service = ContractService(contracts_dir=contracts_dir, drafts_dir=drafts_dir)
    saved = service.save_draft(draft, user={"tenant": "tenant-a", "role": "editor", "id": "alice"})

    saved_settlement_schema = saved["schema"][0]
    saved_payments_schema = saved["schema"][1]
    saved_amount = saved_payments_schema["properties"][0]
    saved_payment_id = saved_payments_schema["properties"][1]

    assert saved_settlement_schema["name"] == "settlements"
    assert saved_payments_schema["name"] == "payments"
    assert saved_payments_schema["businessName"] == "Edited Payments"

    assert saved_amount["name"] == "amount"
    assert saved_amount["logicalType"] == "decimal"
    assert saved_amount["businessName"] == "Edited Amount"

    assert saved_payment_id["name"] == "payment_id"
    assert saved_payment_id["required"] is True
    assert saved_payment_id["businessName"] == "Edited Payment Id"


def test_contract_service_analyze_draft_delegates_main_vs_draft_to_governance(sample_odcs_dict, tmp_path, monkeypatch):
    contracts_dir = tmp_path / "contracts"
    main_contract = dict(sample_odcs_dict)
    main_contract["id"] = "seller-payments"
    main_contract["tenant"] = "tenant-a"
    main_contract["status"] = "active"
    dump_yaml(main_contract, contracts_dir / "seller-payments.yaml")

    draft_contract = dict(main_contract)
    draft_contract.setdefault("description", {})["purpose"] = "Draft purpose"
    draft_contract["status"] = "deprecated"

    captured: dict[str, dict[str, object]] = {}

    def fake_analyze(source_contract, target_contract):
        captured["source"] = source_contract
        captured["target"] = target_contract
        return {"allowed": True, "diff": [], "breaking_changes": [], "auto_deprecations": []}

    monkeypatch.setattr(contract_service_module.governance_service, "analyze_contracts", fake_analyze)

    service = ContractService(contracts_dir=contracts_dir, drafts_dir=tmp_path / ".contracthub" / "drafts")
    result = service.analyze_draft(draft_contract, user={"tenant": "tenant-a", "role": "editor", "id": "alice"})

    assert result["allowed"] is True
    assert captured["source"].description.purpose == "Draft purpose"
    assert captured["source"].status == "active"
    assert captured["target"].status == "active"


def test_contract_service_analyze_draft_convenience_wrapper(sample_odcs_dict, tmp_path, monkeypatch):
    contracts_dir = tmp_path / "contracts"
    main_contract = dict(sample_odcs_dict)
    main_contract["id"] = "seller-payments"
    main_contract["tenant"] = "tenant-a"
    dump_yaml(main_contract, contracts_dir / "seller-payments.yaml")

    monkeypatch.setenv("CONTRACTHUB_CONTRACTS_DIR", str(contracts_dir))
    monkeypatch.setenv("CONTRACTHUB_DRAFTS_DIR", str(tmp_path / ".contracthub" / "drafts"))
    monkeypatch.setattr(
        contract_service_module.governance_service,
        "analyze_contracts",
        lambda *args, **kwargs: {"allowed": True, "diff": [], "breaking_changes": [], "auto_deprecations": []},
    )

    result = analyze_draft(main_contract, user={"tenant": "tenant-a", "role": "editor", "id": "alice"})

    assert result["allowed"] is True


def test_contract_service_parse_and_serialize_yaml_helpers_round_trip(sample_odcs_dict):
    source_yaml = yaml.safe_dump(sample_odcs_dict, sort_keys=False)

    payload = parse_contract_yaml(source_yaml)
    rendered = serialize_contract_yaml(payload)

    assert payload["id"] == sample_odcs_dict["id"]
    assert parse_contract_yaml(rendered)["id"] == sample_odcs_dict["id"]


def test_governance_service_analyze_delegates_to_merge_engine(sample_odcs_dict, sample_odcs_model, monkeypatch):
    source_yaml = yaml.safe_dump(sample_odcs_dict, sort_keys=False)
    target_yaml = yaml.safe_dump(sample_odcs_dict, sort_keys=False)
    expected = MergeAnalysis()
    captured: dict[str, object] = {}

    class FakeEngine:
        def analyze(self, *, base_contract, business_contract):
            captured["base"] = base_contract
            captured["business"] = business_contract
            return expected

    monkeypatch.setattr(governance_service, "_MERGE_ENGINE", FakeEngine())

    result = governance_service.analyze(source_yaml, target_yaml)

    assert result is expected
    assert captured["base"] == sample_odcs_model
    assert captured["business"] == sample_odcs_model


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
