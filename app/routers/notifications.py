from fastapi import APIRouter, Depends, Query
from app.core.deps import get_current_user, require_roles
from app.crud.crud_notifications import get_notifications_summary

router = APIRouter(tags=["notifications"])

@router.get("/admin/notifications/summary", dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def notifications_summary(
    last_seen_users: str | None = Query(None),
    last_seen_feedbacks: str | None = Query(None)
):
    return get_notifications_summary(
        last_seen_users=last_seen_users,
        last_seen_feedbacks=last_seen_feedbacks
    )
