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

def update_user_role(user_id: str, role: str):
    sb = supabase()
    upd = sb.table("users").update({"role": role}).eq("id", user_id).execute()
    return upd.data[0] if upd.data else None
