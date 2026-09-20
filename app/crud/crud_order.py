from app.core.config import get_settings
from app.core.rpc import unwrap_rpc_object
from app.core.supabase_client import supabase
from uuid import uuid4


ORDER_COLUMNS = "id,user_id,items,total,status,proof_url,sender_name,note,created_at"
settings = get_settings()

def upload_payment_proof(user_id: str, file_name: str, file_data: bytes, content_type: str):
    sb = supabase()
    ext = (file_name or "").split(".")[-1].lower() or "jpg"
    key = f"{user_id}/{uuid4().hex}.{ext}"
    sb.storage.from_(settings.PAYMENTS_BUCKET).upload(
        path=key,
        file=file_data,
        file_options={"contentType": content_type, "upsert": "true"},
    )
    pub = sb.storage.from_(settings.PAYMENTS_BUCKET).get_public_url(key)
    return pub

def create_order_transactional(
    user_id: str,
    items: list[dict],
    proof_url: str | None,
    sender_name: str,
    note: str | None,
):
    response = supabase().rpc(
        "create_order_transactional",
        {
            "p_user_id": user_id,
            "p_items": items,
            "p_proof_url": proof_url,
            "p_sender_name": sender_name,
            "p_note": note,
        },
    ).execute()
    return unwrap_rpc_object(response.data, rpc_name="create_order_transactional")

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
