from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user, require_roles
from app.crud import crud_dashboard
from app.errors.exceptions import BadRequestError
from app.schemas.schemas import DashboardOverviewOut

router = APIRouter(prefix="/admin/dashboard", tags=["dashboard"])


@router.get(
    "/overview",
    response_model=DashboardOverviewOut,
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def dashboard_overview(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    days: int = Query(14, ge=1, le=90),
    current=Depends(get_current_user),
):
    if start_date and end_date and start_date > end_date:
        raise BadRequestError(detail="Tanggal awal tidak boleh setelah tanggal akhir")

    start_at = (
        datetime.combine(start_date, time.min, tzinfo=timezone.utc).isoformat()
        if start_date
        else None
    )
    # Exclusive upper bound keeps all records on end_date without timestamp hacks.
    end_at = (
        datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc).isoformat()
        if end_date
        else None
    )

    payload = crud_dashboard.get_dashboard_overview(start_at, end_at, days)
    payload["me"] = {
        "id": current["id"],
        "email": current["email"],
        "full_name": current["full_name"],
        "nim": current.get("nim"),
        "role": current["role"],
    }
    return payload
