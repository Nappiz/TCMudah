from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from app.schemas.schemas import CheckoutInfoOut, OrderCreateIn, OrderOut, AdminOrderOut
from pydantic import BaseModel
from typing import Literal
from app.core.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.crud import crud_order

router = APIRouter(tags=["orders"])
settings = get_settings()

@router.get("/checkout/info", response_model=CheckoutInfoOut, dependencies=[Depends(get_current_user)])
def checkout_info():
    return {
        "bank_name": settings.BANK_NAME,
        "bank_account": settings.BANK_ACCOUNT,
        "bank_holder": settings.BANK_HOLDER,
        "group_link": settings.GROUP_LINK,
    }

@router.post("/orders/upload")
def upload_payment_proof(file: UploadFile = File(...), user=Depends(get_current_user)):
    data = file.file.read()
    pub = crud_order.upload_payment_proof(user["id"], file.filename, data, file.content_type or "image/jpeg")
    return {"url": pub}

@router.post("/orders", response_model=OrderOut, status_code=201, dependencies=[Depends(get_current_user)])
def create_order(payload: OrderCreateIn, user=Depends(get_current_user)):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Keranjang kosong")

    class_ids = [it.item_id for it in payload.items if it.item_type == "class"]
    package_ids = [it.item_id for it in payload.items if it.item_type == "package"]
    
    price_by_id = crud_order.get_class_and_package_prices(class_ids, package_ids)

    missing = [it.item_id for it in payload.items if it.item_id not in price_by_id]
    if missing:
        raise HTTPException(status_code=400, detail=f"Item tidak ditemukan: {', '.join(missing)}")

    items_enriched = []
    total = 0
    for it in payload.items:
        price = price_by_id[it.item_id]
        items_enriched.append({
            "item_id": it.item_id, 
            "item_type": it.item_type,
            "qty": it.qty, 
            "price": price
        })
        total += price * it.qty

    row = crud_order.create_order(
        user["id"], items_enriched, total, payload.proof_url, user["full_name"], payload.note
    )

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "items": row["items"],
        "total": row["total"],
        "status": row["status"],
        "proof_url": row.get("proof_url"),
        "sender_name": row.get("sender_name"),
        "note": row.get("note"),
        "created_at": row.get("created_at"),
    }

@router.get("/orders/me", response_model=list[OrderOut], dependencies=[Depends(get_current_user)])
def my_orders(user=Depends(get_current_user)):
    return crud_order.get_my_orders(user["id"])

@router.get("/admin/orders",
         response_model=list[AdminOrderOut],
         dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def list_orders_admin(status: str = Query("", description="optional filter: pending/approved/rejected/expired")):
    orders = crud_order.get_admin_orders(status)

    uids = list({o["user_id"] for o in orders if o.get("user_id")})
    users_map = crud_order.get_users_by_ids(uids)

    item_ids = set()
    for o in orders:
        for it in o.get("items", []):
            iid = it.get("item_id") or it.get("class_id")
            if iid:
                item_ids.add(iid)
                
    item_titles = crud_order.get_item_titles(list(item_ids))

    out = []
    for o in orders:
        u = users_map.get(o["user_id"], {})
        
        enriched_items = []
        for it in o.get("items", []):
            new_it = it.copy()
            iid = it.get("item_id") or it.get("class_id")
            if iid:
                new_it["item_title"] = item_titles.get(iid, "Unknown Item")
            enriched_items.append(new_it)

        out.append({
            "id": o["id"],
            "user_id": o["user_id"],
            "items": enriched_items,
            "total": o.get("total", 0),
            "status": o.get("status", "pending"),
            "proof_url": o.get("proof_url"),
            "sender_name": o.get("sender_name"),
            "note": o.get("note"),
            "created_at": o.get("created_at"),
            "user_name": u.get("full_name"),
            "user_email": u.get("email"),
        })
    return out

class OrderStatusIn(BaseModel):
    status: Literal["approved", "rejected", "expired"]

@router.patch("/admin/orders/{oid}/status",
           response_model=AdminOrderOut,
           dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def update_order_status(oid: str, data: OrderStatusIn):
    row = crud_order.update_order_status(oid, data.status)
    if not row:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")

    u = crud_order.get_user_brief(row.get("user_id")) if row.get("user_id") else None

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "items": row.get("items", []),
        "total": row.get("total", 0),
        "status": row.get("status", "pending"),
        "proof_url": row.get("proof_url"),
        "sender_name": row.get("sender_name"),
        "note": row.get("note"),
        "created_at": row.get("created_at"),
        "user_name": (u or {}).get("full_name"),
        "user_email": (u or {}).get("email"),
    }
