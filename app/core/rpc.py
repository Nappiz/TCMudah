from typing import Any


def unwrap_rpc_object(data: Any, *, rpc_name: str) -> dict:
    """Normalize a scalar json/jsonb RPC result and fail loudly on contract drift."""
    if isinstance(data, dict):
        return data

    # Some PostgREST/client combinations wrap scalar results in a one-item list.
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        return data[0]

    raise RuntimeError(f"RPC {rpc_name} returned an unexpected payload")
