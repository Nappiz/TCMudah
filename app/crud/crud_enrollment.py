from app.core.supabase_client import supabase
from app.core.pagination import decode_cursor, encode_cursor
from app.core.rpc import unwrap_rpc_object


def _with_opaque_cursor(payload: dict) -> dict:
    payload = payload.copy()
    payload["next_cursor"] = encode_cursor(
        payload.pop("next_after_name", None),
        payload.pop("next_after_id", None),
    )
    return payload


def get_enrollment_bootstrap(
    user_id: str | None = None,
    search: str = "",
    limit: int = 50,
    cursor: str | None = None,
):
    after_name, after_id = decode_cursor(cursor)
    sb = supabase()
    response = sb.rpc(
        "admin_enrollment_bootstrap",
        {
            "p_user_id": user_id,
            "p_search": search.strip() or None,
            "p_limit": max(1, min(limit, 100)),
            "p_after_name": after_name,
            "p_after_id": after_id,
        },
    ).execute()
    payload = unwrap_rpc_object(response.data, rpc_name="admin_enrollment_bootstrap")
    return _with_opaque_cursor(payload)


def get_enrollment_candidates(
    search: str = "",
    limit: int = 50,
    cursor: str | None = None,
):
    after_name, after_id = decode_cursor(cursor)
    sb = supabase()
    response = sb.rpc(
        "admin_enrollment_candidates",
        {
            "p_search": search.strip() or None,
            "p_limit": max(1, min(limit, 100)),
            "p_after_name": after_name,
            "p_after_id": after_id,
        },
    ).execute()
    payload = unwrap_rpc_object(response.data, rpc_name="admin_enrollment_candidates")
    return _with_opaque_cursor(payload)


def get_active_class_ids(user_id: str):
    sb = supabase()
    response = (
        sb.table("enrollments")
        .select("class_id")
        .eq("user_id", user_id)
        .eq("active", True)
        .execute()
    )
    return [row["class_id"] for row in (response.data or [])]

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
