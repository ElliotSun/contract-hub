import pytest
from unittest.mock import patch
from contracthub.interfaces.cli import main


def test_export_ge_handles_missing_pyspark_gracefully(monkeypatch):
    class FakeExporter:
        def export_to_path(self, *args, **kwargs):
            raise RuntimeError(
                "datacontract-cli Great Expectations export with engine='spark' requires pyspark to be installed"
            )

    monkeypatch.setattr(
        "contracthub.interfaces.cli.GreatExpectationsExporter", lambda: FakeExporter()
    )

    test_args = [
        "contracthub",
        "export-ge",
        "--contract",
        "dummy.yaml",
        "--output",
        "out.json",
    ]
    with patch("sys.argv", test_args):
        with pytest.raises(SystemExit) as excinfo:
            main()

        assert "requires pyspark to be installed" in str(excinfo.value)
