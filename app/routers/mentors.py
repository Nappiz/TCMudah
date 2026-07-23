from fastapi import APIRouter, Depends
from app.errors.exceptions import NotFoundError

from app.schemas.schemas import MentorIn, MentorOut, MentorUpdate
from app.core.deps import require_roles
from app.crud import crud_mentor

router = APIRouter(tags=["mentors"])

@router.get("/mentors", response_model=list[MentorOut])
def list_mentors_public():
    return crud_mentor.get_public_mentors()

@router.get(
    "/admin/mentors",
    response_model=list[MentorOut],
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))]
)
def list_mentors_admin():
    return crud_mentor.get_all_mentors()

@router.post(
    "/admin/mentors",
    response_model=MentorOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))]
)
def create_mentor(data: MentorIn):
    return crud_mentor.create_mentor(data.model_dump())

@router.patch(
    "/admin/mentors/{mid}",
    response_model=MentorOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))]
)
def update_mentor(mid: str, data: MentorUpdate):
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    up = crud_mentor.update_mentor(mid, payload)
    if not up:
        raise NotFoundError(detail="Data tidak ditemukan")
    return up

@router.delete(
    "/admin/mentors/{mid}",
    dependencies=[Depends(require_roles("admin", "superadmin"))]
)
def delete_mentor(mid: str):
    delres = crud_mentor.delete_mentor(mid)
    if not delres:
        raise NotFoundError(detail="Data tidak ditemukan")
    return {"ok": True}
