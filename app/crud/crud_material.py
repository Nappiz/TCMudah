from app.core.supabase_client import supabase

def get_admin_materials(class_id: str):
    sb = supabase()
    q = (
        sb.table("class_materials")
        .select("*")
        .eq("class_id", class_id)
        .order("created_at", desc=True)
    )
    res = q.execute()
    return res.data or []

def create_material(data: dict):
    sb = supabase()
    ins = sb.table("class_materials").insert(data).execute()
    return ins.data[0] if ins.data else None

def get_material_by_id(mid: str):
    sb = supabase()
    res = sb.table("class_materials").select("*").eq("id", mid).limit(1).execute()
    return res.data[0] if res.data else None

def update_material(mid: str, data: dict):
    sb = supabase()
    up = sb.table("class_materials").update(data).eq("id", mid).execute()
    return up.data[0] if up.data else None

def delete_material(mid: str):
    sb = supabase()
    delres = sb.table("class_materials").delete().eq("id", mid).execute()
    return delres.data if delres.data else None

def get_user_materials(class_id: str):
    sb = supabase()
    q = (
        sb.table("class_materials")
        .select("*")
        .eq("class_id", class_id)
        .eq("visible", True)
        .order("created_at", desc=True)
    )
    res = q.execute()
    return res.data or []

def check_user_enrollment(user_id: str, class_id: str):
    sb = supabase()
    enr = (
        sb.table("enrollments")
        .select("id")
        .eq("user_id", user_id)
        .eq("class_id", class_id)
        .eq("active", True)
        .limit(1)
        .execute()
    )
    return bool(enr.data)
