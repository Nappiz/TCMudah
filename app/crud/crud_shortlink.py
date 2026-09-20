from app.core.supabase_client import supabase
from app.core.rpc import unwrap_rpc_object


SHORTLINK_COLUMNS = "id,slug,url,title,description,active,clicks,created_by,created_at"

def get_admin_shortlinks(limit: int = 20, offset: int = 0, search: str = ""):
    response = supabase().rpc(
        "admin_paginated_shortlinks",
        {
            "p_limit": max(1, min(limit, 100)),
            "p_offset": max(0, offset),
            "p_search": search.strip() or None,
        },
    ).execute()
    payload = unwrap_rpc_object(response.data, rpc_name="admin_paginated_shortlinks")
    return int(payload.get("total") or 0), payload.get("data") or []

def check_slug_exists(slug: str, exclude_id: str = None):
    sb = supabase()
    q = sb.table("shortlinks").select("id").ilike("slug", slug)
    if exclude_id:
        q = q.neq("id", exclude_id)
    exists = q.limit(1).execute()
    return bool(exists.data)

def create_shortlink(data: dict):
    sb = supabase()
    ins = sb.table("shortlinks").insert(data).execute()
    return ins.data[0] if ins.data else None

def get_shortlink_by_id(sid: str):
    sb = supabase()
    res = sb.table("shortlinks").select(SHORTLINK_COLUMNS).eq("id", sid).limit(1).execute()
    return res.data[0] if res.data else None

def update_shortlink(sid: str, data: dict):
    sb = supabase()
    up = sb.table("shortlinks").update(data).eq("id", sid).execute()
    return up.data[0] if up.data else None

def delete_shortlink(sid: str):
    sb = supabase()
    delres = sb.table("shortlinks").delete().eq("id", sid).execute()
    return delres.data if delres.data else None

def resolve_shortlink(slug: str):
    sb = supabase()
    res = (
        sb.table("shortlinks")
        .select("id, url, clicks, active")
        .ilike("slug", slug)
        .eq("active", True)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    return res.data[0]

def increment_shortlink_clicks(sid: str, current_clicks: int):
    sb = supabase()
    try:
        sb.table("shortlinks").update({"clicks": current_clicks + 1}).eq("id", sid).execute()
    except Exception:
        pass
