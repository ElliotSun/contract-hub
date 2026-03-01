import json

import contracthub.quality.ge_exporter as ge_adapter


def test_generate_expectation_suite_uses_datacontract_exporter(monkeypatch):
    class FakeExporter:
        @staticmethod
        def export(data_contract, schema_name, server, sql_server_type, export_args):
            assert schema_name == "all"
            assert export_args["engine"] == "spark"
            return json.dumps(
                {
                    "name": "suite.sample",
                    "expectations": [
                        {
                            "type": "expect_column_values_to_not_be_null",
                            "kwargs": {"column": "id"},
                            "meta": {},
                        }
                    ],
                }
            )

    class FakeExpectationConfiguration:
        def __init__(self, expectation_type, kwargs, meta):
            self.expectation_type = expectation_type
            self.kwargs = kwargs
            self.meta = meta

    class FakeExpectationSuite:
        def __init__(self, expectation_suite_name):
            self.expectation_suite_name = expectation_suite_name
            self.expectations = []

        def add_expectation(self, expectation_configuration):
            self.expectations.append(expectation_configuration)

    monkeypatch.setattr(ge_adapter.exporter_factory, "create", lambda _: FakeExporter())
    monkeypatch.setattr(
        ge_adapter,
        "_load_ge_suite_classes",
        lambda: (FakeExpectationSuite, FakeExpectationConfiguration),
    )

    suite = ge_adapter.generate_expectation_suite(contract=object(), schema_name="all")
    assert suite.expectation_suite_name == "suite.sample"
    assert len(suite.expectations) == 1
    assert suite.expectations[0].expectation_type == "expect_column_values_to_not_be_null"

