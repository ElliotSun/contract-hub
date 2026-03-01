import pytest

from contracthub.importers.sql_importer import SQLFolderImporter, _map_sql_type_to_odcs


def test_sql_folder_importer_rejects_missing_folder():
    with pytest.raises(ValueError, match="Folder does not exist"):
        SQLFolderImporter("/tmp/does-not-exist-12345").import_contract()


def test_sql_folder_importer_rejects_empty_sql_folder(tmp_path):
    folder = tmp_path / "empty_product"
    folder.mkdir()
    with pytest.raises(ValueError, match="No .sql files found"):
        SQLFolderImporter(str(folder)).import_contract()


def test_sql_folder_importer_rejects_folder_with_no_create_table(tmp_path):
    folder = tmp_path / "no_table_product"
    folder.mkdir()
    (folder / "noop.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(ValueError, match="No CREATE TABLE statements found"):
        SQLFolderImporter(str(folder)).import_contract()


def test_map_sql_type_to_odcs_fallback_type():
    assert _map_sql_type_to_odcs("GEOGRAPHY") == "string"


def test_sql_folder_importer_import_source_updates_path(tmp_path):
    folder = tmp_path / "p1"
    folder.mkdir()
    (folder / "t.sql").write_text("CREATE TABLE t (id INT);", encoding="utf-8")
    importer = SQLFolderImporter(str(tmp_path / "unused"))
    contract = importer.import_source(source=str(folder))
    assert contract["name"] == "p1"
