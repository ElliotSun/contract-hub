import pytest

import contracthub.core.loader as loader
from open_data_contract_standard.model import OpenDataContractStandard


CONTRACT_YAML = """
apiVersion: v3.1.0
kind: DataContract
id: orders
name: orders
version: 1.0.0
status: draft
schema: []
""".strip()


def test_load_contract_from_local_file(tmp_path):
    contract_file = tmp_path / "orders.yaml"
    contract_file.write_text(CONTRACT_YAML, encoding="utf-8")

    loaded = loader.load_contract(str(contract_file))

    assert isinstance(loaded, OpenDataContractStandard)
    assert loaded.id == "orders"


def test_load_contract_from_adls2_via_http(monkeypatch):
    calls: dict[str, object] = {}

    class FakeResponse:
        ok = True
        status_code = 200
        text = CONTRACT_YAML

    class FakeFS:
        @staticmethod
        def head(path, maxBytes):  # noqa: ANN001, N803
            raise AssertionError("mssparkutils should not be used in auto context")

    class FakeMSSparkUtils:
        fs = FakeFS()

    def fake_get(url, headers, timeout):  # noqa: ANN001
        calls["url"] = url
        calls["headers"] = headers
        calls["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(loader, "_get_mssparkutils", lambda: FakeMSSparkUtils())
    monkeypatch.setattr(loader.requests, "get", fake_get)

    loaded = loader.load_contract(
        "abfss://contracts@acct.dfs.core.windows.net/domain/orders.yaml?sig=abc123"
    )

    assert loaded.name == "orders"
    assert calls["url"] == "https://acct.dfs.core.windows.net/contracts/domain/orders.yaml?sig=abc123"
    assert calls["headers"] == {}
    assert calls["timeout"] == 30


@pytest.mark.parametrize("runtime_context", ["synapse", "fabric"])
def test_load_contract_from_adls2_via_mssparkutils(monkeypatch, runtime_context):
    calls: dict[str, object] = {}

    class FakeFS:
        @staticmethod
        def head(path, maxBytes):  # noqa: ANN001, N803
            calls["path"] = path
            calls["max_bytes"] = maxBytes
            return CONTRACT_YAML

    class FakeMSSparkUtils:
        fs = FakeFS()

    monkeypatch.setattr(loader, "_get_mssparkutils", lambda: FakeMSSparkUtils())

    loaded = loader.load_contract(
        "abfss://contracts@acct.dfs.core.windows.net/domain/orders.yaml",
        runtime_context=runtime_context,
    )

    assert loaded.id == "orders"
    assert calls["path"] == "abfss://contracts@acct.dfs.core.windows.net/domain/orders.yaml"
    assert isinstance(calls["max_bytes"], int)


def test_load_contract_from_uc_volume_path_uses_mssparkutils_fallback(monkeypatch):
    calls: dict[str, object] = {}

    class FakeFS:
        @staticmethod
        def head(path, maxBytes):  # noqa: ANN001, N803
            calls["path"] = path
            calls["max_bytes"] = maxBytes
            return CONTRACT_YAML

    class FakeMSSparkUtils:
        fs = FakeFS()

    monkeypatch.setattr(loader, "_read_local_text", lambda _: (_ for _ in ()).throw(FileNotFoundError()))
    monkeypatch.setattr(loader, "_get_mssparkutils", lambda: FakeMSSparkUtils())

    loaded = loader.load_contract(
        "dbfs:/Volumes/main/bronze/contracts/orders.yaml",
        runtime_context="fabric",
    )

    assert loaded.id == "orders"
    assert calls["path"] == "dbfs:/Volumes/main/bronze/contracts/orders.yaml"
    assert isinstance(calls["max_bytes"], int)


def test_load_contract_invalid_runtime_context_raises():
    with pytest.raises(ValueError, match="runtime_context"):
        loader.load_contract("contracts/orders.yaml", runtime_context="notebook")


def test_load_contract_invalid_yaml_payload_type_raises(tmp_path):
    contract_file = tmp_path / "invalid.yaml"
    contract_file.write_text("- not-a-mapping", encoding="utf-8")
    with pytest.raises(ValueError, match="deserialize into a mapping"):
        loader.load_contract(str(contract_file))


def test_load_contract_http_path(monkeypatch):
    class FakeResponse:
        ok = True
        status_code = 200
        text = CONTRACT_YAML

    monkeypatch.setattr(loader.requests, "get", lambda url, headers, timeout: FakeResponse())
    loaded = loader.load_contract("https://example.com/contracts/orders.yaml")
    assert loaded.id == "orders"


def test_read_http_text_error_raises(monkeypatch):
    class FakeResponse:
        ok = False
        status_code = 403
        text = "forbidden"

    monkeypatch.setattr(loader.requests, "get", lambda url, headers, timeout: FakeResponse())

    with pytest.raises(RuntimeError, match="status=403"):
        loader._read_http_text("https://example.com/contracts/orders.yaml", headers={})  # noqa: SLF001


def test_uc_volume_auto_runtime_does_not_fallback_to_sparkutils(monkeypatch):
    monkeypatch.setattr(loader, "_read_local_text", lambda _: (_ for _ in ()).throw(FileNotFoundError()))
    monkeypatch.setattr(loader, "_read_with_mssparkutils", lambda _: CONTRACT_YAML)
    with pytest.raises(FileNotFoundError):
        loader._read_uc_volume_text("dbfs:/Volumes/main/bronze/contracts/orders.yaml", "auto")  # noqa: SLF001


def test_unknown_path_uses_sparkutils_only_in_notebook_runtime(monkeypatch):
    monkeypatch.setattr(loader, "_read_with_mssparkutils", lambda _: CONTRACT_YAML)
    text = loader._read_contract_text("s3://bucket/contract.yaml", "synapse")  # noqa: SLF001
    assert "apiVersion" in text
    with pytest.raises(ValueError, match="Unsupported contract path"):
        loader._read_contract_text("s3://bucket/contract.yaml", "auto")  # noqa: SLF001


def test_read_with_mssparkutils_handles_missing_module_or_fs(monkeypatch):
    monkeypatch.setattr(loader, "_get_mssparkutils", lambda: None)
    assert loader._read_with_mssparkutils("abfss://x@y/p.yaml") is None  # noqa: SLF001

    class NoFs:
        pass

    monkeypatch.setattr(loader, "_get_mssparkutils", lambda: NoFs())
    assert loader._read_with_mssparkutils("abfss://x@y/p.yaml") is None  # noqa: SLF001


def test_read_with_mssparkutils_legacy_head_signature(monkeypatch):
    class LegacyFs:
        @staticmethod
        def head(path, max_bytes):  # noqa: ANN001
            assert "abfss://" in path
            assert isinstance(max_bytes, int)
            return CONTRACT_YAML

    class Util:
        fs = LegacyFs()

    monkeypatch.setattr(loader, "_get_mssparkutils", lambda: Util())
    assert loader._read_with_mssparkutils("abfss://x@y/p.yaml") == CONTRACT_YAML  # noqa: SLF001


def test_get_mssparkutils_resolution_paths(monkeypatch):
    class NotebookUtils:
        mssparkutils = object()

    monkeypatch.setattr(loader.importlib, "import_module", lambda name: NotebookUtils if name == "notebookutils" else None)
    assert loader._get_mssparkutils() is NotebookUtils.mssparkutils  # noqa: SLF001

    def failing_import(name):  # noqa: ANN001
        if name == "notebookutils":
            raise ImportError("missing notebookutils")
        if name == "mssparkutils":
            return "fallback"
        raise ImportError(name)

    monkeypatch.setattr(loader.importlib, "import_module", failing_import)
    assert loader._get_mssparkutils() == "fallback"  # noqa: SLF001


def test_resolve_runtime_context_from_env_and_local_alias(monkeypatch):
    monkeypatch.setenv("CONTRACTHUB_RUNTIME_CONTEXT", "LOCAL")
    assert loader._resolve_runtime_context(None) == "auto"  # noqa: SLF001
    assert loader._resolve_runtime_context("fabric") == "fabric"  # noqa: SLF001


def test_adls2_uri_conversion_and_headers(monkeypatch):
    assert loader._adls2_to_https_url("https://acct.dfs.core.windows.net/c/path.yaml") == "https://acct.dfs.core.windows.net/c/path.yaml"  # noqa: E501, SLF001
    assert loader._adls2_to_https_url("abfss://c@acct.dfs.core.windows.net/path.yaml") == "https://acct.dfs.core.windows.net/c/path.yaml"  # noqa: E501, SLF001

    with pytest.raises(ValueError, match="Unsupported ADLS2 URI scheme"):
        loader._adls2_to_https_url("s3://bucket/path.yaml")  # noqa: SLF001
    with pytest.raises(ValueError, match="format abfss://"):
        loader._adls2_to_https_url("abfss://acct.dfs.core.windows.net/path.yaml")  # noqa: SLF001

    assert loader._adls2_headers("https://x.dfs.core.windows.net/c/path.yaml?sig=abc") == {}  # noqa: SLF001
    monkeypatch.setenv("CONTRACTHUB_ADLS_BEARER_TOKEN", "token-1")
    assert loader._adls2_headers("https://x.dfs.core.windows.net/c/path.yaml") == {"Authorization": "Bearer token-1"}  # noqa: E501, SLF001


def test_read_contract_text_classifiers():
    assert loader._is_uc_volume_path("/Volumes/main/silver/c.yaml") is True  # noqa: SLF001
    assert loader._is_uc_volume_path("dbfs:/Volumes/main/silver/c.yaml") is True  # noqa: SLF001
    assert loader._is_uc_volume_path("abfss://x@y/c.yaml") is False  # noqa: SLF001
    assert loader._normalize_uc_volume_local_path("dbfs:/Volumes/main/c.yaml") == "/dbfs/Volumes/main/c.yaml"  # noqa: E501, SLF001
    assert loader._normalize_uc_volume_local_path("/Volumes/main/c.yaml") == "/Volumes/main/c.yaml"  # noqa: SLF001
    assert loader._is_local_path("file:///tmp/c.yaml") is True  # noqa: SLF001
    assert loader._is_http_path("https://example.com/c.yaml") is True  # noqa: SLF001
    assert loader._is_adls2_path("https://acct.dfs.core.windows.net/c/path.yaml") is True  # noqa: SLF001


def test_read_local_text_with_file_scheme(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text(CONTRACT_YAML, encoding="utf-8")
    text = loader._read_local_text(f"file://{f}")  # noqa: SLF001
    assert "apiVersion" in text


def test_read_with_mssparkutils_without_head_returns_none(monkeypatch):
    class NoHeadFs:
        pass

    class Util:
        fs = NoHeadFs()

    monkeypatch.setattr(loader, "_get_mssparkutils", lambda: Util())
    assert loader._read_with_mssparkutils("abfss://x@y/p.yaml") is None  # noqa: SLF001


def test_get_mssparkutils_returns_none_when_all_imports_fail(monkeypatch):
    monkeypatch.setattr(loader.importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError(name)))
    assert loader._get_mssparkutils() is None  # noqa: SLF001


def test_adls2_headers_without_sig_and_without_token_is_empty(monkeypatch):
    monkeypatch.delenv("CONTRACTHUB_ADLS_BEARER_TOKEN", raising=False)
    assert loader._adls2_headers("https://x.dfs.core.windows.net/c/path.yaml") == {}  # noqa: SLF001
