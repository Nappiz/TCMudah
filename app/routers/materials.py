from fastapi import APIRouter, Depends, Query
from app.errors.exceptions import ForbiddenError, NotFoundError
from app.core.rpc import public_rpc_error

from app.schemas.schemas import MaterialIn, MaterialOut, MaterialUpdate
from app.core.deps import require_roles, get_current_user
from app.crud import crud_material

router = APIRouter(tags=["materials"])

@router.get("/admin/materials", response_model=list[MaterialOut],
         dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def list_materials_admin(class_id: str = Query(...)):
    return crud_material.get_admin_materials(class_id)

@router.post("/admin/materials", response_model=MaterialOut,
          dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def create_material_admin(payload: MaterialIn):
    data_to_insert = payload.model_dump(by_alias=True, exclude_none=True)
    return crud_material.create_material(data_to_insert)

@router.patch("/admin/materials/{mid}", response_model=MaterialOut,
           dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def update_material_admin(mid: str, data: MaterialUpdate):
    payload = data.model_dump(by_alias=True, exclude_none=True)
    if not payload:
        res = crud_material.get_material_by_id(mid)
        if not res:
            raise NotFoundError(detail="Materi tidak ditemukan")
        return res
    up = crud_material.update_material(mid, payload)
    if not up:
        raise NotFoundError(detail="Materi tidak ditemukan")
    return up

@router.delete("/admin/materials/{mid}",
            dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def delete_material_admin(mid: str):
    delres = crud_material.delete_material(mid)
    if not delres:
        raise NotFoundError(detail="Materi tidak ditemukan")
    return {"ok": True}

@router.get("/materials", response_model=list[MaterialOut], dependencies=[Depends(get_current_user)])
def list_materials_user(class_id: str = Query(...), user=Depends(get_current_user)):
    role = (user or {}).get("role", "peserta")
    is_staff = role in ("mentor", "admin", "superadmin")
    try:
        return crud_material.get_authorized_materials(
            user["id"], class_id, is_staff
        )
    except Exception as exc:
        message = public_rpc_error(exc, ("Tidak punya akses ke kelas ini",))
        if message:
            raise ForbiddenError(detail=message) from exc
        raise
