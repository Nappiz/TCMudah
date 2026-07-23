from fastapi import APIRouter, Depends, HTTPException
from app.schemas.schemas import ClassIn, ClassOut, ClassUpdate
from app.core.deps import require_roles
from app.crud import crud_class

router = APIRouter(tags=["classes"])

@router.get("/classes", response_model=list[ClassOut])
def list_classes_public():
    return crud_class.get_public_classes()

@router.get(
    "/admin/classes",
    response_model=list[ClassOut],
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))]
)
def list_classes_admin():
    return crud_class.get_all_classes()

@router.get(
    "/admin/classes/{cid}",
    response_model=ClassOut,
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))]
)
def get_class_admin(cid: str):
    data = crud_class.get_class_by_id(cid)
    if not data:
        raise HTTPException(status_code=404, detail="Kelas tidak ditemukan")
    return data

@router.post(
    "/admin/classes",
    response_model=ClassOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))]
)
def create_class(data: ClassIn):
    return crud_class.create_class(data.model_dump())

@router.patch(
    "/admin/classes/{cid}",
    response_model=ClassOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))]
)
def update_class(cid: str, data: ClassUpdate):
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    up = crud_class.update_class(cid, payload)
    if not up:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return up

@router.delete(
    "/admin/classes/{cid}",
    dependencies=[Depends(require_roles("admin", "superadmin"))]
)
def delete_class(cid: str):
    delres = crud_class.delete_class(cid)
    if not delres:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return {"ok": True}
