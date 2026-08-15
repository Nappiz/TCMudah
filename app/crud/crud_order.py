from app.core.supabase_client import supabase
from uuid import uuid4

def upload_payment_proof(user_id: str, file_name: str, file_data: bytes, content_type: str):
    sb = supabase()
    ext = (file_name or "").split(".")[-1].lower() or "jpg"
    key = f"{user_id}/{uuid4().hex}.{ext}"
    sb.storage.from_("payments").upload(
        path=key,
        file=file_data,
        file_options={"contentType": content_type, "upsert": "true"},
    )
    pub = sb.storage.from_("payments").get_public_url(key)
    return pub

def get_class_and_package_prices(class_ids: list[str], package_ids: list[str]):
    sb = supabase()
    price_by_id = {}
    if class_ids:
        c_res = sb.table("classes").select("id, price, visible").in_("id", class_ids).execute()
        for row in (c_res.data or []):
            price_by_id[row["id"]] = int(row["price"])
            
    if package_ids:
        p_res = sb.table("packages").select("id, price, visible").in_("id", package_ids).execute()
        for row in (p_res.data or []):
            price_by_id[row["id"]] = int(row["price"])
    return price_by_id

def create_order(user_id: str, items_enriched: list, total: int, proof_url: str, sender_name: str, note: str):
    sb = supabase()
    ins = sb.table("orders").insert({
        "user_id": user_id,
        "items": items_enriched,
        "total": total,
        "status": "pending",
        "proof_url": proof_url,
        "sender_name": sender_name,
        "note": note,
    }).execute()
    return ins.data[0] if ins.data else None

def get_my_orders(user_id: str):
    sb = supabase()
    res = sb.table("orders").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return res.data or []

def get_admin_orders(status: str = ""):
    sb = supabase()
    q = sb.table("orders").select("*, users(full_name, email)").order("created_at", desc=True)
    if status:
        q = q.eq("status", status)
    res = q.execute()
    return res.data or []

def get_item_titles(class_ids: list[str], package_ids: list[str]):
    sb = supabase()
    item_titles = {}
    if class_ids:
        c_res = sb.table("classes").select("id, title").in_("id", class_ids).execute()
        for row in (c_res.data or []):
            item_titles[row["id"]] = row["title"]
    if package_ids:
        p_res = sb.table("packages").select("id, title").in_("id", package_ids).execute()
        for row in (p_res.data or []):
            item_titles[row["id"]] = row["title"]
    return item_titles

def update_order_status(oid: str, status: str):
    sb = supabase()
    sb.table("orders").update({"status": status}).eq("id", oid).execute()
    res = sb.table("orders").select("*, users(full_name, email)").eq("id", oid).execute()
    return res.data[0] if res.data else None
