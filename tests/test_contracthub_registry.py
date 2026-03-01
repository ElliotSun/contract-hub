import contracthub.importers as contracthub_importers


def test_default_registry_contains_expected_importers():
    assert "delta" in contracthub_importers.default_registry.list_importers()
    assert "sql-folder" in contracthub_importers.default_registry.list_importers()

