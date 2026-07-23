from fastapi import APIRouter, Depends
from app.errors.exceptions import NotFoundError

from app.schemas.schemas import TestimonialIn, TestimonialOut, TestimonialUpdate
from app.core.deps import require_roles
from app.crud import crud_testimonial

router = APIRouter(tags=["testimonials"])

@router.get("/testimonials", response_model=list[TestimonialOut])
def list_testimonials_public():
    return crud_testimonial.get_public_testimonials()

@router.get(
    "/admin/testimonials",
    response_model=list[TestimonialOut],
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def list_testimonials_admin():
    return crud_testimonial.get_all_testimonials()

@router.post(
    "/admin/testimonials",
    response_model=TestimonialOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def create_testimonial(data: TestimonialIn):
    return crud_testimonial.create_testimonial(data.model_dump())

@router.patch(
    "/admin/testimonials/{tid}",
    response_model=TestimonialOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def update_testimonial(tid: str, data: TestimonialUpdate):
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    up = crud_testimonial.update_testimonial(tid, payload)
    if not up:
        raise NotFoundError(detail="Data tidak ditemukan")
    return up

@router.delete(
    "/admin/testimonials/{tid}",
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def delete_testimonial(tid: str):
    delres = crud_testimonial.delete_testimonial(tid)
    if not delres:
        raise NotFoundError(detail="Data tidak ditemukan")
    return {"ok": True}
