from app.core.supabase_client import supabase

def get_public_packages():
    sb = supabase()
    res = (
        sb.table("packages")
        .select("*")
        .eq("visible", True)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

def get_all_packages():
    sb = supabase()
    res = sb.table("packages").select("*").order("created_at", desc=True).execute()
    return res.data or []

def get_package_by_id(pid: str):
    sb = supabase()
    res = sb.table("packages").select("*").eq("id", pid).limit(1).execute()
    return res.data[0] if res.data else None

def get_packages_by_ids(pids: list[str]):
    if not pids:
        return []
    sb = supabase()
    res = sb.table("packages").select("*").in_("id", pids).execute()
    return res.data or []

def create_package(data: dict):
    sb = supabase()
    ins = sb.table("packages").insert(data).execute()
    return ins.data[0] if ins.data else None

def update_package(pid: str, data: dict):
    sb = supabase()
    up = sb.table("packages").update(data).eq("id", pid).execute()
    return up.data[0] if up.data else None

def delete_package(pid: str):
    sb = supabase()
    delres = sb.table("packages").delete().eq("id", pid).execute()
    return delres.data if delres.data else None
