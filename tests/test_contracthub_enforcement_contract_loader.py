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

    class FakeDownloader:
        @staticmethod
        def readall() -> bytes:
            return CONTRACT_YAML.encode("utf-8")

    class FakeFileClient:
        def __init__(self, account_url, file_system_name, file_path, credential):  # noqa: ANN001
            calls["account_url"] = account_url
            calls["file_system_name"] = file_system_name
            calls["file_path"] = file_path
            calls["credential"] = credential

        @staticmethod
        def download_file() -> FakeDownloader:
            return FakeDownloader()

    from contracthub.core import cloud_storage
    monkeypatch.setattr(
        cloud_storage.AzureADLSCloudStorageAdapter,
        "_import_azure_datalake_sdk",
        lambda self: {
            "AccessToken": object,
            "DataLakeFileClient": FakeFileClient,
            "DataLakeServiceClient": object,
        },
    )
    monkeypatch.setattr(
        cloud_storage.AzureADLSCloudStorageAdapter,
        "resolve_credential",
        lambda self, credential=None: "credential-1",
    )

    loaded = loader.load_contract(
        "abfss://contracts@acct.dfs.core.windows.net/domain/orders.yaml"
    )

    assert loaded.name == "orders"
    assert calls["account_url"] == "https://acct.dfs.core.windows.net"
    assert calls["file_system_name"] == "contracts"
    assert calls["file_path"] == "domain/orders.yaml"
    assert calls["credential"] == "credential-1"


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
    assert (
        calls["path"]
        == "abfss://contracts@acct.dfs.core.windows.net/domain/orders.yaml"
    )
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

    monkeypatch.setattr(
        loader, "_read_local_text", lambda _: (_ for _ in ()).throw(FileNotFoundError())
    )
    monkeypatch.setattr(loader, "_get_mssparkutils", lambda: FakeMSSparkUtils())

    loaded = loader.load_contract(
        "dbfs:/Volumes/main/bronze/contracts/orders.yaml",
        runtime_context="fabric",
    )

    assert loaded.id == "orders"
    assert calls["path"] == "dbfs:/Volumes/main/bronze/contracts/orders.yaml"
    assert isinstance(calls["max_bytes"], int)


def test_load_contract_invalid_runtime_context_raises():
    with pytest.raises(Exception, match="runtime_context"):
        loader.load_contract("contracts/orders.yaml", runtime_context="notebook")


def test_load_contract_invalid_yaml_payload_type_raises(tmp_path):
    contract_file = tmp_path / "invalid.yaml"
    contract_file.write_text("- not-a-mapping", encoding="utf-8")
    with pytest.raises(Exception, match="deserialize into a mapping"):
        loader.load_contract(str(contract_file))


def test_load_contract_http_path(monkeypatch):
    class FakeResponse:
        ok = True
        status_code = 200
        text = CONTRACT_YAML

    monkeypatch.setattr(
        loader.requests, "get", lambda url, headers, timeout: FakeResponse()
    )
    loaded = loader.load_contract("https://example.com/contracts/orders.yaml")
    assert loaded.id == "orders"


def test_read_http_text_error_raises(monkeypatch):
    class FakeResponse:
        ok = False
        status_code = 403
        text = "forbidden"

    monkeypatch.setattr(
        loader.requests, "get", lambda url, headers, timeout: FakeResponse()
    )

    with pytest.raises(Exception, match="status=403"):
        loader._read_http_text("https://example.com/contracts/orders.yaml", headers={})  # noqa: SLF001


def test_uc_volume_auto_runtime_does_not_fallback_to_sparkutils(monkeypatch):
    monkeypatch.setattr(
        loader, "_read_local_text", lambda _: (_ for _ in ()).throw(FileNotFoundError())
    )
    monkeypatch.setattr(loader, "_read_with_mssparkutils", lambda _: CONTRACT_YAML)
    with pytest.raises(FileNotFoundError):
        loader._read_uc_volume_text(
            "dbfs:/Volumes/main/bronze/contracts/orders.yaml", "auto"
        )  # noqa: SLF001


