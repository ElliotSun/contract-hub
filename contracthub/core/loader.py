from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Optional, cast
from urllib.parse import urlparse

if TYPE_CHECKING:
    from azure.core.credentials import TokenCredential

import requests
import yaml
from open_data_contract_standard.model import OpenDataContractStandard

from contracthub.core.config import config_manager
from contracthub.core.cloud_storage import cloud_storage_adapter_registry
from contracthub.exceptions import StorageError

LOGGER = logging.getLogger(__name__)
DEFAULT_SPARKUTILS_MAX_BYTES = int(
    config_manager.get("core.sparkutils_max_bytes", "CONTRACTHUB_SPARKUTILS_MAX_BYTES", str(10 * 1024 * 1024))
)
RuntimeContext = Literal["auto", "synapse", "fabric"]


@dataclass(slots=True)
class ContractLoader:
    """Load ODCS YAML contracts into ODCS model objects.

    Purpose:
    - Provide a single loader that supports all contract storage locations we
      operate in (local paths, ADLS2, HTTP/S, and Unity Catalog volumes).
    - Support notebook runtimes (Synapse/Fabric) via `mssparkutils`.
    - Always return an `OpenDataContractStandard` model, since we only support ODCS.

    Storage/auth scope:
    - ADLS2 access is SDK-based and uses either a configured bearer token,
      a custom passed credential, or `azure.identity.DefaultAzureCredential`.
    - Unity Catalog external volumes are treated as mounted paths and read via
      the local/Databricks filesystem layer, not via ContractHub-managed cloud auth.
    - SAS URL authentication is intentionally not supported.
    """

    runtime_context: RuntimeContext = "auto"
    credential: TokenCredential | None = None

    def load(self, contract_path: str) -> OpenDataContractStandard:
        return load_contract(
            contract_path,
            runtime_context=self.runtime_context,
            credential=self.credential,
        )


def load_contract(
    contract_path: str,
    runtime_context: RuntimeContext | str | None = None,
    credential: TokenCredential | None = None,
) -> OpenDataContractStandard:
    """Load an ODCS contract from local or remote YAML sources.

    This is intentionally more capable than `OpenDataContractStandard.from_file`,
    because we need to handle supported remote paths (ADLS2/HTTP) and
    notebook-only access methods (`mssparkutils`).
    """
    resolved_context = _resolve_runtime_context(runtime_context)
    contract_text = read_contract_text(
        contract_path, resolved_context, credential=credential
    )
    payload = yaml.safe_load(contract_text)
    if not isinstance(payload, dict):
        raise ValueError("Contract YAML must deserialize into a mapping object")
        
    spec_version = payload.get("dataContractSpecification") or payload.get("apiVersion", "")
    if not (str(spec_version).startswith("3.") or str(spec_version).startswith("v3.")):
        raise ValueError(f"ContractHub requires ODCS version 3.x, found: {spec_version}")
        
    return OpenDataContractStandard.model_validate(payload)


def read_contract_text(
    contract_path: str,
    runtime_context: RuntimeContext,
    credential: TokenCredential | None = None,
) -> str:
    """Return raw YAML text from the supported storage backends."""
    if is_uc_volume_path(contract_path):
        return _read_uc_volume_text(contract_path, runtime_context)

    if is_local_path(contract_path):
        return _read_local_text(contract_path)

    adapter = cloud_storage_adapter_registry.get_adapter(contract_path)
    if adapter is not None:
        if contract_path.startswith(("abfs://", "abfss://")) or ".dfs.core.windows.net" in contract_path:
            if _notebook_runtime_enabled(runtime_context):
                via_sparkutils = _read_with_mssparkutils(contract_path)
                if via_sparkutils is not None:
                    return via_sparkutils
        return adapter.read_text(contract_path, credential=credential)

    if _is_http_path(contract_path):
        return _read_http_text(contract_path)

    if _notebook_runtime_enabled(runtime_context):
        via_sparkutils = _read_with_mssparkutils(contract_path)
        if via_sparkutils is not None:
            return via_sparkutils

    raise ValueError(f"Unsupported contract path: {contract_path}")


def _read_uc_volume_text(contract_path: str, runtime_context: RuntimeContext) -> str:
    """Read from UC volume paths, preferring mounted local `/dbfs` access."""
    local_candidate = normalize_uc_volume_local_path(contract_path)
    try:
        return _read_local_text(local_candidate)
    except OSError:
        if _notebook_runtime_enabled(runtime_context):
            via_sparkutils = _read_with_mssparkutils(contract_path)
            if via_sparkutils is not None:
                return via_sparkutils
        raise


def _read_local_text(contract_path: str) -> str:
    """Read a local file (plain path or file:// URI)."""
    parsed = urlparse(contract_path)
    if parsed.scheme == "file":
        local_path = Path(parsed.path).expanduser()
    else:
        local_path = Path(contract_path).expanduser()
    return local_path.read_text(encoding="utf-8")


def _read_adls2_text(
    contract_path: str, credential: TokenCredential | None = None
) -> str:
    """Read ADLS2 content via Azure Storage SDK.

    We prefer the Microsoft SDK here so auth can follow Azure-native patterns
    such as `DefaultAzureCredential` instead of custom REST handling.
    """
    if credential is not None:
        file_client = _create_adls2_file_client(contract_path, credential)
    else:
        file_client = _create_adls2_file_client(contract_path)
    downloader = file_client.download_file()
    payload = downloader.readall()
    if isinstance(payload, bytes):
        return payload.decode("utf-8")
    return str(payload)


