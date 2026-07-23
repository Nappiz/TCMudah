from app.core.supabase_client import supabase

def get_public_classes():
    sb = supabase()
    res = (
        sb.table("classes")
        .select("*")
        .eq("visible", True)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

def get_all_classes():
    sb = supabase()
    res = sb.table("classes").select("*").order("created_at", desc=True).execute()
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
