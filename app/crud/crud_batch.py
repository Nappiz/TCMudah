from app.core.supabase_client import supabase
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

def create_batch(data: dict):
    sb = supabase()
    
    # If this batch is active, deactivate others
    if data.get("is_active"):
        sb.table("batches").update({"is_active": False}).neq("id", "00000000-0000-0000-0000-000000000000").execute()
        
    ins = sb.table("batches").insert(data).execute()
    invalidate_active_batch_cache()
    return ins.data[0] if ins.data else None

def update_batch(bid: str, data: dict):
    sb = supabase()
    
    # If this batch is being set to active, deactivate others
    if data.get("is_active"):
        sb.table("batches").update({"is_active": False}).neq("id", bid).execute()
        
    up = sb.table("batches").update(data).eq("id", bid).execute()
    invalidate_active_batch_cache()
    return up.data[0] if up.data else None

def delete_batch(bid: str):
    sb = supabase()
    delres = sb.table("batches").delete().eq("id", bid).execute()
    invalidate_active_batch_cache()
    return delres.data if delres.data else None
