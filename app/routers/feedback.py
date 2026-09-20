from fastapi import APIRouter, Depends, Query
from app.errors.exceptions import ForbiddenError, NotFoundError

from app.schemas.schemas import FeedbackIn, FeedbackOut, PaginatedFeedbackOut
from app.core.deps import require_roles, get_current_user
from app.crud import crud_feedback
from app.crud import crud_material # to reuse check_user_enrollment

router = APIRouter(tags=["feedback"])

@router.post("/feedback", response_model=FeedbackOut, dependencies=[Depends(get_current_user)])
def create_or_update_feedback(payload: FeedbackIn, user=Depends(get_current_user)):
    role = (user or {}).get("role", "peserta")
    is_staff = role in ("mentor", "admin", "superadmin")

    if not is_staff:
        has_access = crud_material.check_user_enrollment(user["id"], payload.class_id)
        if not has_access:
            raise ForbiddenError(detail="Tidak punya akses ke kelas ini")

    row = crud_feedback.upsert_feedback(user["id"], payload.class_id, payload.text, payload.rating)

    return {
        "id": row["id"],
        "class_id": row["class_id"],
        "text": row["text"],
        "rating": row.get("rating"),
        "created_at": row.get("created_at"),
    }

@router.get("/feedback/me", response_model=list[FeedbackOut], dependencies=[Depends(get_current_user)])
def my_feedbacks(user=Depends(get_current_user)):
    return crud_feedback.get_my_feedbacks(user["id"])

@router.get(
    "/admin/feedback",
    response_model=PaginatedFeedbackOut,
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))]
)
def list_feedback_admin(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    class_id: str | None = Query(None),
):
    total, data = crud_feedback.get_admin_feedbacks(
        limit=limit,
        offset=(page - 1) * limit,
        class_id=class_id,
    )
    return {"total": total, "data": data}

@router.delete(
    "/admin/feedback/{fid}",
    dependencies=[Depends(require_roles("admin", "superadmin"))]
)
def delete_feedback_admin(fid: str):
    delres = crud_feedback.delete_feedback(fid)
    if not delres:
        raise NotFoundError(detail="Feedback tidak ditemukan")
    return {"ok": True}
