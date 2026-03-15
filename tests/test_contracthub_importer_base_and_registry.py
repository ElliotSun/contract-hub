from datacontract.imports.importer_factory import importer_factory

import contracthub.importers  # noqa: F401


def test_importer_factory_registers_contracthub_importers():
    delta_importer = importer_factory.create("delta")
    sql_importer = importer_factory.create("sql-folder")

    assert delta_importer.import_format == "delta"
    assert sql_importer.import_format == "sql-folder"
