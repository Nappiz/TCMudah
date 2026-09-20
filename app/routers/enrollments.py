from fastapi import APIRouter, Depends, Query
from app.errors.exceptions import BadRequestError, NotFoundError

from app.schemas.schemas import (
    ActiveClassIdsOut,
    EnrollmentBootstrapOut,
    EnrollmentCandidatesOut,
    EnrollmentOut,
    EnrollmentPackageIn,
    EnrollmentSetIn,
)
from app.core.deps import require_roles, get_current_user
from app.core.rpc import public_rpc_error
from app.crud import crud_enrollment

router = APIRouter(tags=["enrollments"])


@router.get(
    "/admin/enrollments/bootstrap",
    response_model=EnrollmentBootstrapOut,
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def enrollment_bootstrap(
    user_id: str | None = Query(None),
    q: str = Query("", max_length=120),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=512),
):
    try:
        return crud_enrollment.get_enrollment_bootstrap(user_id, q, limit, cursor)
    except ValueError as exc:
        raise BadRequestError(detail=str(exc)) from exc


@router.get(
    "/admin/enrollments/candidates",
    response_model=EnrollmentCandidatesOut,
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def enrollment_candidates(
    q: str = Query("", max_length=120),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=512),
):
    try:
        return crud_enrollment.get_enrollment_candidates(q, limit, cursor)
    except ValueError as exc:
        raise BadRequestError(detail=str(exc)) from exc


@router.get(
    "/admin/enrollments/active-class-ids",
    response_model=ActiveClassIdsOut,
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def enrollment_active_class_ids(user_id: str = Query(...)):
    return {"class_ids": crud_enrollment.get_active_class_ids(user_id)}

@router.post("/admin/enrollments/set-by-package", response_model=list[EnrollmentOut],
          dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def set_user_enrollments_by_package(payload: EnrollmentPackageIn, current=Depends(get_current_user)):
    try:
        return crud_enrollment.set_package_enrollments(
            payload.user_id, payload.package_id, current["id"]
        )
    except Exception as exc:
        message = public_rpc_error(
            exc,
            (
                "Paket tidak ditemukan",
                "Paket ini kosong",
                "Peserta tidak ditemukan",
                "Kelas paket tidak ditemukan",
            ),
        )
        if message:
            raise BadRequestError(detail=message) from exc
        raise

@router.get("/enrollments/me", response_model=list[EnrollmentOut], dependencies=[Depends(get_current_user)])
def my_enrollments(user=Depends(get_current_user)):
    return crud_enrollment.get_active_user_enrollments(user["id"])

@router.post("/admin/enrollments/set", response_model=list[EnrollmentOut],
          dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def set_user_enrollments(payload: EnrollmentSetIn, current=Depends(get_current_user)):
    try:
        return crud_enrollment.set_user_enrollments(
            payload.user_id, payload.class_ids, current["id"]
        )
    except Exception as exc:
        message = public_rpc_error(
            exc, ("Peserta tidak ditemukan", "Kelas tidak ditemukan")
        )
        if message:
            raise BadRequestError(detail=message) from exc
        raise

@router.patch("/admin/enrollments/{eid}/active", response_model=EnrollmentOut,
           dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def toggle_enrollment(eid: str, active: bool = Query(True)):
    up = crud_enrollment.toggle_enrollment_active(eid, active)
    if not up:
        raise NotFoundError(detail="Enrollment tidak ditemukan")
    return up

@router.get("/admin/enrollments", response_model=list[EnrollmentOut],
         dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def admin_list_enrollments(user_id: str = Query(..., description="target user id")):
    return crud_enrollment.get_user_enrollments(user_id)
