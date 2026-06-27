import abc
import base64
import importlib
import json
import logging
import time
from urllib.parse import urlparse
from typing import Any, List, Optional

from contracthub.core.config import config_manager
from contracthub.exceptions import StorageError

LOGGER = logging.getLogger(__name__)


class CloudStorageAdapter(abc.ABC):
    """
    Base class for cloud storage adapters used to read contracts,
    resolve credentials, and scan for Delta Tables.
    """

    @abc.abstractmethod
    def can_handle(self, uri: str) -> bool:
        """Return True if this adapter can handle the given URI."""
        pass

    @abc.abstractmethod
    def read_text(self, uri: str, credential: Any = None) -> str:
        """Read a file's content as text from the cloud storage."""
        pass

    @abc.abstractmethod
    def resolve_credential(self, credential: Any = None) -> Any:
        """Resolve cloud-specific credential from config or dynamic params."""
        pass

    @abc.abstractmethod
    def discover_delta_tables(self, uri: str, credential: Any = None) -> List[str]:
        """Scan a directory for Delta Tables (folders containing a `_delta_log` directory)."""
        pass


class _StaticBearerTokenCredential:
    """Minimal TokenCredential wrapper around a pre-fetched bearer token."""

    _DEFAULT_TTL_SECONDS = 3600  # 1-hour expiry window

    def __init__(self, token: str, AccessToken: Any) -> None:  # noqa: N803
        self._token = token
        self._access_token_cls = AccessToken

    def get_token(self, *scopes: str, **kwargs: Any) -> Any:  # noqa: ARG002
        expires_on = int(time.time()) + self._DEFAULT_TTL_SECONDS
        try:
            parts = self._token.split(".")
            if len(parts) == 3:
                payload_part = parts[1]
                payload_part += "=" * ((4 - len(payload_part) % 4) % 4)
                payload_json = json.loads(base64.b64decode(payload_part))
                if "exp" in payload_json:
                    expires_on = int(payload_json["exp"])
        except Exception:
            pass
            
        return self._access_token_cls(self._token, expires_on)


