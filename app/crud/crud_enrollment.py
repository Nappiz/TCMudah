from app.core.supabase_client import supabase
from app.core.pagination import decode_cursor, encode_cursor
from app.core.rpc import unwrap_rpc_list, unwrap_rpc_object


ENROLLMENT_COLUMNS = "id,user_id,class_id,active,assigned_by,created_at"


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


def set_user_enrollments(user_id: str, class_ids: list[str], assigned_by: str):
    sb = supabase()
    response = sb.rpc(
        "admin_set_user_enrollments",
        {
            "p_user_id": user_id,
            "p_class_ids": class_ids,
            "p_assigned_by": assigned_by,
        },
    ).execute()
    return unwrap_rpc_list(response.data, rpc_name="admin_set_user_enrollments")


def set_package_enrollments(user_id: str, package_id: str, assigned_by: str):
    sb = supabase()
    response = sb.rpc(
        "admin_set_package_enrollments",
        {
            "p_user_id": user_id,
            "p_package_id": package_id,
            "p_assigned_by": assigned_by,
        },
    ).execute()
    return unwrap_rpc_list(response.data, rpc_name="admin_set_package_enrollments")

def get_user_enrollments(user_id: str):
    sb = supabase()
    final = sb.table("enrollments").select(ENROLLMENT_COLUMNS).eq("user_id", user_id).order("created_at", desc=True).execute()
    return final.data or []

def get_active_user_enrollments(user_id: str):
    sb = supabase()
    res = (
        sb.table("enrollments")
        .select(ENROLLMENT_COLUMNS)
        .eq("user_id", user_id)
        .eq("active", True)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

def toggle_enrollment_active(eid: str, active: bool):
    sb = supabase()
    up = sb.table("enrollments").update({"active": active}).eq("id", eid).execute()
    return up.data[0] if up.data else None
