from app.core.supabase_client import supabase
from app.core.rpc import unwrap_rpc_object

def get_user_by_email(email: str):
    sb = supabase()
    res = sb.table("users").select("*").eq("email", email).limit(1).execute()
    return res.data[0] if res.data else None

def get_user_by_id(user_id: str):
    sb = supabase()
    res = sb.table("users").select("*").eq("id", user_id).limit(1).execute()
    return res.data[0] if res.data else None

def create_user(email: str, password_hash: str, full_name: str, nim: str = None):
    sb = supabase()
    inserted = sb.table("users").insert({
        "email": email,
        "password_hash": password_hash,
        "full_name": full_name,
        "nim": nim,
        "role": "peserta",
    }).execute()
    return inserted.data[0] if inserted.data else None

def get_paginated_users(limit: int = 20, offset: int = 0, search: str = "", role_filter: str = ""):
    sb = supabase()
    response = sb.rpc(
        "admin_paginated_users",
        {
            "p_limit": max(1, min(limit, 100)),
            "p_offset": max(0, offset),
            "p_search": search.strip() or None,
            "p_role": role_filter or None,
        },
    ).execute()
    payload = unwrap_rpc_object(response.data, rpc_name="admin_paginated_users")
    return int(payload.get("total") or 0), payload.get("data") or []

def update_user_role(user_id: str, role: str):
    sb = supabase()
    upd = sb.table("users").update({"role": role}).eq("id", user_id).execute()
    return upd.data[0] if upd.data else None
