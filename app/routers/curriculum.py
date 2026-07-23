from fastapi import APIRouter, Depends, Query, Path
from app.errors.exceptions import BadRequestError, NotFoundError

from app.schemas.schemas import CurriculumIn, CurriculumOut, CurriculumUpdate
from app.core.deps import require_roles
from app.crud import crud_curriculum

router = APIRouter(prefix="/curriculum", tags=["curriculum"])

@router.get("", response_model=list[CurriculumOut])
def list_curriculum(q: str = Query("", alias="q")):
    return crud_curriculum.get_all_curriculum(q)

@router.post(
    "",
    response_model=CurriculumOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def create_curriculum(data: CurriculumIn):
    exists = crud_curriculum.get_curriculum_by_code(data.code)
    if exists:
        raise BadRequestError(detail="Kode mata kuliah sudah ada")
    
    return crud_curriculum.create_curriculum(data.model_dump())

@router.patch(
    "/{item_id}",
    response_model=CurriculumOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def update_curriculum(item_id: str = Path(...), data: CurriculumUpdate = ...):
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    up = crud_curriculum.update_curriculum(item_id, payload)
    
    if not up:
        raise NotFoundError(detail="Data tidak ditemukan")
    return up

@router.delete(
    "/{item_id}",
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def delete_curriculum(item_id: str):
    delres = crud_curriculum.delete_curriculum(item_id)
    if not delres:
        raise NotFoundError(detail="Data tidak ditemukan")
    return {"ok": True}
