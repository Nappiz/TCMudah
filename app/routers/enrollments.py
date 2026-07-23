from fastapi import APIRouter, Depends, Query
from app.errors.exceptions import BadRequestError, NotFoundError

from app.schemas.schemas import EnrollmentOut, EnrollmentSetIn, EnrollmentPackageIn
from app.core.deps import require_roles, get_current_user
from app.crud import crud_enrollment

router = APIRouter(tags=["enrollments"])

@router.post("/admin/enrollments/set-by-package", response_model=list[EnrollmentOut],
          dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def set_user_enrollments_by_package(payload: EnrollmentPackageIn, current=Depends(get_current_user)):
    target_class_ids = crud_enrollment.get_package_class_ids(payload.package_id)
    if target_class_ids is None:
        raise NotFoundError(detail="Paket tidak ditemukan")
        
    if not target_class_ids:
        raise BadRequestError(detail="Paket ini kosong, tidak ada kelas di dalamnya")

    existing_class_ids = crud_enrollment.get_existing_enrollments(payload.user_id, target_class_ids)
    classes_to_insert = [cid for cid in target_class_ids if cid not in existing_class_ids]

    if classes_to_insert:
        to_insert_data = [
            {
                "user_id": payload.user_id, 
                "class_id": cid, 
                "active": True, 
                "assigned_by": current["id"]
            } 
            for cid in classes_to_insert
        ]
        crud_enrollment.insert_enrollments(to_insert_data)

    if existing_class_ids:
        crud_enrollment.update_enrollments_active(payload.user_id, list(existing_class_ids))

    return crud_enrollment.get_user_enrollments(payload.user_id)

@router.get("/enrollments/me", response_model=list[EnrollmentOut], dependencies=[Depends(get_current_user)])
def my_enrollments(user=Depends(get_current_user)):
    return crud_enrollment.get_active_user_enrollments(user["id"])

@router.post("/admin/enrollments/set", response_model=list[EnrollmentOut],
          dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def set_user_enrollments(payload: EnrollmentSetIn, current=Depends(get_current_user)):
    existing_map = crud_enrollment.get_all_user_enrollments(payload.user_id)
    req_set = set(payload.class_ids)

    to_delete = [row["id"] for cid, row in existing_map.items() if cid not in req_set]
    crud_enrollment.delete_enrollments(to_delete)

    to_insert = [{"user_id": payload.user_id, "class_id": cid, "active": True, "assigned_by": current["id"]} for cid in req_set if cid not in existing_map]
    crud_enrollment.insert_enrollments(to_insert)

    if req_set:
        crud_enrollment.update_enrollments_active(payload.user_id, list(req_set))

    return crud_enrollment.get_user_enrollments(payload.user_id)

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
