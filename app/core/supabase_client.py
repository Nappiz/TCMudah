from __future__ import annotations

import time
from threading import Lock
from typing import Any

import httpx
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from .config import get_settings
from .telemetry import record_db_call

_settings = get_settings()
_supabase: "ObservedSupabaseClient | None" = None
_http_client: httpx.Client | None = None
_client_lock = Lock()


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
    global _http_client, _supabase
    if _supabase is not None:
        return _supabase

    # Sync routes may concurrently reach the first database call. Serialize
    # client creation so only one connection pool is retained per process.
    with _client_lock:
        if _supabase is not None:
            return _supabase
        timeout = max(1, _settings.SUPABASE_TIMEOUT_SECONDS)
        max_connections = max(1, _settings.SUPABASE_MAX_CONNECTIONS)
        max_keepalive = min(
            max_connections,
            max(0, _settings.SUPABASE_MAX_KEEPALIVE_CONNECTIONS),
        )
        _http_client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive,
                keepalive_expiry=30,
            ),
        )
        _supabase = ObservedSupabaseClient(
            create_client(
                _settings.SUPABASE_URL,
                _settings.SUPABASE_SERVICE_ROLE_KEY,
                options=SyncClientOptions(
                    postgrest_client_timeout=timeout,
                    storage_client_timeout=timeout,
                    function_client_timeout=timeout,
                    httpx_client=_http_client,
                ),
            )
        )
    return _supabase


def close_supabase_client() -> None:
    global _http_client, _supabase
    with _client_lock:
        if _http_client is not None:
            _http_client.close()
        _http_client = None
        _supabase = None
