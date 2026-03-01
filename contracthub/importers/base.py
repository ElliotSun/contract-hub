from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Dict, Optional, Tuple, Type

from open_data_contract_standard.model import Description, OpenDataContractStandard

from contracthub.lifecycle.merge_engine import merge_contract


class BaseImporter(ABC):
    """Base class for ContractHub importers.

    Importers are stateless mappers from source metadata to ODCS contract dicts.
    Patch-mode merge is delegated to lifecycle merge engine.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def _build_imported_contract(self) -> Dict[str, Any]:
        """Build a new imported contract as an ODCS dictionary."""

    def import_contract(self, existing_contract: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        imported_contract = self._build_imported_contract()
        validated_import = self._validate_contract(imported_contract)
        if existing_contract is None:
            self.logger.info("Generated contract without patch mode")
            return validated_import

        self.logger.info("Generated contract with patch mode merge")
        merged_contract = merge_contract(existing=deepcopy(existing_contract), imported=validated_import)
        return self._validate_contract(merged_contract)

    def import_source(self, source: Optional[str] = None, import_args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Compatibility hook for datacontract custom importer style."""
        if source:
            self._set_source(source)
        existing = (import_args or {}).get("existing_contract")
        return self.import_contract(existing_contract=existing)

    def _set_source(self, source: str) -> None:
        raise NotImplementedError(f"{self.__class__.__name__} does not support overriding source at runtime")

    @staticmethod
    def _validate_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
        normalized = deepcopy(contract)
        if isinstance(normalized.get("description"), str):
            normalized["description"] = Description(usage=normalized["description"])

        model = OpenDataContractStandard.model_validate(normalized)
        return model.model_dump(by_alias=True, exclude_none=True)


class ImporterRegistry:
    """Registry for ContractHub importer classes."""

    def __init__(self) -> None:
        self._importers: Dict[str, Type[BaseImporter]] = {}
        self._logger = logging.getLogger(self.__class__.__name__)

    def register_importer(self, name: str, importer_cls: Type[BaseImporter]) -> None:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("Importer name must not be empty")
        if normalized in self._importers:
            self._logger.warning("Overwriting existing importer registration: %s", normalized)
        self._importers[normalized] = importer_cls

    def get_importer(self, name: str) -> Type[BaseImporter]:
        normalized = name.strip().lower()
        if normalized not in self._importers:
            available = ", ".join(sorted(self._importers))
            raise KeyError(f"Importer '{normalized}' not found. Registered: {available}")
        return self._importers[normalized]

    def create(self, name: str, *args: Any, **kwargs: Any) -> BaseImporter:
        importer_cls = self.get_importer(name)
        return importer_cls(*args, **kwargs)

    def list_importers(self) -> list[str]:
        return sorted(self._importers)


default_registry = ImporterRegistry()


def register_importer(name: str, importer_cls: Type[BaseImporter]) -> None:
    default_registry.register_importer(name, importer_cls)


def register_datacontract_importer(
    name: str,
    importer_cls: Type[BaseImporter],
    *,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Register a ContractHub importer in datacontract-cli importer_factory."""

    from datacontract.imports.importer import Importer
    from datacontract.imports.importer_factory import importer_factory
    from open_data_contract_standard.model import OpenDataContractStandard

    class ContractHubDatacontractImporter(Importer):
        def import_source(self, *args: Any, **kwargs: Any) -> Any:
            source, import_args, legacy_spec = _unpack_import_source_args(args, kwargs)
            importer = importer_cls(source, logger=logger)
            contract_dict = importer.import_contract(existing_contract=(import_args or {}).get("existing_contract"))
            odcs = OpenDataContractStandard.model_validate(contract_dict)
            if legacy_spec is None:
                return odcs
            return _apply_odcs_to_legacy_spec(legacy_spec, odcs)

    importer_factory.register_importer(name, ContractHubDatacontractImporter)


def _unpack_import_source_args(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Any]:
    if len(args) >= 2 and isinstance(args[0], str):
        return args[0], args[1] or {}, None

    if len(args) >= 3:
        legacy_spec = args[0]
        source = args[1]
        import_args = args[2] or {}
        if not isinstance(source, str):
            raise TypeError("Expected source as string for custom importer")
        return source, import_args, legacy_spec

    source = kwargs.get("source")
    if not isinstance(source, str):
        raise TypeError("source must be provided as a string")
    import_args = kwargs.get("import_args") or {}
    legacy_spec = kwargs.get("data_contract_specification")
    return source, import_args, legacy_spec


def _apply_odcs_to_legacy_spec(legacy_spec: Any, odcs: Any) -> Any:
    if hasattr(legacy_spec, "id"):
        legacy_spec.id = getattr(odcs, "id", None)

    info = getattr(legacy_spec, "info", None)
    if info is not None:
        if hasattr(info, "title"):
            info.title = getattr(odcs, "name", None)
        if hasattr(info, "version"):
            info.version = getattr(odcs, "version", None)
        if hasattr(info, "description"):
            description = getattr(odcs, "description", None)
            if isinstance(description, dict):
                info.description = description.get("usage") or str(description)
            else:
                info.description = str(description) if description else None

    return legacy_spec
