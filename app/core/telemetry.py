from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger("tcmudah.performance")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SLOW_QUERY_MS = float(os.getenv("SLOW_QUERY_MS", "300"))
_REGION = os.getenv("VERCEL_REGION") or os.getenv("AWS_REGION") or "unknown"


@dataclass
class RequestTelemetry:
    request_id: str
    started_at: float
    db_queries: int = 0
    db_duration_ms: float = 0.0
    db_rows: int = 0


_current: ContextVar[RequestTelemetry | None] = ContextVar(
    "request_telemetry", default=None
)
_latencies: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))
_latency_lock = threading.Lock()
_cold_lock = threading.Lock()
_is_cold = True


def normalize_request_id(candidate: str | None) -> str:
    if candidate and _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


def start_request(request_id: str) -> tuple[RequestTelemetry, Token]:
    telemetry = RequestTelemetry(request_id=request_id, started_at=time.perf_counter())
    return telemetry, _current.set(telemetry)


def finish_request(token: Token) -> None:
    _current.reset(token)


def current_request() -> RequestTelemetry | None:
    return _current.get()


def claim_cold_request() -> bool:
    global _is_cold
    with _cold_lock:
        cold = _is_cold
        _is_cold = False
        return cold


def _row_count(data: Any) -> int:
    if isinstance(data, list):
        return len(data)
    if data is None:
        return 0
    return 1


def record_db_call(
    operation: str,
    duration_ms: float,
    data: Any = None,
    error_type: str | None = None,
) -> None:
    telemetry = current_request()
    rows = _row_count(data)
    if telemetry:
        telemetry.db_queries += 1
        telemetry.db_duration_ms += duration_ms
        telemetry.db_rows += rows

    if error_type or duration_ms >= _SLOW_QUERY_MS:
        logger.warning(
            json.dumps(
                {
                    "event": "db_call_failed" if error_type else "slow_db_call",
                    "request_id": telemetry.request_id if telemetry else None,
                    "operation": operation,
                    "duration_ms": round(duration_ms, 2),
                    "rows": rows,
                    "error_type": error_type,
                    "region": _REGION,
                },
                separators=(",", ":"),
            )
        )


def record_route_latency(route: str, duration_ms: float) -> None:
    with _latency_lock:
        _latencies[route].append(duration_ms)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * percentile)))
    return round(ordered[index], 2)


def latency_snapshot() -> dict[str, dict[str, float | int]]:
    with _latency_lock:
        samples = {route: list(values) for route, values in _latencies.items()}
    return {
        route: {
            "count": len(values),
            "p50_ms": _percentile(values, 0.50),
            "p95_ms": _percentile(values, 0.95),
            "p99_ms": _percentile(values, 0.99),
        }
        for route, values in sorted(samples.items())
    }


def log_request(
    *,
    telemetry: RequestTelemetry,
    method: str,
    route: str,
    status: int,
    duration_ms: float,
    response_bytes: int,
    cold: bool,
) -> None:
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": telemetry.request_id,
                "method": method,
                "route": route,
                "status": status,
                "duration_ms": round(duration_ms, 2),
                "db_queries": telemetry.db_queries,
                "db_duration_ms": round(telemetry.db_duration_ms, 2),
                "db_rows": telemetry.db_rows,
                "response_bytes": response_bytes,
                "cold_instance": cold,
                "region": _REGION,
            },
            separators=(",", ":"),
        )
    )