def test_unknown_path_uses_sparkutils_only_in_notebook_runtime(monkeypatch):
    monkeypatch.setattr(loader, "_read_with_mssparkutils", lambda _: CONTRACT_YAML)
    text = loader.read_contract_text("foo://bucket/contract.yaml", "synapse")
    assert "apiVersion" in text
    with pytest.raises(Exception, match="Unsupported contract path"):
        loader.read_contract_text("foo://bucket/contract.yaml", "auto")


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

    monkeypatch.setattr(
        loader.importlib,
        "import_module",
        lambda name: NotebookUtils if name == "notebookutils" else None,
    )
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
    assert (
        loader._adls2_to_https_url("https://acct.dfs.core.windows.net/c/path.yaml")
        == "https://acct.dfs.core.windows.net/c/path.yaml"
    )  # noqa: E501, SLF001
    assert (
        loader._adls2_to_https_url("abfss://c@acct.dfs.core.windows.net/path.yaml")
        == "https://acct.dfs.core.windows.net/c/path.yaml"
    )  # noqa: E501, SLF001

    with pytest.raises(Exception, match="Unsupported ADLS2 URI scheme"):
        loader._adls2_to_https_url("s3://bucket/path.yaml")  # noqa: SLF001
    with pytest.raises(Exception, match="format abfss://"):
        loader._adls2_to_https_url("abfss://acct.dfs.core.windows.net/path.yaml")  # noqa: SLF001


def test_read_contract_text_classifiers():
    assert loader.is_uc_volume_path("/Volumes/main/silver/c.yaml") is True
    assert loader.is_uc_volume_path("dbfs:/Volumes/main/silver/c.yaml") is True
    assert loader.is_uc_volume_path("abfss://x@y/c.yaml") is False
    assert (
        loader.normalize_uc_volume_local_path("dbfs:/Volumes/main/c.yaml")
        == "/dbfs/Volumes/main/c.yaml"
    )
    assert (
        loader.normalize_uc_volume_local_path("/Volumes/main/c.yaml")
        == "/Volumes/main/c.yaml"
    )
    assert loader.is_local_path("file:///tmp/c.yaml") is True
    assert loader._is_http_path("https://example.com/c.yaml") is True  # noqa: SLF001
    assert loader.is_adls2_path("https://acct.dfs.core.windows.net/c/path.yaml") is True


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
    monkeypatch.setattr(
        loader.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(ImportError(name)),
    )
    assert loader._get_mssparkutils() is None  # noqa: SLF001


def test_resolve_adls2_credential_uses_static_token_wrapper(monkeypatch):
    from contracthub.core import cloud_storage
    class FakeAccessToken:
        def __init__(self, token, expires_on):  # noqa: ANN001
            self.token = token
            self.expires_on = expires_on

    monkeypatch.setattr(
        cloud_storage.AzureADLSCloudStorageAdapter,
        "_import_azure_datalake_sdk",
        lambda self: {
            "AccessToken": FakeAccessToken,
            "DataLakeFileClient": object,
            "DataLakeServiceClient": object,
        },
    )

    adapter = cloud_storage.AzureADLSCloudStorageAdapter()
    credential = adapter.resolve_credential(credential="token-1")
    token = credential.get_token("https://storage.azure.com/.default")

    assert token.token == "token-1"


def test_resolve_adls2_credential_uses_default_azure_credential(monkeypatch):
    from contracthub.core import cloud_storage
    class FakeAccessToken:
        def __init__(self, token, expires_on=0):  # noqa: ANN001
            self.token = token
            self.expires_on = expires_on

    class FakeDefaultAzureCredential:
        def get_token(self, *args, **kwargs):
            return FakeAccessToken("default-token")

    class FakeAzureIdentity:
        DefaultAzureCredential = FakeDefaultAzureCredential

    monkeypatch.setattr(cloud_storage.config_manager, "get", lambda *args, **kwargs: "default")

    monkeypatch.setattr(
        cloud_storage.AzureADLSCloudStorageAdapter,
        "_import_azure_datalake_sdk",
        lambda self: {
            "AccessToken": FakeAccessToken,
            "DataLakeFileClient": object,
            "DataLakeServiceClient": object,
        },
    )
    monkeypatch.setattr(
        cloud_storage.importlib,
        "import_module",
        lambda name: (
            FakeAzureIdentity
            if name == "azure.identity"
            else (_ for _ in ()).throw(ImportError(name))
        ),
    )

    adapter = cloud_storage.AzureADLSCloudStorageAdapter()
    credential = adapter.resolve_credential()

    assert isinstance(credential, cloud_storage._StaticBearerTokenCredential)
    token = credential.get_token("https://storage.azure.com/.default")
    assert token.token == "default-token"


