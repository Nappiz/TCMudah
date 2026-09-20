from typing import Any


def unwrap_rpc_object(data: Any, *, rpc_name: str) -> dict:
    """Normalize a scalar json/jsonb RPC result and fail loudly on contract drift."""
    if isinstance(data, dict):
        return data

    # Some PostgREST/client combinations wrap scalar results in a one-item list.
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        return data[0]

    raise RuntimeError(f"RPC {rpc_name} returned an unexpected payload")


def unwrap_rpc_list(data: Any, *, rpc_name: str) -> list:
    # Scalar JSON arrays can be wrapped once by some PostgREST/client versions.
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], list):
        return data[0]
    if isinstance(data, list):
        return data
    raise RuntimeError(f"RPC {rpc_name} returned an unexpected payload")


def public_rpc_error(exc: Exception, allowed_messages: tuple[str, ...]) -> str | None:
    """Return only an allow-listed business error; never leak database details."""
    raw = str(getattr(exc, "message", "") or exc)
    return next((message for message in allowed_messages if message in raw), None)
