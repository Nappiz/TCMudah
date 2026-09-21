from app.core.supabase_client import supabase
from app.core.rpc import unwrap_rpc_object

def submit_feedback(
    user_id: str,
    class_id: str,
    is_staff: bool,
    text: str,
    rating: int | None,
):
    response = supabase().rpc(
        "submit_feedback",
        {
            "p_user_id": user_id,
            "p_class_id": class_id,
            "p_is_staff": is_staff,
            "p_text": text,
            "p_rating": rating,
        },
    ).execute()
    return unwrap_rpc_object(response.data, rpc_name="submit_feedback")

def get_my_feedbacks(user_id: str):
    sb = supabase()
    res = (
        sb.table("feedbacks")
        .select("id, class_id, text, rating, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

def get_admin_feedbacks(
    limit: int = 20,
    offset: int = 0,
    class_id: str | None = None,
):
    response = supabase().rpc(
        "admin_paginated_feedbacks",
        {
            "p_limit": max(1, min(limit, 100)),
            "p_offset": max(0, offset),
            "p_class_id": class_id,
        },
    ).execute()
    payload = unwrap_rpc_object(response.data, rpc_name="admin_paginated_feedbacks")
    return int(payload.get("total") or 0), payload.get("data") or []

def delete_feedback(fid: str):
    sb = supabase()
    delres = sb.table("feedbacks").delete().eq("id", fid).execute()
    return delres.data if delres.data else None
