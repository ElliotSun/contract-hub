from datacontract.imports.importer_factory import importer_factory

from contracthub.importers.delta_importer import DeltaTableImporter
from contracthub.importers.sql_importer import SQLFolderImporter

# Register ContractHub custom importers with datacontract-cli importer factory.
importer_factory.register_importer("delta", DeltaTableImporter)  # type: ignore[arg-type]
importer_factory.register_importer("delta-table", DeltaTableImporter)  # type: ignore[arg-type]
importer_factory.register_importer("sql-folder", SQLFolderImporter)  # type: ignore[arg-type]
importer_factory.register_importer("delta-ddl", SQLFolderImporter)  # type: ignore[arg-type]

__all__ = [
    "DeltaTableImporter",
    "SQLFolderImporter",
]
