import base64
import json


def encode_cursor(sort_name: str | None, row_id: str | None) -> str | None:
    if not sort_name or not row_id:
        return None
    raw = json.dumps({"name": sort_name, "id": row_id}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> tuple[str | None, str | None]:
    if not cursor:
        return None, None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        name = payload["name"]
        row_id = payload["id"]
        if not isinstance(name, str) or not isinstance(row_id, str):
            raise ValueError
        return name, row_id
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid pagination cursor") from exc
