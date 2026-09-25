from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from app.errors.exceptions import (
    BadRequestError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.rpc import public_rpc_error

from app.schemas.schemas import (
    AdminOrderOut,
    CheckoutInfoOut,
    OrderCreateIn,
    OrderOut,
    PaymentUploadIntentIn,
    PaymentUploadIntentOut,
)
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

@router.post(
    "/orders/upload-intent",
    response_model=PaymentUploadIntentOut,
    status_code=201,
)
def create_payment_upload_intent(
    payload: PaymentUploadIntentIn,
    user=Depends(get_current_user),
):
    if payload.size_bytes > settings.PAYMENT_UPLOAD_MAX_BYTES:
        raise BadRequestError(detail="Ukuran bukti pembayaran terlalu besar")
    try:
        return crud_order.create_payment_upload_intent(
            user["id"], payload.content_type, payload.size_bytes
        )
    except Exception as exc:
        message = public_rpc_error(
            exc, ("Bucket bukti pembayaran harus private",)
        )
        if message:
            raise ServiceUnavailableError(detail=message) from exc
        raise

@router.post("/orders", response_model=OrderOut, status_code=201, dependencies=[Depends(get_current_user)])
def create_order(payload: OrderCreateIn, user=Depends(get_current_user)):
    try:
        row = crud_order.create_order_transactional(
            user["id"],
            [item.model_dump() for item in payload.items],
            payload.proof_path,
            payload.sender_name or user["full_name"],
            payload.note,
        )
    except Exception as exc:
        message = public_rpc_error(
            exc,
            (
                "Keranjang kosong",
                "Item order duplikat",
                "Kelas duplikat dengan isi bundle",
                "Format item order tidak valid",
                "Item order tidak valid",
                "Item tidak tersedia",
                "Bukti pembayaran tidak valid atau kedaluwarsa",
                "Bukti pembayaran belum diunggah",
                "Bukti pembayaran tidak sesuai intent",
            ),
        )
        if message:
            raise BadRequestError(detail=message) from exc
        raise

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
def my_orders(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
):
    return crud_order.get_my_orders(user["id"], limit, offset)

@router.get("/admin/orders",
         dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def list_orders_admin(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=120),
    status: str = Query("", pattern="^(|pending|approved|rejected|expired)$")
):
    offset = (page - 1) * limit
    total, orders = crud_order.get_paginated_orders(limit=limit, offset=offset, search=search, status=status)

    return {"total": total, "data": orders}

@router.get(
    "/admin/orders/{oid}/proof",
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def view_payment_proof(oid: str):
    proof_path = crud_order.get_order_proof_path(oid)
    if not proof_path:
        raise NotFoundError(detail="Bukti pembayaran tidak ditemukan")
    signed_url = crud_order.create_payment_proof_read_url(proof_path)
    if not signed_url:
        raise NotFoundError(detail="Bukti pembayaran tidak valid")
    return RedirectResponse(
        signed_url,
        status_code=302,
        headers={
            "Cache-Control": "private, no-store",
            "Referrer-Policy": "no-referrer",
        },
    )

class OrderStatusIn(BaseModel):
    status: Literal["approved", "rejected", "expired"]

@router.patch("/admin/orders/{oid}/status",
           response_model=AdminOrderOut,
           dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def update_order_status(oid: str, data: OrderStatusIn):
    row = crud_order.update_order_status(oid, data.status)
    if not row:
        raise NotFoundError(detail="Order tidak ditemukan")
    return row
