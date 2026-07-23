from app.core.supabase_client import supabase

def get_all_curriculum(query: str = ""):
    sb = supabase()
    q = sb.table("curriculum").select("*").order("sem", desc=False).order("code", desc=False)
    if query:
        like = f"%{query}%"
        q = q.ilike("name", like)
    res = q.execute()
    return res.data or []

def get_curriculum_by_code(code: str):
    sb = supabase()
    res = sb.table("curriculum").select("id").eq("code", code).limit(1).execute()
    return res.data[0] if res.data else None

def create_curriculum(data: dict):
    sb = supabase()
    ins = sb.table("curriculum").insert(data).execute()
    return ins.data[0] if ins.data else None

def update_curriculum(item_id: str, data: dict):
    sb = supabase()
    up = sb.table("curriculum").update(data).eq("id", item_id).execute()
    return up.data[0] if up.data else None

def delete_curriculum(item_id: str):
    sb = supabase()
    delres = sb.table("curriculum").delete().eq("id", item_id).execute()
    return delres.data if delres.data else None