def _read_http_text(url: str, headers: Optional[dict[str, str]] = None) -> str:
    """Fetch contract text over HTTP/S with optional headers."""
    try:
        response = requests.get(url, headers=headers or {}, timeout=30)
        if not response.ok:
            raise StorageError(
                f"Failed to fetch contract from {url}: "
                f"status={response.status_code}, body={response.text[:500]}"
            )
        return response.text
    except requests.RequestException as exc:
        raise StorageError(f"Network error while fetching contract from {url}") from exc

def list_adls2_paths(
    root_path: str, credential: TokenCredential | None = None
) -> list[str]:
    """List YAML documents under an ADLS2 root using the Azure SDK."""
    adapter = cloud_storage_adapter_registry.get_adapter(root_path)
    if adapter is not None and hasattr(adapter, "list_paths"):
        return adapter.list_paths(root_path, credential=credential)
    return []


def _read_with_mssparkutils(contract_path: str) -> Optional[str]:
    """Attempt to read via mssparkutils in Synapse/Fabric runtimes."""
    mssparkutils = _get_mssparkutils()
    if mssparkutils is None:
        return None

    fs = getattr(mssparkutils, "fs", None)
    if fs is None:
        return None

    if hasattr(fs, "head"):
        try:
            text = fs.head(contract_path, maxBytes=DEFAULT_SPARKUTILS_MAX_BYTES)
        except TypeError:
            try:
                text = fs.head(contract_path, DEFAULT_SPARKUTILS_MAX_BYTES)
            except Exception as inner_exc:
                raise StorageError(
                    f"Failed to read contract via mssparkutils: {inner_exc}"
                ) from inner_exc
        except Exception as exc:
            raise StorageError(
                f"Failed to read contract via mssparkutils: {exc}"
            ) from exc

        if isinstance(text, str):
            LOGGER.debug(
                "Loaded contract via mssparkutils.fs.head from %s", contract_path
            )
            return text

    return None


def _get_mssparkutils() -> Any:
    try:
        notebookutils = importlib.import_module("notebookutils")
        mssparkutils = getattr(notebookutils, "mssparkutils", None)
        if mssparkutils is not None:
            return mssparkutils
    except ImportError:
        pass
    except Exception as exc:
        LOGGER.debug("Failed to import notebookutils: %s", exc)

    try:
        return importlib.import_module("mssparkutils")
    except ImportError:
        return None
    except Exception as exc:
        LOGGER.debug("Failed to import mssparkutils: %s", exc)
        return None




def _resolve_runtime_context(
    runtime_context: RuntimeContext | str | None,
) -> RuntimeContext:
    """Normalize runtime_context for notebook-aware reads."""
    candidate = runtime_context or config_manager.get("core.runtime_context", "CONTRACTHUB_RUNTIME_CONTEXT", "auto")
    normalized = str(candidate).strip().lower()
    if normalized == "local":
        normalized = "auto"
    if normalized not in {"auto", "synapse", "fabric"}:
        raise ValueError("runtime_context must be one of: auto, synapse, fabric")
    return cast(RuntimeContext, normalized)


def _notebook_runtime_enabled(runtime_context: RuntimeContext) -> bool:
    return runtime_context in {"synapse", "fabric"}


def is_uc_volume_path(path: str) -> bool:
    return (
        path.startswith("/Volumes/")
        or path.startswith("/dbfs/Volumes/")
        or path.startswith("dbfs:/Volumes/")
    )


def normalize_uc_volume_local_path(path: str) -> str:
    if path.startswith("dbfs:/Volumes/"):
        return f"/dbfs/{path[len('dbfs:/') :]}"
    return path


def is_local_path(path: str) -> bool:
    parsed = urlparse(path)
    if parsed.scheme in {"", "file"}:
        return True
    if len(parsed.scheme) == 1 and parsed.scheme.isalpha():
        return True
    return False


def _is_http_path(contract_path: str) -> bool:
    parsed = urlparse(contract_path)
    return parsed.scheme in {"http", "https"}


def is_adls2_path(path: str) -> bool:
    parsed = urlparse(path)
    if parsed.scheme in {"abfs", "abfss"}:
        return True
    if parsed.scheme in {"https", "http"} and parsed.netloc.endswith(
        ".dfs.core.windows.net"
    ):
        return True
    return False


def _adls2_to_https_url(contract_path: str) -> str:
    parsed = urlparse(contract_path)
    if parsed.scheme in {"http", "https"}:
        return contract_path

    if parsed.scheme not in {"abfs", "abfss"}:
        raise ValueError(f"Unsupported ADLS2 URI scheme: {parsed.scheme}")

    if "@" not in parsed.netloc:
        raise ValueError(
            "ADLS2 URI must be in format abfss://<container>@<account>.dfs.core.windows.net/<path>"
        )

    container, account_host = parsed.netloc.split("@", 1)
    relative_path = parsed.path.lstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"https://{account_host}/{container}/{relative_path}{query}"



