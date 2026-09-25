from app.core.supabase_client import supabase
from app.crud.crud_batch import get_active_batch_id_cached


CLASS_COLUMNS = "id,title,description,mentor_ids,curriculum_ids,price,base_price_per_meeting,visible,batch_id,created_at,offers:class_offers(id,class_id,meeting_count,list_price,price,is_recommended,visible,sort_order,created_at)"
def _normalize_offers(offers: list[dict], legacy_price: int = 0):
    normalized = [dict(offer) for offer in offers]
    if not normalized:
        normalized = [{
            "meeting_count": 6,
            "list_price": legacy_price,
            "price": legacy_price,
            "is_recommended": True,
            "visible": True,
            "sort_order": 0,
        }]
    if not any(offer.get("is_recommended") for offer in normalized):
        normalized[0]["is_recommended"] = True
    return normalized


def get_public_classes():
    sb = supabase()
    # Find active batch
    active_batch_id = get_active_batch_id_cached()
    
    q = sb.table("classes").select(CLASS_COLUMNS).eq("visible", True).order("created_at", desc=True)
    if active_batch_id:
        q = q.eq("batch_id", active_batch_id)
        
    res = q.execute()
    return res.data or []

def get_all_classes(batch_id: str = None):
    sb = supabase()
    
    if batch_id is None:
        batch_id = get_active_batch_id_cached()
        
    q = sb.table("classes").select(CLASS_COLUMNS).order("created_at", desc=True)
    if batch_id and batch_id != "all":
        q = q.eq("batch_id", batch_id)
        
    res = q.execute()
    return res.data or []

def get_class_by_id(cid: str):
    sb = supabase()
    res = sb.table("classes").select(CLASS_COLUMNS).eq("id", cid).limit(1).execute()
    return res.data[0] if res.data else None

def get_classes_by_ids(cids: list[str]):
    if not cids:
        return []
    sb = supabase()
    res = sb.table("classes").select(CLASS_COLUMNS).in_("id", cids).execute()
    return res.data or []

def create_class(data: dict):
    sb = supabase()
    if "offers" not in data:
        payload = dict(data)
        if not payload.get("batch_id"):
            active_id = get_active_batch_id_cached()
            if active_id:
                payload["batch_id"] = active_id
        ins = sb.table("classes").insert(payload).execute()
        return ins.data[0] if ins.data else None

    payload = dict(data)
    offers = _normalize_offers(payload.pop("offers", []), payload.get("price", 0))
    recommended = next(offer for offer in offers if offer.get("is_recommended"))
    payload["price"] = recommended["price"]
    if not payload.get("batch_id"):
        active_id = get_active_batch_id_cached()
        if active_id:
            payload["batch_id"] = active_id
            
    ins = sb.table("classes").insert(payload).execute()
    if not ins.data:
        return None
    created = ins.data[0]
    try:
        offer_rows = []
        for offer in offers:
            row = {k: v for k, v in offer.items() if k != "id" or v is not None}
            row["class_id"] = created["id"]
            offer_rows.append(row)
        sb.table("class_offers").insert(offer_rows).execute()
    except Exception:
        sb.table("classes").delete().eq("id", created["id"]).execute()
        raise
    return get_class_by_id(created["id"])

def update_class(cid: str, data: dict):
    sb = supabase()
    if "offers" not in data:
        up = sb.table("classes").update(data).eq("id", cid).execute()
        return up.data[0] if up.data else None

    payload = dict(data)
    offers = payload.pop("offers", None)
    if offers is not None:
        offers = _normalize_offers(offers, payload.get("price", 0))
        recommended = next(offer for offer in offers if offer.get("is_recommended"))
        payload["price"] = recommended["price"]

    existing_ids: set[str] = set()
    if offers is not None:
        existing_response = (
            sb.table("class_offers")
            .select("id,class_id")
            .eq("class_id", cid)
            .execute()
        )
        existing_ids = {row["id"] for row in existing_response.data or []}
        supplied_existing_ids = {
            offer["id"] for offer in offers if offer.get("id")
        }
        unknown_ids = supplied_existing_ids - existing_ids
        if unknown_ids:
            raise ValueError("Pilihan pertemuan tidak termasuk dalam kelas ini")
        removed_ids = existing_ids - supplied_existing_ids
        if removed_ids:
            references = (
                sb.table("package_items")
                .select("class_offer_id")
                .in_("class_offer_id", list(removed_ids))
                .limit(1)
                .execute()
            )
            if references.data:
                raise ValueError(
                    "Pilihan pertemuan masih digunakan oleh bundle dan tidak dapat dihapus"
                )

    if payload:
        up = sb.table("classes").update(payload).eq("id", cid).execute()
        if not up.data:
            return None
    elif not get_class_by_id(cid):
        return None

    if offers is not None:
        # Synchronize in one database transaction. Besides preventing partial
        # writes, the RPC temporarily moves changed meeting counts out of the
        # way so values such as 2 and 6 can be swapped safely.
        sb.rpc(
            "admin_sync_class_offers",
            {"p_class_id": cid, "p_offers": offers},
        ).execute()

    return get_class_by_id(cid)

def delete_class(cid: str):
    sb = supabase()
    delres = sb.table("classes").delete().eq("id", cid).execute()
    return delres.data if delres.data else None
