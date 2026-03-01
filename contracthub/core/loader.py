from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional, cast
from urllib.parse import urlparse

import requests
import yaml
from open_data_contract_standard.model import OpenDataContractStandard

LOGGER = logging.getLogger(__name__)
DEFAULT_SPARKUTILS_MAX_BYTES = int(
    os.getenv("CONTRACTHUB_SPARKUTILS_MAX_BYTES", str(10 * 1024 * 1024))
)
RuntimeContext = Literal["auto", "synapse", "fabric"]


@dataclass(slots=True)
class ContractLoader:
    """Load ODCS YAML contracts into ODCS model objects."""

    runtime_context: RuntimeContext = "auto"

    def load(self, contract_path: str) -> OpenDataContractStandard:
        return load_contract(contract_path, runtime_context=self.runtime_context)


def load_contract(
    contract_path: str,
    runtime_context: RuntimeContext | str | None = None,
) -> OpenDataContractStandard:
    """Load an ODCS contract from local or remote YAML sources."""
    resolved_context = _resolve_runtime_context(runtime_context)
    contract_text = _read_contract_text(contract_path, resolved_context)
    payload = yaml.safe_load(contract_text)
    if not isinstance(payload, dict):
        raise ValueError("Contract YAML must deserialize into a mapping object")
    return OpenDataContractStandard.model_validate(payload)


def _read_contract_text(contract_path: str, runtime_context: RuntimeContext) -> str:
    if _is_uc_volume_path(contract_path):
        return _read_uc_volume_text(contract_path, runtime_context)

    if _is_local_path(contract_path):
        return _read_local_text(contract_path)

    if _is_adls2_path(contract_path):
        if _notebook_runtime_enabled(runtime_context):
            via_sparkutils = _read_with_mssparkutils(contract_path)
            if via_sparkutils is not None:
                return via_sparkutils
        return _read_adls2_text(contract_path)

    if _is_http_path(contract_path):
        return _read_http_text(contract_path)

    if _notebook_runtime_enabled(runtime_context):
        via_sparkutils = _read_with_mssparkutils(contract_path)
        if via_sparkutils is not None:
            return via_sparkutils

    raise ValueError(f"Unsupported contract path: {contract_path}")


def _read_uc_volume_text(contract_path: str, runtime_context: RuntimeContext) -> str:
    local_candidate = _normalize_uc_volume_local_path(contract_path)
    try:
        return _read_local_text(local_candidate)
    except OSError:
        if _notebook_runtime_enabled(runtime_context):
            via_sparkutils = _read_with_mssparkutils(contract_path)
            if via_sparkutils is not None:
                return via_sparkutils
        raise


def _read_local_text(contract_path: str) -> str:
    parsed = urlparse(contract_path)
    if parsed.scheme == "file":
        local_path = Path(parsed.path).expanduser()
    else:
        local_path = Path(contract_path).expanduser()
    return local_path.read_text(encoding="utf-8")


def _read_adls2_text(contract_path: str) -> str:
    https_url = _adls2_to_https_url(contract_path)
    headers = _adls2_headers(https_url)
    return _read_http_text(https_url, headers=headers)


def _read_http_text(url: str, headers: Optional[dict[str, str]] = None) -> str:
    response = requests.get(url, headers=headers or {}, timeout=30)
    if not response.ok:
        raise RuntimeError(
            f"Failed to fetch contract from {url}: "
            f"status={response.status_code}, body={response.text[:500]}"
        )
    return response.text


def _read_with_mssparkutils(contract_path: str) -> Optional[str]:
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
            text = fs.head(contract_path, DEFAULT_SPARKUTILS_MAX_BYTES)
        if isinstance(text, str) and text.strip():
            LOGGER.debug("Loaded contract via mssparkutils.fs.head from %s", contract_path)
            return text

    return None


def _get_mssparkutils() -> Any:
    try:
        notebookutils = importlib.import_module("notebookutils")
        mssparkutils = getattr(notebookutils, "mssparkutils", None)
        if mssparkutils is not None:
            return mssparkutils
    except Exception:
        pass

    try:
        return importlib.import_module("mssparkutils")
    except Exception:
        return None


def _resolve_runtime_context(runtime_context: RuntimeContext | str | None) -> RuntimeContext:
    candidate = runtime_context or os.getenv("CONTRACTHUB_RUNTIME_CONTEXT", "auto")
    normalized = str(candidate).strip().lower()
    if normalized == "local":
        normalized = "auto"
    if normalized not in {"auto", "synapse", "fabric"}:
        raise ValueError("runtime_context must be one of: auto, synapse, fabric")
    return cast(RuntimeContext, normalized)


def _notebook_runtime_enabled(runtime_context: RuntimeContext) -> bool:
    return runtime_context in {"synapse", "fabric"}


def _is_uc_volume_path(contract_path: str) -> bool:
    return (
        contract_path.startswith("/Volumes/")
        or contract_path.startswith("/dbfs/Volumes/")
        or contract_path.startswith("dbfs:/Volumes/")
    )


def _normalize_uc_volume_local_path(contract_path: str) -> str:
    if contract_path.startswith("dbfs:/Volumes/"):
        return f"/dbfs/{contract_path[len('dbfs:/') :]}"
    return contract_path


def _is_local_path(contract_path: str) -> bool:
    parsed = urlparse(contract_path)
    return parsed.scheme in {"", "file"}


def _is_http_path(contract_path: str) -> bool:
    parsed = urlparse(contract_path)
    return parsed.scheme in {"http", "https"}


def _is_adls2_path(contract_path: str) -> bool:
    parsed = urlparse(contract_path)
    if parsed.scheme in {"abfs", "abfss"}:
        return True
    if parsed.scheme in {"https", "http"} and parsed.netloc.endswith(".dfs.core.windows.net"):
        return True
    return False


def _adls2_to_https_url(contract_path: str) -> str:
    parsed = urlparse(contract_path)
    if parsed.scheme in {"http", "https"}:
        return contract_path

    if parsed.scheme not in {"abfs", "abfss"}:
        raise ValueError(f"Unsupported ADLS2 URI scheme: {parsed.scheme}")

    if "@" not in parsed.netloc:
        raise ValueError("ADLS2 URI must be in format abfss://<container>@<account>.dfs.core.windows.net/<path>")

    container, account_host = parsed.netloc.split("@", 1)
    relative_path = parsed.path.lstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"https://{account_host}/{container}/{relative_path}{query}"


def _adls2_headers(https_url: str) -> dict[str, str]:
    parsed = urlparse(https_url)
    if "sig=" in parsed.query.lower():
        return {}

    token = os.getenv("CONTRACTHUB_ADLS_BEARER_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}
