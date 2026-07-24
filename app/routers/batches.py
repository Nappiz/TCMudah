from fastapi import APIRouter, Depends
from app.errors.exceptions import NotFoundError
from app.schemas.schemas import BatchIn, BatchUpdate, BatchOut
from app.core.deps import require_roles
from app.crud import crud_batch

router = APIRouter(tags=["batches"])

@router.get("/batches", response_model=list[BatchOut])
def get_all_batches():
    # Public endpoint to list batches (maybe needed by frontend to filter)
    return crud_batch.get_all_batches()

@router.get("/batches/active", response_model=BatchOut)
def get_active_batch():
    batch = crud_batch.get_active_batch()
    if not batch:
        raise NotFoundError(detail="No active batch found")
    return batch

@router.post("/admin/batches", response_model=BatchOut, dependencies=[Depends(require_roles("superadmin", "admin"))])
def create_batch(payload: BatchIn):
    return crud_batch.create_batch(payload.model_dump())

@router.patch("/admin/batches/{bid}", response_model=BatchOut, dependencies=[Depends(require_roles("superadmin", "admin"))])
def update_batch(bid: str, payload: BatchUpdate):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        batch = crud_batch.get_all_batches() # just a fallback
        return next((b for b in batch if b["id"] == bid), None)
    up = crud_batch.update_batch(bid, data)
    if not up:
        raise NotFoundError(detail="Batch tidak ditemukan")
    return up

@router.delete("/admin/batches/{bid}", dependencies=[Depends(require_roles("superadmin"))])
def delete_batch(bid: str):
    res = crud_batch.delete_batch(bid)
    if not res:
        raise NotFoundError(detail="Batch tidak ditemukan")
    return {"ok": True}