def test_resolve_adls2_credential_uses_custom_passed_credential(monkeypatch):
    from contracthub.core import cloud_storage
    class FakeAccessToken:
        def __init__(self, token, expires_on=0):  # noqa: ANN001
            self.token = token
            self.expires_on = expires_on

    monkeypatch.setattr(
        cloud_storage.AzureADLSCloudStorageAdapter,
        "_import_azure_datalake_sdk",
        lambda self: {
            "AccessToken": FakeAccessToken,
            "DataLakeFileClient": object,
            "DataLakeServiceClient": object,
        },
    )

    adapter = cloud_storage.AzureADLSCloudStorageAdapter()

    # 1. Without get_token (AttributeError fallback)
    custom_credential = object()
    credential = adapter.resolve_credential(credential=custom_credential)
    assert credential is custom_credential

    # 2. With get_token (should still be returned directly as-is without redundant wrapping)
    class CustomWithToken:
        def get_token(self, *args, **kwargs):
            return FakeAccessToken("custom-token")
    
    custom_token_cred = CustomWithToken()
    credential2 = adapter.resolve_credential(credential=custom_token_cred)
    assert credential2 is custom_token_cred


def test_load_contract_uses_custom_passed_credential(monkeypatch):
    from contracthub.core import cloud_storage
    calls = {}
    custom_credential = object()

    class FakeDownloader:
        @staticmethod
        def readall() -> bytes:
            return CONTRACT_YAML.encode("utf-8")

    class FakeFileClient:
        def __init__(self, account_url, file_system_name, file_path, credential):  # noqa: ANN001
            calls["credential"] = credential

        @staticmethod
        def download_file() -> FakeDownloader:
            return FakeDownloader()

    monkeypatch.setattr(
        cloud_storage.AzureADLSCloudStorageAdapter,
        "_import_azure_datalake_sdk",
        lambda self: {
            "AccessToken": object,
            "DataLakeFileClient": FakeFileClient,
            "DataLakeServiceClient": object,
        },
    )

    loaded = loader.load_contract(
        "abfss://contracts@acct.dfs.core.windows.net/domain/orders.yaml",
        credential=custom_credential,
    )
    assert loaded.id == "orders"
    assert calls["credential"] is custom_credential


def test_contract_loader_class_uses_custom_passed_credential(monkeypatch):
    calls = {}
    custom_credential = object()

    class FakeDownloader:
        @staticmethod
        def readall() -> bytes:
            return CONTRACT_YAML.encode("utf-8")

    class FakeFileClient:
        def __init__(self, account_url, file_system_name, file_path, credential):  # noqa: ANN001
            calls["credential"] = credential

        @staticmethod
        def download_file() -> FakeDownloader:
            return FakeDownloader()

    from contracthub.core import cloud_storage
    monkeypatch.setattr(
        cloud_storage.AzureADLSCloudStorageAdapter,
        "_import_azure_datalake_sdk",
        lambda self: {
            "AccessToken": object,
            "DataLakeFileClient": FakeFileClient,
            "DataLakeServiceClient": object,
        },
    )

    contract_loader = loader.ContractLoader(credential=custom_credential)
    loaded = contract_loader.load("abfss://contracts@acct.dfs.core.windows.net/domain/orders.yaml")
    assert loaded.id == "orders"
    assert calls["credential"] is custom_credential


