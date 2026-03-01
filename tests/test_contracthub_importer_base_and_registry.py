from types import SimpleNamespace

import pytest

import contracthub.importers.base as importer_base
import contracthub.importers.base as importer_registry


def _minimal_contract(name: str = "dataset") -> dict:
    return {
        "apiVersion": "v3.1.0",
        "kind": "DataContract",
        "id": name,
        "name": name,
        "version": "1.0.0",
        "status": "draft",
        "schema": [],
    }


class DummyImporter(importer_base.BaseImporter):
    def __init__(self, source: str = "initial", logger=None):  # noqa: ANN001
        super().__init__(logger=logger)
        self.source = source

    def _build_imported_contract(self):  # noqa: D401
        return _minimal_contract(name=self.source)

    def _set_source(self, source: str) -> None:
        self.source = source


class NoSetSourceImporter(importer_base.BaseImporter):
    def _build_imported_contract(self):  # noqa: D401
        return _minimal_contract()


def test_base_importer_import_contract_without_patch():
    result = DummyImporter("orders").import_contract()
    assert result["id"] == "orders"


def test_base_importer_import_contract_with_patch_mode(monkeypatch):
    importer = DummyImporter("orders")
    monkeypatch.setattr(importer_base, "merge_contract", lambda existing, imported: _minimal_contract("merged"))
    result = importer.import_contract(existing_contract=_minimal_contract("old"))
    assert result["id"] == "merged"


def test_base_importer_import_source_sets_source_and_uses_existing(monkeypatch):
    importer = DummyImporter("old")
    monkeypatch.setattr(
        importer,
        "import_contract",
        lambda existing_contract=None: {"existing": existing_contract},  # noqa: ANN001
    )
    result = importer.import_source(source="new", import_args={"existing_contract": {"id": "x"}})
    assert importer.source == "new"
    assert result["existing"]["id"] == "x"


def test_base_importer_default_set_source_raises():
    with pytest.raises(NotImplementedError, match="does not support overriding source"):
        NoSetSourceImporter()._set_source("x")  # noqa: SLF001


def test_base_importer_validate_contract_maps_string_description():
    contract = _minimal_contract("orders")
    contract["description"] = "plain text description"
    validated = importer_base.BaseImporter._validate_contract(contract)
    assert validated["description"]["usage"] == "plain text description"


def test_registry_register_get_create_and_list():
    registry = importer_registry.ImporterRegistry()
    registry.register_importer("dummy", DummyImporter)
    assert registry.get_importer("dummy") is DummyImporter
    created = registry.create("dummy", "created")
    assert isinstance(created, DummyImporter)
    assert created.source == "created"
    assert registry.list_importers() == ["dummy"]


def test_registry_rejects_invalid_and_unknown_names():
    registry = importer_registry.ImporterRegistry()
    with pytest.raises(ValueError, match="must not be empty"):
        registry.register_importer("   ", DummyImporter)
    with pytest.raises(KeyError, match="Registered:"):
        registry.get_importer("missing")


def test_registry_logs_warning_when_overwriting(caplog):
    registry = importer_registry.ImporterRegistry()
    registry.register_importer("dummy", DummyImporter)
    registry.register_importer("dummy", DummyImporter)
    assert "Overwriting existing importer registration" in caplog.text


def test_unpack_import_source_args_variants():
    source, import_args, legacy = importer_registry._unpack_import_source_args(("src", {"x": 1}), {})  # noqa: SLF001
    assert source == "src"
    assert import_args == {"x": 1}
    assert legacy is None

    legacy_spec = object()
    source, import_args, legacy = importer_registry._unpack_import_source_args(  # noqa: SLF001
        (legacy_spec, "src", {"y": 2}),
        {},
    )
    assert source == "src"
    assert import_args == {"y": 2}
    assert legacy is legacy_spec

    source, import_args, legacy = importer_registry._unpack_import_source_args(  # noqa: SLF001
        (),
        {"source": "src", "import_args": {"z": 3}, "data_contract_specification": legacy_spec},
    )
    assert source == "src"
    assert import_args == {"z": 3}
    assert legacy is legacy_spec

    with pytest.raises(TypeError, match="Expected source as string"):
        importer_registry._unpack_import_source_args((object(), object(), {}), {})  # noqa: SLF001
    with pytest.raises(TypeError, match="source must be provided"):
        importer_registry._unpack_import_source_args((), {})  # noqa: SLF001


def test_apply_odcs_to_legacy_spec_handles_dict_and_string_description():
    legacy = SimpleNamespace(id=None, info=SimpleNamespace(title=None, version=None, description=None))
    odcs_dict_desc = SimpleNamespace(id="id-1", name="name-1", version="1.2.3", description={"usage": "hello"})
    mapped = importer_registry._apply_odcs_to_legacy_spec(legacy, odcs_dict_desc)  # noqa: SLF001
    assert mapped.id == "id-1"
    assert mapped.info.title == "name-1"
    assert mapped.info.version == "1.2.3"
    assert mapped.info.description == "hello"

    odcs_string_desc = SimpleNamespace(id="id-2", name="name-2", version="2.0.0", description="desc")
    mapped = importer_registry._apply_odcs_to_legacy_spec(legacy, odcs_string_desc)  # noqa: SLF001
    assert mapped.info.description == "desc"


def test_register_datacontract_importer_supports_current_and_legacy_signatures(monkeypatch):
    captured = {}

    def fake_register(name, importer_cls):  # noqa: ANN001
        captured["name"] = name
        captured["cls"] = importer_cls

    from datacontract.imports.importer_factory import importer_factory

    monkeypatch.setattr(importer_factory, "register_importer", fake_register)
    importer_registry.register_datacontract_importer("dummy-contracthub", DummyImporter)
    assert captured["name"] == "dummy-contracthub"

    cls = captured["cls"]
    instance = cls("dummy-contracthub")

    current_result = instance.import_source("orders", {"existing_contract": _minimal_contract("old")})
    assert current_result.id == "orders"

    legacy_spec = SimpleNamespace(id=None, info=SimpleNamespace(title=None, version=None, description=None))
    legacy_result = instance.import_source(legacy_spec, "payments", {})
    assert legacy_result.info.title == "payments"
