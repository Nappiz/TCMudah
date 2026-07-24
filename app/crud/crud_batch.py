from app.core.supabase_client import supabase

def get_all_batches():
    sb = supabase()
    res = sb.table("batches").select("*").order("created_at", desc=True).execute()
    return res.data or []

def get_active_batch():
    sb = supabase()
    res = sb.table("batches").select("*").eq("is_active", True).order("created_at", desc=True).limit(1).execute()
    return res.data[0] if res.data else None

def create_batch(data: dict):
    sb = supabase()
    
    # If this batch is active, deactivate others
    if data.get("is_active"):
        sb.table("batches").update({"is_active": False}).neq("id", "00000000-0000-0000-0000-000000000000").execute()
        
    ins = sb.table("batches").insert(data).execute()
    return ins.data[0] if ins.data else None

def update_batch(bid: str, data: dict):
    sb = supabase()
    
    # If this batch is being set to active, deactivate others
    if data.get("is_active"):
        sb.table("batches").update({"is_active": False}).neq("id", bid).execute()
        
    up = sb.table("batches").update(data).eq("id", bid).execute()
    return up.data[0] if up.data else None

def delete_batch(bid: str):
    sb = supabase()
    delres = sb.table("batches").delete().eq("id", bid).execute()
    return delres.data if delres.data else None
