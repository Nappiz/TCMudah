from app.core.supabase_client import supabase
from app.crud.crud_batch import get_active_batch_id_cached

def get_public_classes():
    sb = supabase()
    # Find active batch
    active_batch_id = get_active_batch_id_cached()
    
    q = sb.table("classes").select("*").eq("visible", True).order("created_at", desc=True)
    if active_batch_id:
        q = q.eq("batch_id", active_batch_id)
        
    res = q.execute()
    return res.data or []

def get_all_classes(batch_id: str = None):
    sb = supabase()
    
    if batch_id is None:
        batch_id = get_active_batch_id_cached()
        
    q = sb.table("classes").select("*").order("created_at", desc=True)
    if batch_id and batch_id != "all":
        q = q.eq("batch_id", batch_id)
        
    res = q.execute()
    return res.data or []

def get_class_by_id(cid: str):
    sb = supabase()
    res = sb.table("classes").select("*").eq("id", cid).limit(1).execute()
    return res.data[0] if res.data else None

def get_classes_by_ids(cids: list[str]):
    if not cids:
        return []
    sb = supabase()
    res = sb.table("classes").select("*").in_("id", cids).execute()
    return res.data or []

def create_class(data: dict):
    sb = supabase()
    if not data.get("batch_id"):
        active_id = get_active_batch_id_cached()
        if active_id:
            data["batch_id"] = active_id
            
    ins = sb.table("classes").insert(data).execute()
    return ins.data[0] if ins.data else None

def update_class(cid: str, data: dict):
    sb = supabase()
    up = sb.table("classes").update(data).eq("id", cid).execute()
    return up.data[0] if up.data else None

def delete_class(cid: str):
    sb = supabase()
    delres = sb.table("classes").delete().eq("id", cid).execute()
    return delres.data if delres.data else None
