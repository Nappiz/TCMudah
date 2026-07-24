from app.core.supabase_client import supabase

def get_public_packages():
    sb = supabase()
    # Find active batch
    b_res = sb.table("batches").select("id").eq("is_active", True).order("created_at", desc=True).limit(1).execute()
    active_batch_id = b_res.data[0]["id"] if b_res.data else None
    
    q = sb.table("packages").select("*").eq("visible", True).order("created_at", desc=True)
    if active_batch_id:
        q = q.eq("batch_id", active_batch_id)
        
    res = q.execute()
    return res.data or []

def get_all_packages(batch_id: str = None):
    sb = supabase()
    
    if batch_id is None:
        b_res = sb.table("batches").select("id").eq("is_active", True).order("created_at", desc=True).limit(1).execute()
        batch_id = b_res.data[0]["id"] if b_res.data else None
        
    q = sb.table("packages").select("*").order("created_at", desc=True)
    if batch_id and batch_id != "all":
        q = q.eq("batch_id", batch_id)
        
    res = q.execute()
    return res.data or []

def get_package_by_id(pid: str):
    sb = supabase()
    res = sb.table("packages").select("*").eq("id", pid).limit(1).execute()
    return res.data[0] if res.data else None

def get_packages_by_ids(pids: list[str]):
    if not pids:
        return []
    sb = supabase()
    res = sb.table("packages").select("*").in_("id", pids).execute()
    return res.data or []

def create_package(data: dict):
    sb = supabase()
    if not data.get("batch_id"):
        b_res = sb.table("batches").select("id").eq("is_active", True).order("created_at", desc=True).limit(1).execute()
        if b_res.data:
            data["batch_id"] = b_res.data[0]["id"]
            
    ins = sb.table("packages").insert(data).execute()
    return ins.data[0] if ins.data else None

def update_package(pid: str, data: dict):
    sb = supabase()
    up = sb.table("packages").update(data).eq("id", pid).execute()
    return up.data[0] if up.data else None

def delete_package(pid: str):
    sb = supabase()
    delres = sb.table("packages").delete().eq("id", pid).execute()
    return delres.data if delres.data else None
