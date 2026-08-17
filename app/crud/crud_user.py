from app.core.supabase_client import supabase
from app.core.auth import hash_password

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

def get_all_users():
    sb = supabase()
    res = sb.table("users").select("id, email, full_name, nim, role, created_at").order("created_at", desc=True).execute()
    return res.data or []

def build_search_query(q, search: str):
    if search:
        search_term = f"%{search}%"
        return q.ilike("full_name", search_term)
    return q

def get_paginated_users(limit: int = 20, offset: int = 0, search: str = "", role_filter: str = ""):
    sb = supabase()
    
    def should_query_group(group_roles):
        if not role_filter:
            return True
        return role_filter in group_roles
    
    n_A, n_B, n_C = 0, 0, 0
    
    if should_query_group(["superadmin"]):
        q_A = build_search_query(sb.table("users").select("id", count="exact").eq("role", "superadmin"), search)
        n_A = q_A.limit(1).execute().count or 0
        
    if should_query_group(["admin"]):
        q_B = build_search_query(sb.table("users").select("id", count="exact").eq("role", "admin"), search)
        n_B = q_B.limit(1).execute().count or 0
        
    if should_query_group(["mentor", "peserta"]):
        c_roles = [role_filter] if role_filter else ["mentor", "peserta"]
        q_C = build_search_query(sb.table("users").select("id", count="exact").in_("role", c_roles), search)
        n_C = q_C.limit(1).execute().count or 0
        
    total = n_A + n_B + n_C
    results = []
    end = offset + limit
    
    def fetch_set(role_val, local_offset, local_limit):
        q = sb.table("users").select("id, email, full_name, nim, role, created_at").order("created_at", desc=True)
        q = q.in_("role", role_val) if isinstance(role_val, list) else q.eq("role", role_val)
        q = build_search_query(q, search)
        return q.range(local_offset, local_offset + local_limit - 1).execute().data or []

    start_A = max(0, offset)
    end_A = min(n_A, end)
    if start_A < end_A:
        results.extend(fetch_set("superadmin", start_A, end_A - start_A))
        
    start_B = max(n_A, offset)
    end_B = min(n_A + n_B, end)
    if start_B < end_B:
        results.extend(fetch_set("admin", start_B - n_A, end_B - start_B))
        
    start_C = max(n_A + n_B, offset)
    end_C = min(total, end)
    if start_C < end_C:
        c_roles = [role_filter] if role_filter in ["mentor", "peserta"] else ["mentor", "peserta"]
        results.extend(fetch_set(c_roles, start_C - (n_A + n_B), end_C - start_C))
        
    return total, results

def update_user_role(user_id: str, role: str):
    sb = supabase()
    upd = sb.table("users").update({"role": role}).eq("id", user_id).execute()
    return upd.data[0] if upd.data else None
