from app.core.supabase_client import supabase
from app.core.rpc import unwrap_rpc_object
from app.crud.crud_batch import get_active_batch_id_cached


PACKAGE_COLUMNS = "id,title,description,class_ids,price,visible,batch_id,created_at,items:package_items(class_id,class_offer_id)"
def _validate_items(items: list[dict]):
    if not items:
        return
    offer_ids = [item["class_offer_id"] for item in items]
    if len(offer_ids) != len(set(offer_ids)):
        raise ValueError("Pilihan kelas dalam bundle tidak boleh duplikat")
    response = (
        supabase()
        .table("class_offers")
        .select("id,class_id")
        .in_("id", offer_ids)
        .execute()
    )
    valid_pairs = {(row["class_id"], row["id"]) for row in response.data or []}
    requested_pairs = {
        (item["class_id"], item["class_offer_id"]) for item in items
    }
    if valid_pairs != requested_pairs:
        raise ValueError("Pilihan pertemuan bundle tidak valid")


def _default_items_for_classes(class_ids: list[str]):
    if not class_ids:
        return []
    response = (
        supabase()
        .table("class_offers")
        .select("id,class_id,is_recommended,sort_order")
        .in_("class_id", class_ids)
        .eq("visible", True)
        .order("sort_order")
        .execute()
    )
    by_class: dict[str, dict] = {}
    for offer in response.data or []:
        current = by_class.get(offer["class_id"])
        if current is None or offer.get("is_recommended"):
            by_class[offer["class_id"]] = offer
    return [
        {"class_id": class_id, "class_offer_id": by_class[class_id]["id"]}
        for class_id in class_ids
        if class_id in by_class
    ]


def get_public_packages():
    sb = supabase()
    # Find active batch
    active_batch_id = get_active_batch_id_cached()
    
    q = sb.table("packages").select(PACKAGE_COLUMNS).eq("visible", True).order("created_at", desc=True)
    if active_batch_id:
        q = q.eq("batch_id", active_batch_id)
        
    res = q.execute()
    return res.data or []

def get_all_packages(batch_id: str = None):
    sb = supabase()
    
    if batch_id is None:
        batch_id = get_active_batch_id_cached()
        
    q = (
        sb.table("packages")
        .select(PACKAGE_COLUMNS)
        .order("created_at", desc=True)
        .is_("archived_at", "null")
    )
    if batch_id and batch_id != "all":
        q = q.eq("batch_id", batch_id)
        
    res = q.execute()
    return res.data or []

def get_package_by_id(pid: str):
    sb = supabase()
    res = sb.table("packages").select(PACKAGE_COLUMNS).eq("id", pid).limit(1).execute()
    return res.data[0] if res.data else None

def get_packages_by_ids(pids: list[str]):
    if not pids:
        return []
    sb = supabase()
    res = sb.table("packages").select(PACKAGE_COLUMNS).in_("id", pids).execute()
    return res.data or []

def create_package(data: dict):
    sb = supabase()
    if "items" not in data:
        payload = dict(data)
        if not payload.get("batch_id"):
            active_id = get_active_batch_id_cached()
            if active_id:
                payload["batch_id"] = active_id
        ins = sb.table("packages").insert(payload).execute()
        return ins.data[0] if ins.data else None

    payload = dict(data)
    items = payload.pop("items", [])
    if items:
        payload["class_ids"] = list(dict.fromkeys(item["class_id"] for item in items))
    else:
        items = _default_items_for_classes(payload.get("class_ids", []))
    _validate_items(items)
    if not payload.get("batch_id"):
        active_id = get_active_batch_id_cached()
        if active_id:
            payload["batch_id"] = active_id
            
    ins = sb.table("packages").insert(payload).execute()
    if not ins.data:
        return None
    created = ins.data[0]
    try:
        if items:
            sb.table("package_items").insert([
                {**item, "package_id": created["id"]} for item in items
            ]).execute()
    except Exception:
        sb.table("packages").delete().eq("id", created["id"]).execute()
        raise
    return get_package_by_id(created["id"])

def update_package(pid: str, data: dict):
    sb = supabase()
    if "items" not in data:
        up = sb.table("packages").update(data).eq("id", pid).execute()
        return up.data[0] if up.data else None

    payload = dict(data)
    items = payload.pop("items", None)
    if items is not None:
        payload["class_ids"] = list(dict.fromkeys(item["class_id"] for item in items))
    elif "class_ids" in payload:
        items = _default_items_for_classes(payload["class_ids"])
    if items is not None:
        _validate_items(items)

    if payload:
        up = sb.table("packages").update(payload).eq("id", pid).execute()
        if not up.data:
            return None
    elif not get_package_by_id(pid):
        return None

    if items is not None:
        existing_response = (
            sb.table("package_items")
            .select("class_id")
            .eq("package_id", pid)
            .execute()
        )
        existing_class_ids = {
            item["class_id"] for item in existing_response.data or []
        }
        selected_class_ids = {item["class_id"] for item in items}
        if items:
            sb.table("package_items").upsert(
                [{**item, "package_id": pid} for item in items],
                on_conflict="package_id,class_id",
            ).execute()
        removed_class_ids = existing_class_ids - selected_class_ids
        if removed_class_ids:
            (
                sb.table("package_items")
                .delete()
                .eq("package_id", pid)
                .in_("class_id", list(removed_class_ids))
                .execute()
            )
    return get_package_by_id(pid)

def delete_package(pid: str):
    response = supabase().rpc("admin_archive_package", {"p_package_id": pid}).execute()
    if response.data is None:
        return None
    return unwrap_rpc_object(response.data, rpc_name="admin_archive_package")