def test_resolve_adls2_credential_respects_auth_method_env(monkeypatch):
    from contracthub.core import cloud_storage
    class FakeAccessToken:
        def __init__(self, token, expires_on=0):  # noqa: ANN001
            self.token = token
            self.expires_on = expires_on

    class FakeAzureCliCredential:
        def get_token(self, *args, **kwargs):
            return FakeAccessToken("cli-token")

    class FakeManagedIdentityCredential:
        def get_token(self, *args, **kwargs):
            return FakeAccessToken("msi-token")

    class FakeEnvironmentCredential:
        def get_token(self, *args, **kwargs):
            return FakeAccessToken("env-token")

    class FakeDefaultAzureCredential:
        def get_token(self, *args, **kwargs):
            return FakeAccessToken("default-token")

    class FakeAzureIdentity:
        AzureCliCredential = FakeAzureCliCredential
        ManagedIdentityCredential = FakeManagedIdentityCredential
        EnvironmentCredential = FakeEnvironmentCredential
        DefaultAzureCredential = FakeDefaultAzureCredential

    monkeypatch.setattr(
        cloud_storage.AzureADLSCloudStorageAdapter,
        "_import_azure_datalake_sdk",
        lambda self: {
            "AccessToken": FakeAccessToken,
            "DataLakeFileClient": object,
            "DataLakeServiceClient": object,
        },
    )
    monkeypatch.setattr(
        cloud_storage.importlib,
        "import_module",
        lambda name: (
            FakeAzureIdentity
            if name == "azure.identity"
            else (_ for _ in ()).throw(ImportError(name))
        ),
    )

    adapter = cloud_storage.AzureADLSCloudStorageAdapter()

    # 1. Test "cli" / "azurecli"
    monkeypatch.setenv("CONTRACTHUB_AZURE_AUTH_METHOD", "cli")
    credential = adapter.resolve_credential()
    assert isinstance(credential, cloud_storage._StaticBearerTokenCredential)
    assert credential.get_token("https://storage.azure.com/.default").token == "cli-token"

    # 2. Test "msi" / "managedidentity"
    monkeypatch.setenv("CONTRACTHUB_AZURE_AUTH_METHOD", "managedidentity")
    credential = adapter.resolve_credential()
    assert isinstance(credential, cloud_storage._StaticBearerTokenCredential)
    assert credential.get_token("https://storage.azure.com/.default").token == "msi-token"

    # 3. Test "env" / "environment"
    monkeypatch.setenv("CONTRACTHUB_AZURE_AUTH_METHOD", "env")
    credential = adapter.resolve_credential()
    assert isinstance(credential, cloud_storage._StaticBearerTokenCredential)
    assert credential.get_token("https://storage.azure.com/.default").token == "env-token"

    # 4. Test "default" / unset
    monkeypatch.setenv("CONTRACTHUB_AZURE_AUTH_METHOD", "default")
    credential = adapter.resolve_credential()
    assert isinstance(credential, cloud_storage._StaticBearerTokenCredential)
    assert credential.get_token("https://storage.azure.com/.default").token == "default-token"


def test_cloud_storage_adapter_registry():
    from contracthub.core.cloud_storage import cloud_storage_adapter_registry
    
    azure_adapter = cloud_storage_adapter_registry.get_adapter("abfss://my_container@my_account.dfs.core.windows.net/contract.yaml")
    assert azure_adapter is not None
    assert azure_adapter.can_handle("abfss://c@a.dfs.core.windows.net/")
    assert azure_adapter.can_handle("https://onelake.dfs.fabric.microsoft.com/myworkspace/myitem/mycontract.yaml")
    assert azure_adapter.can_handle("abfss://myworkspace@onelake.dfs.fabric.microsoft.com/myitem/mycontract.yaml")
    
    s3_adapter = cloud_storage_adapter_registry.get_adapter("s3://my_bucket/contract.yaml")
    assert s3_adapter is not None
    assert s3_adapter.can_handle("s3a://some-bucket")
    
    gcp_adapter = cloud_storage_adapter_registry.get_adapter("gs://my_bucket/contract.yaml")
    assert gcp_adapter is not None
    assert gcp_adapter.can_handle("gs://some-bucket")


def test_aws_s3_cloud_storage_adapter():
    from contracthub.core.cloud_storage import AwsS3CloudStorageAdapter

    adapter = AwsS3CloudStorageAdapter()
    
    # Verify can_handle
    assert adapter.can_handle("s3://bucket/key")
    assert adapter.can_handle("s3a://bucket/key")
    assert not adapter.can_handle("abfss://bucket/key")

    with pytest.raises(NotImplementedError):
        adapter.resolve_credential()

    with pytest.raises(NotImplementedError):
        adapter.read_text("s3://bucket/key.yaml")

    with pytest.raises(NotImplementedError):
        adapter.discover_delta_tables("s3://bucket/key")


def test_gcp_cloud_storage_adapter():
    from contracthub.core.cloud_storage import GcpCloudStorageAdapter

    adapter = GcpCloudStorageAdapter()

    # Verify can_handle
    assert adapter.can_handle("gs://bucket/key")
    assert not adapter.can_handle("s3://bucket/key")

    with pytest.raises(NotImplementedError):
        adapter.resolve_credential()

    with pytest.raises(NotImplementedError):
        adapter.read_text("gs://bucket/key.yaml")

    with pytest.raises(NotImplementedError):
        adapter.discover_delta_tables("gs://bucket/key")
