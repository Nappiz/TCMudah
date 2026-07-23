from app.core.supabase_client import supabase

def get_package_class_ids(package_id: str):
    sb = supabase()
    pkg_res = sb.table("packages").select("class_ids").eq("id", package_id).limit(1).execute()
    if not pkg_res.data:
        return None
    return pkg_res.data[0]["class_ids"]

def get_existing_enrollments(user_id: str, class_ids: list[str]):
    if not class_ids:
        return set()
    sb = supabase()
    existing = sb.table("enrollments").select("class_id").eq("user_id", user_id).in_("class_id", class_ids).execute()
    return {row["class_id"] for row in (existing.data or [])}

def insert_enrollments(to_insert_data: list[dict]):
    if not to_insert_data:
        return
    sb = supabase()
    sb.table("enrollments").insert(to_insert_data).execute()

def update_enrollments_active(user_id: str, class_ids: list[str]):
    if not class_ids:
        return
    sb = supabase()
    sb.table("enrollments").update({"active": True}).eq("user_id", user_id).in_("class_id", class_ids).execute()

def get_user_enrollments(user_id: str):
    sb = supabase()
    final = sb.table("enrollments").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return final.data or []

def get_active_user_enrollments(user_id: str):
    sb = supabase()
    res = (
        sb.table("enrollments")
        .select("*")
        .eq("user_id", user_id)
        .eq("active", True)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

def get_all_user_enrollments(user_id: str):
    sb = supabase()
    existing = sb.table("enrollments").select("id, class_id").eq("user_id", user_id).execute()
    return {row["class_id"]: row for row in (existing.data or [])}

def delete_enrollments(ids: list[str]):
    if not ids:
        return
    sb = supabase()
    sb.table("enrollments").delete().in_("id", ids).execute()

def toggle_enrollment_active(eid: str, active: bool):
    sb = supabase()
    up = sb.table("enrollments").update({"active": active}).eq("id", eid).execute()
    return up.data[0] if up.data else None
