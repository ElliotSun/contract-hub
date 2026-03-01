import pytest

from open_data_contract_standard.model import OpenDataContractStandard, SchemaObject, SchemaProperty

import contracthub.quality.sql_exporter as exporter_mod


def _minimal_contract_model():
    return OpenDataContractStandard(
        apiVersion="v3.1.0",
        kind="DataContract",
        id="c1",
        name="c1",
        version="1.0.0",
        status="draft",
        schema=[
            SchemaObject(
                name="tbl",
                physicalName="tbl_phys",
                properties=[
                    SchemaProperty(
                        name="id",
                        physicalName="id_phys",
                        logicalType="integer",
                        physicalType="BIGINT",
                    )
                ],
            )
        ],
    )


def test_load_contract_model_from_dict_and_model():
    as_dict = _minimal_contract_model().model_dump(by_alias=True, exclude_none=True)
    loaded_from_dict = exporter_mod._load_contract_model(as_dict)  # noqa: SLF001
    assert loaded_from_dict.id == "c1"

    loaded_from_model = exporter_mod._load_contract_model(_minimal_contract_model())  # noqa: SLF001
    assert loaded_from_model.id == "c1"


def test_load_contract_model_invalid_yaml_raises(tmp_path):
    file_path = tmp_path / "bad.yaml"
    file_path.write_text("- list", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping object"):
        exporter_mod._load_contract_model(file_path)  # noqa: SLF001


def test_prepare_for_sql_export_handles_nested_items_and_existing_custom_property():
    model = _minimal_contract_model()
    prop = model.schema_[0].properties[0]
    prop.customProperties = [exporter_mod.CustomProperty(property="physicalType", value="BIGINT")]
    prop.items = SchemaProperty(logicalType="string", physicalType="STRING")

    prepared = exporter_mod._prepare_for_sql_export(model, use_physical_names=True)  # noqa: SLF001
    schema = prepared.schema_[0]
    assert schema.name == "tbl_phys"
    assert schema.properties[0].name == "id_phys"
    assert len(schema.properties[0].customProperties) == 1


def test_upsert_unity_server_replaces_existing():
    contract = _minimal_contract_model()
    exporter_mod._upsert_unity_server(  # noqa: SLF001
        contract,
        server_name="contracthub_target",
        catalog="main",
        schema_name="silver",
    )
    exporter_mod._upsert_unity_server(  # noqa: SLF001
        contract,
        server_name="contracthub_target",
        catalog="main2",
        schema_name="gold",
    )
    servers = [s for s in (contract.servers or []) if s.server == "contracthub_target"]
    assert len(servers) == 1
    assert servers[0].catalog == "main2"
