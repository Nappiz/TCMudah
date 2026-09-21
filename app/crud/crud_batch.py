from app.core.supabase_client import supabase
from app.core.rpc import unwrap_rpc_object
import time
import threading

_active_batch_cache = {"id": None, "expires_at": 0.0}
_active_batch_cache_lock = threading.Lock()
CACHE_TTL = 60.0  # seconds
BATCH_COLUMNS = "id,name,is_active,created_at"

def get_active_batch_id_cached() -> str | None:
    global _active_batch_cache
    now = time.monotonic()
    if now < _active_batch_cache["expires_at"]:
        return _active_batch_cache["id"]

    with _active_batch_cache_lock:
        now = time.monotonic()
        if now < _active_batch_cache["expires_at"]:
            return _active_batch_cache["id"]

        sb = supabase()
        res = sb.table("batches").select("id").eq("is_active", True).order("created_at", desc=True).limit(1).execute()
        bid = res.data[0]["id"] if res.data else None
        _active_batch_cache["id"] = bid
        _active_batch_cache["expires_at"] = now + CACHE_TTL
        return bid

def invalidate_active_batch_cache():
    global _active_batch_cache
    _active_batch_cache["id"] = None
    _active_batch_cache["expires_at"] = 0.0

def get_all_batches():
    sb = supabase()
    res = sb.table("batches").select(BATCH_COLUMNS).order("created_at", desc=True).execute()
    return res.data or []

def get_active_batch():
    sb = supabase()
    res = sb.table("batches").select(BATCH_COLUMNS).eq("is_active", True).order("created_at", desc=True).limit(1).execute()
    return res.data[0] if res.data else None

def get_batch_by_id(batch_id: str):
    res = (
        supabase()
        .table("batches")
        .select(BATCH_COLUMNS)
        .eq("id", batch_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None

def create_batch(data: dict):
    response = supabase().rpc(
        "admin_create_batch",
        {"p_name": data["name"], "p_is_active": bool(data.get("is_active"))},
    ).execute()
    invalidate_active_batch_cache()
    return unwrap_rpc_object(response.data, rpc_name="admin_create_batch")

def update_batch(bid: str, data: dict):
    response = supabase().rpc(
        "admin_update_batch", {"p_batch_id": bid, "p_patch": data}
    ).execute()
    invalidate_active_batch_cache()
    if response.data is None:
        return None
    return unwrap_rpc_object(response.data, rpc_name="admin_update_batch")

def delete_batch(bid: str):
    sb = supabase()
    delres = sb.table("batches").delete().eq("id", bid).execute()
    invalidate_active_batch_cache()
    return delres.data if delres.data else None
