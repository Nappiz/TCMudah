from app.core.supabase_client import supabase

def get_public_mentors():
    sb = supabase()
    res = (
        sb.table("mentors")
        .select("*")
        .eq("visible", True)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

def get_all_mentors():
    sb = supabase()
    res = sb.table("mentors").select("*").order("created_at", desc=True).execute()
    return res.data or []

def create_mentor(data: dict):
    sb = supabase()
    ins = sb.table("mentors").insert(data).execute()
    return ins.data[0] if ins.data else None

def update_mentor(mid: str, data: dict):
    sb = supabase()
    up = sb.table("mentors").update(data).eq("id", mid).execute()
    return up.data[0] if up.data else None

def delete_mentor(mid: str):
    sb = supabase()
    delres = sb.table("mentors").delete().eq("id", mid).execute()
    return delres.data if delres.data else None
