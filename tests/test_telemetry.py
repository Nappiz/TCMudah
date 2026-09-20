from types import SimpleNamespace

import pytest

from app.core.supabase_client import ObservedSupabaseClient
from app.core.rpc import unwrap_rpc_list
from app.core.telemetry import current_request, finish_request, start_request


class FakeQuery:
    def __init__(self, *, data=None, error: Exception | None = None):
        self.data = data
        self.error = error

    def select(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self.error:
            raise self.error
        return SimpleNamespace(data=self.data)


class FakeClient:
    def __init__(self, query: FakeQuery):
        self.query = query

    def table(self, _table_name: str):
        return self.query


def test_observed_query_records_count_duration_and_rows():
    telemetry, token = start_request("telemetry-success")
    try:
        client = ObservedSupabaseClient(
            FakeClient(FakeQuery(data=[{"id": 1}, {"id": 2}]))
        )
        result = client.table("classes").select("id").execute()

        assert result.data == [{"id": 1}, {"id": 2}]
        assert telemetry.db_queries == 1
        assert telemetry.db_rows == 2
        assert telemetry.db_duration_ms >= 0
        assert current_request() is telemetry
    finally:
        finish_request(token)


def test_observed_query_records_failure_without_swallowing_it(caplog):
    telemetry, token = start_request("telemetry-failure")
    try:
        client = ObservedSupabaseClient(
            FakeClient(FakeQuery(error=ValueError("sensitive database detail")))
        )

        with pytest.raises(ValueError, match="sensitive database detail"):
            client.table("orders").execute()

        assert telemetry.db_queries == 1
        assert '"event":"db_call_failed"' in caplog.text
        assert '"error_type":"ValueError"' in caplog.text
        assert "sensitive database detail" not in caplog.text
    finally:
        finish_request(token)


def test_rpc_list_accepts_postgrest_scalar_array_wrapper():
    assert unwrap_rpc_list([[{"id": "one"}]], rpc_name="wrapped_list") == [
        {"id": "one"}
    ]
