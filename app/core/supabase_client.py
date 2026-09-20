from __future__ import annotations

import time
from typing import Any

from supabase import Client, create_client

from .config import get_settings
from .telemetry import record_db_call

_settings = get_settings()
_supabase: "ObservedSupabaseClient | None" = None


class _ObservedQuery:
    def __init__(self, query: Any, operation: str):
        self._query = query
        self._operation = operation

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._query, name)
        if not callable(attribute) or name == "execute":
            return attribute

        def call(*args: Any, **kwargs: Any) -> Any:
            result = attribute(*args, **kwargs)
            return (
                _ObservedQuery(result, self._operation)
                if hasattr(result, "execute")
                else result
            )

        return call

    def execute(self) -> Any:
        started = time.perf_counter()
        result = None
        error_type = None
        try:
            result = self._query.execute()
            return result
        except Exception as exc:
            error_type = type(exc).__name__
            raise
        finally:
            record_db_call(
                self._operation,
                (time.perf_counter() - started) * 1000,
                getattr(result, "data", None),
                error_type,
            )


class ObservedSupabaseClient:
    def __init__(self, client: Client):
        self._client = client

    def table(self, table_name: str) -> _ObservedQuery:
        return _ObservedQuery(self._client.table(table_name), f"table:{table_name}")

    def rpc(self, function_name: str, params: dict | None = None) -> _ObservedQuery:
        return _ObservedQuery(
            self._client.rpc(function_name, params), f"rpc:{function_name}"
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def supabase() -> ObservedSupabaseClient:
    global _supabase
    if _supabase is None:
        _supabase = ObservedSupabaseClient(
            create_client(_settings.SUPABASE_URL, _settings.SUPABASE_SERVICE_ROLE_KEY)
        )
    return _supabase
