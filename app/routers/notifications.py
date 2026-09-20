from datetime import datetime

from fastapi import APIRouter, Depends, Query
from app.core.deps import require_roles
from app.crud.crud_notifications import get_notifications_summary
from app.schemas.schemas import NotificationsSummaryOut

router = APIRouter(tags=["notifications"])

@router.get(
    "/admin/notifications/summary",
    response_model=NotificationsSummaryOut,
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def notifications_summary(
    last_seen_users: datetime | None = Query(None),
    last_seen_feedbacks: datetime | None = Query(None)
):
    return get_notifications_summary(
        last_seen_users=last_seen_users.isoformat() if last_seen_users else None,
        last_seen_feedbacks=last_seen_feedbacks.isoformat() if last_seen_feedbacks else None,
    )
