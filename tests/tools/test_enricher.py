from unittest.mock import MagicMock
from pathlib import Path
from contracthub.tools.enricher import ContractEnricher
from open_data_contract_standard.model import OpenDataContractStandard

def test_contract_enricher(mocker, tmp_path):
    # Mock OpenAI client
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"edge_label": "MOCKED_LABEL"}'

    # We patch openai.Client to mock the client instantiation and completions
    mock_openai_client_class = mocker.patch("openai.Client")
    mock_client_instance = mock_openai_client_class.return_value
    mock_client_instance.chat.completions.create.return_value = mock_response

    # Copy the sample odcs to tmp_path
    sample_path = Path("sample_odcs.yaml")
    test_path = tmp_path / "test_odcs.yaml"
    with open(sample_path, "r") as f:
        test_path.write_text(f.read())

    enricher = ContractEnricher()
    enricher.process(str(test_path), max_workers=2)

    # Validate OpenAI was called correctly
    assert mock_client_instance.chat.completions.create.call_count > 0

    # Read back the enriched YAML
    enriched_odcs = OpenDataContractStandard.from_file(str(test_path))

    # Verify that the semantic edge label was added
    labels_found = 0
    for schema in enriched_odcs.schema_:
        if schema.relationships:
            for rel in schema.relationships:
                if rel.customProperties:
                    for cp in rel.customProperties:
                        if cp.property == "graph_semantic.edge_label" and cp.value == "MOCKED_LABEL":
                            labels_found += 1
        if schema.properties:
            for prop in schema.properties:
                if prop.relationships:
                    for rel in prop.relationships:
                        if rel.customProperties:
                            for cp in rel.customProperties:
                                if cp.property == "graph_semantic.edge_label" and cp.value == "MOCKED_LABEL":
                                    labels_found += 1

    assert labels_found > 0