class AzureADLSCloudStorageAdapter(CloudStorageAdapter):
    """CloudStorageAdapter implementation for Azure ADLS2."""

    def can_handle(self, uri: str) -> bool:
        parsed = urlparse(uri)
        if parsed.scheme in {"abfs", "abfss"}:
            return True
        if parsed.scheme in {"https", "http"} and parsed.netloc.endswith((".dfs.core.windows.net", ".dfs.fabric.microsoft.com")):
            return True
        return False

    def read_text(self, uri: str, credential: Any = None) -> str:
        file_client = self._create_adls2_file_client(uri, credential)
        downloader = file_client.download_file()
        payload = downloader.readall()
        if isinstance(payload, bytes):
            return payload.decode("utf-8")
        return str(payload)

    def resolve_credential(self, credential: Any = None) -> Any:
        sdk = self._import_azure_datalake_sdk()
        if credential is not None:
            if isinstance(credential, str):
                return _StaticBearerTokenCredential(
                    token=credential,
                    AccessToken=sdk["AccessToken"],
                )
            return credential

        try:
            azure_identity = importlib.import_module("azure.identity")
        except ImportError as exc:
            raise RuntimeError(
                "ADLS2 access requires azure-identity. "
                "Install with `pip install contracthub[azure]`."
            ) from exc

        auth_method = config_manager.get("azure.auth_method", "CONTRACTHUB_AZURE_AUTH_METHOD", "default").lower().strip()
        
        aliases = {
            "cli": "AzureCliCredential",
            "msi": "ManagedIdentityCredential",
            "env": "EnvironmentCredential",
        }
        class_name = aliases.get(auth_method) or auth_method
        target_lower = class_name.lower()
        if not target_lower.endswith("credential"):
            target_lower += "credential"

        cred_class = None
        for attr_name in dir(azure_identity):
            if attr_name.lower() == target_lower:
                cred_class = getattr(azure_identity, attr_name)
                break

        if cred_class is None:
            cred_class = azure_identity.DefaultAzureCredential

        cred_obj = cred_class()
        scope = config_manager.get("azure.scope", default="https://storage.azure.com/.default")
        token = cred_obj.get_token(scope).token
        return _StaticBearerTokenCredential(
            token=token,
            AccessToken=sdk["AccessToken"],
        )

    def discover_delta_tables(self, uri: str, credential: Any = None) -> List[str]:
        parsed = self._parse_adls2_path(uri)
        relative_root = parsed["relative_path"] or ""
        
        fs_client = self._create_adls2_filesystem_client(uri, credential=credential)
        
        table_uris = []
        try:
            paths = list(fs_client.get_paths(path=relative_root, recursive=True))
            delta_log_suffix = "_delta_log"
            delta_table_paths = set()
            for path_item in paths:
                path_name = path_item.name
                if path_name.endswith(delta_log_suffix) or f"{delta_log_suffix}/" in path_name:
                    idx = path_name.find(delta_log_suffix)
                    table_relative_path = path_name[:idx].rstrip("/")
                    delta_table_paths.add(table_relative_path)
            
            for tbl_path in delta_table_paths:
                host = urlparse(parsed['account_url']).hostname
                resolved_uri = f"abfss://{parsed['filesystem']}@{host}/{tbl_path}"
                table_uris.append(resolved_uri)
                
            return sorted(table_uris)
        except Exception as exc:
            LOGGER.error(f"Failed to scan ADLS2 directory for delta tables: {exc}")
            raise StorageError(f"Failed to scan ADLS2 directory for delta tables: {exc}") from exc

    def list_paths(self, root_path: str, credential: Any = None) -> List[str]:
        parsed_root = self._parse_adls2_path(root_path)
        if self._looks_like_yaml_path(parsed_root["relative_path"]):
            return [root_path]

        filesystem_client = self._create_adls2_filesystem_client(root_path, credential)
        discovered: List[str] = []
        for entry in filesystem_client.get_paths(
            path=parsed_root["relative_path"] or None, recursive=True
        ):
            entry_name = str(getattr(entry, "name", "") or "")
            if not entry_name or bool(getattr(entry, "is_directory", False)):
                continue
            if not self._looks_like_yaml_path(entry_name):
                continue
            discovered.append(self._adls2_document_path(parsed_root, entry_name))
        return sorted(discovered, key=str.lower)

    def _create_adls2_file_client(self, contract_path: str, credential: Any = None) -> Any:
        sdk = self._import_azure_datalake_sdk()
        parsed = self._parse_adls2_path(contract_path)
        resolved_credential = self.resolve_credential(credential)
        return sdk["DataLakeFileClient"](
            account_url=parsed["account_url"],
            file_system_name=parsed["filesystem"],
            file_path=parsed["relative_path"],
            credential=resolved_credential,
        )

    def _create_adls2_filesystem_client(self, root_path: str, credential: Any = None) -> Any:
        sdk = self._import_azure_datalake_sdk()
        parsed = self._parse_adls2_path(root_path)
        resolved_credential = self.resolve_credential(credential)
        service_client = sdk["DataLakeServiceClient"](
            account_url=parsed["account_url"],
            credential=resolved_credential,
        )
        return service_client.get_file_system_client(file_system=parsed["filesystem"])

    def _import_azure_datalake_sdk(self) -> dict[str, Any]:
        try:
            azure_core_credentials = importlib.import_module("azure.core.credentials")
            azure_datalake = importlib.import_module("azure.storage.filedatalake")
        except ImportError as exc:
            raise RuntimeError(
                "ADLS2 access requires azure-storage-file-datalake. "
                "Install with `pip install contracthub[azure]`."
            ) from exc

        return {
            "AccessToken": azure_core_credentials.AccessToken,
            "DataLakeFileClient": azure_datalake.DataLakeFileClient,
            "DataLakeServiceClient": azure_datalake.DataLakeServiceClient,
        }

    def _parse_adls2_path(self, contract_path: str) -> dict[str, str]:
        parsed = urlparse(contract_path)
        if parsed.scheme in {"abfs", "abfss"}:
            if "@" not in parsed.netloc:
                raise ValueError(
                    "ADLS2/OneLake URI must be in format abfss://<container>@<account_host>/<path>"
                )
            filesystem, account_host = parsed.netloc.split("@", 1)
            relative_path = parsed.path.lstrip("/")
        elif parsed.scheme in {"http", "https"} and parsed.netloc.endswith((".dfs.core.windows.net", ".dfs.fabric.microsoft.com")):
            path_parts = parsed.path.lstrip("/").split("/", 1)
            if not path_parts or not path_parts[0]:
                raise ValueError("ADLS2 HTTPS URI must include the filesystem path segment")
            filesystem = path_parts[0]
            account_host = parsed.netloc
            relative_path = path_parts[1] if len(path_parts) > 1 else ""
        else:
            raise ValueError(f"Unsupported ADLS2 URI: {contract_path}")

        return {
            "filesystem": filesystem,
            "account_host": account_host,
            "relative_path": relative_path.rstrip("/"),
            "account_url": f"https://{account_host}",
            "scheme": parsed.scheme,
            "query": parsed.query,
        }

    def _adls2_document_path(self, parsed_adls2_path: dict[str, str], relative_path: str) -> str:
        query = f"?{parsed_adls2_path['query']}" if parsed_adls2_path["query"] else ""
        if parsed_adls2_path["scheme"] in {"abfs", "abfss"}:
            return (
                f"{parsed_adls2_path['scheme']}://{parsed_adls2_path['filesystem']}"
                f"@{parsed_adls2_path['account_host']}/{relative_path}{query}"
            )
        return (
            f"{parsed_adls2_path['scheme']}://{parsed_adls2_path['account_host']}"
            f"/{parsed_adls2_path['filesystem']}/{relative_path}{query}"
        )

    def _looks_like_yaml_path(self, path: str) -> bool:
        lowered = str(path or "").lower()
        return lowered.endswith(".yaml") or lowered.endswith(".yml")


