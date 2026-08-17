from fastapi import APIRouter, Depends, Query
from app.errors.exceptions import ForbiddenError, NotFoundError

from app.schemas.schemas import FeedbackIn, FeedbackOut, AdminFeedbackOut
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
    response_model=list[AdminFeedbackOut],
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))]
)
def list_feedback_admin(class_id: str = Query("", description="Optional filter: class_id atau kosong untuk semua")):
    fb = crud_feedback.get_admin_feedbacks(class_id)
    cids = list({row["class_id"] for row in fb if row.get("class_id")})
    title_map = crud_feedback.get_class_titles(cids)

    out = []
    for row in fb:
        out.append({
            "id": row["id"],
            "class_id": row["class_id"],
            "text": row["text"],
            "rating": row.get("rating"),
            "created_at": row.get("created_at"),
            "class_title": title_map.get(row["class_id"]),
        })
    return out

@router.delete(
    "/admin/feedback/{fid}",
    dependencies=[Depends(require_roles("admin", "superadmin"))]
)
def delete_feedback_admin(fid: str):
    delres = crud_feedback.delete_feedback(fid)
    if not delres:
        raise NotFoundError(detail="Feedback tidak ditemukan")
    return {"ok": True}
