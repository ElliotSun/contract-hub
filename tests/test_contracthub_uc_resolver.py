import pytest

import contracthub.importers.uc_importer as uc


class FakeResponse:
    def __init__(self, *, ok=True, status_code=200, payload=None, text=""):
        self.ok = ok
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_validate_table_fqn_rejects_invalid():
    with pytest.raises(ValueError, match="catalog.schema.table"):
        uc._validate_table_fqn("main.orders")  # noqa: SLF001


def test_get_table_location_requires_warehouse_id(monkeypatch):
    monkeypatch.delenv("DATABRICKS_SQL_WAREHOUSE_ID", raising=False)
    resolver = uc.UCResolver("https://adb.example.com", "token")
    with pytest.raises(ValueError, match="DATABRICKS_SQL_WAREHOUSE_ID"):
        resolver.get_table_location("main.sales.orders")


def test_get_table_location_inline_success(monkeypatch):
    monkeypatch.setenv("DATABRICKS_SQL_WAREHOUSE_ID", "wh-1")
    resolver = uc.UCResolver("https://adb.example.com/", "token")

    payload = {
        "status": {"state": "SUCCEEDED"},
        "result": {
            "manifest": {"schema": {"columns": [{"name": "location"}]}},
            "data_array": [["abfss://container@acct.dfs.core.windows.net/path"]],
        },
    }
    monkeypatch.setattr(uc.requests, "post", lambda *args, **kwargs: FakeResponse(payload=payload))

    location = resolver.get_table_location("main.sales.orders")
    assert location.startswith("abfss://")


def test_get_table_location_raises_when_location_not_found(monkeypatch):
    monkeypatch.setenv("DATABRICKS_SQL_WAREHOUSE_ID", "wh-1")
    resolver = uc.UCResolver("https://adb.example.com", "token")
    payload = {"status": {"state": "SUCCEEDED"}, "result": {"data_array": [["not-a-location"]]}}
    monkeypatch.setattr(uc.requests, "post", lambda *args, **kwargs: FakeResponse(payload=payload))
    with pytest.raises(RuntimeError, match="Could not resolve location"):
        resolver.get_table_location("main.sales.orders")


def test_get_table_location_polls_until_success(monkeypatch):
    monkeypatch.setenv("DATABRICKS_SQL_WAREHOUSE_ID", "wh-1")
    resolver = uc.UCResolver("https://adb.example.com", "token")
    monkeypatch.setattr(uc.time, "sleep", lambda *_: None)

    post_payload = {"status": {"state": "PENDING"}, "statement_id": "stmt-1"}
    poll_payload = {
        "status": {"state": "SUCCEEDED"},
        "result": {
            "manifest": {"schema": {"columns": [{"name": "x"}, {"name": "location"}]}},
            "data_array": [["x", "s3://bucket/path"]],
        },
    }
    monkeypatch.setattr(uc.requests, "post", lambda *args, **kwargs: FakeResponse(payload=post_payload))
    monkeypatch.setattr(uc.requests, "get", lambda *args, **kwargs: FakeResponse(payload=poll_payload))

    location = resolver.get_table_location("main.sales.orders")
    assert location == "s3://bucket/path"


def test_await_result_failed_state_raises(monkeypatch):
    resolver = uc.UCResolver("https://adb.example.com", "token")
    monkeypatch.setattr(uc.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        uc.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(payload={"status": {"state": "FAILED"}}),
    )
    with pytest.raises(RuntimeError, match="state=FAILED"):
        resolver._await_result({"status": {"state": "RUNNING"}, "statement_id": "stmt-1"})  # noqa: SLF001


def test_await_result_returns_payload_when_no_statement_id():
    resolver = uc.UCResolver("https://adb.example.com", "token")
    payload = {"status": {"state": "RUNNING"}}
    assert resolver._await_result(payload) is payload  # noqa: SLF001


def test_raise_for_status_includes_json_details():
    with pytest.raises(RuntimeError, match="status=400"):
        uc._raise_for_status(FakeResponse(ok=False, status_code=400, payload={"error": "bad"}))  # noqa: SLF001


def test_raise_for_status_includes_text_when_json_fails():
    class NonJson(FakeResponse):
        def json(self):  # noqa: D401
            raise ValueError("not json")

    with pytest.raises(RuntimeError, match="raw-error"):
        uc._raise_for_status(NonJson(ok=False, status_code=500, text="raw-error"))  # noqa: SLF001


def test_extract_location_fallback_and_helpers():
    payload = {"result": {"data_array": [["ignored", "gs://bucket/path"]]}}
    assert uc._extract_location_from_result(payload) == "gs://bucket/path"  # noqa: SLF001
    assert uc._location_column_index([{"name": "abc"}, {"name": "location"}]) == 1  # noqa: SLF001
    assert uc._location_column_index([{"name": "abc"}]) is None  # noqa: SLF001
    assert uc._looks_like_storage_uri("dbfs:/mnt/table") is True  # noqa: SLF001
    assert uc._looks_like_storage_uri("https://example.com") is False  # noqa: SLF001
    assert uc._extract_location_from_result({"result": {"data_array": ["bad-row"]}}) is None  # noqa: SLF001
