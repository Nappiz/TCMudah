from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlparse
from app.core.config import get_settings
from app.core.rpc import unwrap_rpc_object
from app.core.supabase_client import supabase
from uuid import uuid4


ORDER_COLUMNS = "id,user_id,items,total,status,fulfillment_mode,proof_url,sender_name,note,created_at"
settings = get_settings()

_PROOF_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def create_payment_upload_intent(
    user_id: str,
    content_type: str,
    size_bytes: int,
):
    sb = supabase()
    ext = _PROOF_EXTENSIONS[content_type]
    key = f"{user_id}/{uuid4().hex}.{ext}"
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.PAYMENT_UPLOAD_TTL_MINUTES
    )
    sb.rpc(
        "create_payment_upload_intent",
        {
            "p_path": key,
            "p_user_id": user_id,
            "p_bucket_id": settings.PAYMENTS_BUCKET,
            "p_content_type": content_type,
            "p_max_size_bytes": size_bytes,
            "p_expires_at": expires_at.isoformat(),
        },
    ).execute()
    try:
        signed = sb.storage.from_(settings.PAYMENTS_BUCKET).create_signed_upload_url(
            key
        )
    except Exception:
        try:
            sb.table("payment_upload_intents").delete().eq("path", key).execute()
        except Exception:
            pass
        raise
    return {
        "signed_url": signed["signed_url"],
        "path": key,
        "expires_at": expires_at.isoformat(),
        "max_size_bytes": size_bytes,
    }

def create_order_transactional(
    user_id: str,
    items: list[dict],
    proof_path: str,
    sender_name: str,
    note: str | None,
):
    response = supabase().rpc(
        "create_order_transactional",
        {
            "p_user_id": user_id,
            "p_items": items,
            "p_proof_path": proof_path,
            "p_proof_bucket": settings.PAYMENTS_BUCKET,
            "p_sender_name": sender_name,
            "p_note": note,
        },
    ).execute()
    return unwrap_rpc_object(response.data, rpc_name="create_order_transactional")

def get_order_proof_path(order_id: str) -> str | None:
    response = (
        supabase()
        .table("orders")
        .select("proof_url")
        .eq("id", order_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0].get("proof_url")

def create_payment_proof_read_url(proof_path: str) -> str | None:
    if proof_path.startswith(("http://", "https://")):
        candidate = urlparse(proof_path)
        supabase_url = urlparse(settings.SUPABASE_URL)
        expected_prefix = f"/storage/v1/object/public/{settings.PAYMENTS_BUCKET}/"
        if (
            candidate.scheme != "https"
            or candidate.netloc != supabase_url.netloc
            or not candidate.path.startswith(expected_prefix)
        ):
            return None
        # Historical orders stored a public URL. Convert it back to an object
        # path so those proofs continue working after the bucket is private.
        proof_path = unquote(candidate.path.removeprefix(expected_prefix))

    if not proof_path or proof_path.startswith("/") or ".." in proof_path.split("/"):
        return None
    signed = supabase().storage.from_(settings.PAYMENTS_BUCKET).create_signed_url(
        proof_path, settings.PAYMENT_READ_TTL_SECONDS
    )
    return signed.get("signedURL") or signed.get("signed_url")

def get_my_orders(user_id: str, limit: int = 50, offset: int = 0):
    sb = supabase()
    res = (
        sb.table("orders")
        .select(ORDER_COLUMNS)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return res.data or []

def get_paginated_orders(limit: int = 20, offset: int = 0, search: str = "", status: str = ""):
    response = supabase().rpc(
        "admin_paginated_orders",
        {
            "p_limit": max(1, min(limit, 100)),
            "p_offset": max(0, offset),
            "p_search": search.strip() or None,
            "p_status": status or None,
        },
    ).execute()
    payload = unwrap_rpc_object(response.data, rpc_name="admin_paginated_orders")
    return int(payload.get("total") or 0), payload.get("data") or []

def update_order_status(oid: str, status: str):
    response = supabase().rpc(
        "admin_update_order_status",
        {"p_order_id": oid, "p_status": status},
    ).execute()
    if response.data is None:
        return None
    return unwrap_rpc_object(response.data, rpc_name="admin_update_order_status")