class AwsS3CloudStorageAdapter(CloudStorageAdapter):
    """CloudStorageAdapter implementation for Amazon S3 (Placeholder)."""

    def can_handle(self, uri: str) -> bool:
        return uri.startswith("s3://") or uri.startswith("s3a://")

    def read_text(self, uri: str, credential: Any = None) -> str:
        raise NotImplementedError("AWS S3 storage adapter is not implemented yet.")

    def resolve_credential(self, credential: Any = None) -> Any:
        raise NotImplementedError("AWS S3 storage adapter is not implemented yet.")

    def discover_delta_tables(self, uri: str, credential: Any = None) -> List[str]:
        raise NotImplementedError("AWS S3 storage adapter is not implemented yet.")


class GcpCloudStorageAdapter(CloudStorageAdapter):
    """CloudStorageAdapter implementation for Google Cloud Storage (Placeholder)."""

    def can_handle(self, uri: str) -> bool:
        return uri.startswith("gs://")

    def read_text(self, uri: str, credential: Any = None) -> str:
        raise NotImplementedError("GCP GCS storage adapter is not implemented yet.")

    def resolve_credential(self, credential: Any = None) -> Any:
        raise NotImplementedError("GCP GCS storage adapter is not implemented yet.")

    def discover_delta_tables(self, uri: str, credential: Any = None) -> List[str]:
        raise NotImplementedError("GCP GCS storage adapter is not implemented yet.")


class CloudStorageAdapterRegistry:
    """Registry to keep track of and query registered CloudStorageAdapters."""

    def __init__(self) -> None:
        self._adapters: List[CloudStorageAdapter] = []

    def register(self, adapter: CloudStorageAdapter) -> None:
        self._adapters.append(adapter)

    def get_adapter(self, uri: str) -> Optional[CloudStorageAdapter]:
        for adapter in self._adapters:
            if adapter.can_handle(uri):
                return adapter
        return None


# Global instance and default registrations
cloud_storage_adapter_registry = CloudStorageAdapterRegistry()
cloud_storage_adapter_registry.register(AzureADLSCloudStorageAdapter())
cloud_storage_adapter_registry.register(AwsS3CloudStorageAdapter())
cloud_storage_adapter_registry.register(GcpCloudStorageAdapter())
