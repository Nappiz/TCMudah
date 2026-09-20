from __future__ import annotations

import time
from typing import Any

from app.core.telemetry import (
    claim_cold_request,
    finish_request,
    log_request,
    normalize_request_id,
    record_route_latency,
    start_request,
)


class ObservabilityMiddleware:
    """Low-overhead ASGI instrumentation without reading request/response bodies."""

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        inbound_headers = {
            key.lower(): value for key, value in scope.get("headers", [])
        }
        supplied_request_id = inbound_headers.get(b"x-request-id")
        request_id = normalize_request_id(
            supplied_request_id.decode("ascii", errors="ignore")
            if supplied_request_id
            else None
        )
        telemetry, token = start_request(request_id)
        cold = claim_cold_request()
        status_code = 500
        response_bytes = 0

        async def send_with_timing(message: dict) -> None:
            nonlocal status_code, response_bytes
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                elapsed_ms = (time.perf_counter() - telemetry.started_at) * 1000
                app_ms = max(0.0, elapsed_ms - telemetry.db_duration_ms)
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-request-id", request_id.encode("ascii")),
                        (b"x-db-queries", str(telemetry.db_queries).encode("ascii")),
                        (b"x-instance-cold", b"1" if cold else b"0"),
                        (
                            b"server-timing",
                            (
                                f"db;dur={telemetry.db_duration_ms:.2f}, "
                                f"app;dur={app_ms:.2f}"
                            ).encode("ascii"),
                        ),
                    ]
                )
                message["headers"] = headers
            elif message["type"] == "http.response.body":
                response_bytes += len(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, receive, send_with_timing)
        finally:
            duration_ms = (time.perf_counter() - telemetry.started_at) * 1000
            route_object = scope.get("route")
            route = getattr(route_object, "path", None) or scope.get("path", "unknown")
            record_route_latency(route, duration_ms)
            log_request(
                telemetry=telemetry,
                method=scope.get("method", "unknown"),
                route=route,
                status=status_code,
                duration_ms=duration_ms,
                response_bytes=response_bytes,
                cold=cold,
            )
            finish_request(token)

