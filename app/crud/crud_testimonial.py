from app.core.supabase_client import supabase

def get_public_testimonials():
    sb = supabase()
    res = (
        sb.table("testimonials")
        .select("*")
        .eq("visible", True)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

def get_all_testimonials():
    sb = supabase()
    res = sb.table("testimonials").select("*").order("created_at", desc=True).execute()
    return res.data or []

def create_testimonial(data: dict):
    sb = supabase()
    ins = sb.table("testimonials").insert(data).execute()
    return ins.data[0] if ins.data else None

def update_testimonial(tid: str, data: dict):
    sb = supabase()
    up = sb.table("testimonials").update(data).eq("id", tid).execute()
    return up.data[0] if up.data else None

def delete_testimonial(tid: str):
    sb = supabase()
    delres = sb.table("testimonials").delete().eq("id", tid).execute()
    return delres.data if delres.data else None
