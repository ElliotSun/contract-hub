import os
import abc
from pathlib import Path
from typing import Any, List, Optional
import logging

LOGGER = logging.getLogger(__name__)


class CloudStorageAdapter(abc.ABC):
    """
    Base class for cloud and local storage adapters used to discover Delta Tables
    or perform generic directory scanning across different filesystems.
    """

    @abc.abstractmethod
    def discover_delta_tables(self, source_uri: str, credential: Any = None) -> List[str]:
        """
        Scan a source directory for Delta Tables. A Delta Table is identified
        by the presence of a `_delta_log` directory.
        If `source_uri` itself is a Delta Table, it should return `[source_uri]`.
        """
        pass


class LocalStorageAdapter(CloudStorageAdapter):
    def discover_delta_tables(self, source_uri: str, credential: Any = None) -> List[str]:
        if source_uri.startswith("file://"):
            import urllib.request
            import urllib.parse
            parsed = urllib.parse.urlparse(source_uri)
            source_uri = urllib.request.url2pathname(parsed.path)

        root_path = Path(source_uri)
        if not root_path.exists():
            raise FileNotFoundError(f"Source directory not found: {source_uri}")

        if not root_path.is_dir():
            raise ValueError(f"Source is not a directory: {source_uri}")

        # Check if the root itself is a delta table
        if (root_path / "_delta_log").is_dir():
            return [source_uri]

        # Scan immediate subdirectories
        table_uris = []
        try:
            for item in root_path.iterdir():
                if item.is_dir() and (item / "_delta_log").is_dir():
                    table_uris.append(str(item.absolute()))
        except PermissionError as e:
            LOGGER.warning(f"Permission error scanning local directory: {e}")

        return sorted(table_uris)


class StorageAdapterFactory:
    @staticmethod
    def get_adapter(uri: str) -> Any:
        if not uri:
            return LocalStorageAdapter()
            
        from contracthub.core.cloud_storage import cloud_storage_adapter_registry
        adapter = cloud_storage_adapter_registry.get_adapter(uri)
        if adapter is not None:
            return adapter
            
        return LocalStorageAdapter()
