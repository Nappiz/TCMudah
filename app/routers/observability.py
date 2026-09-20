from fastapi import APIRouter, Depends, Response

from app.core.deps import require_roles
from app.core.telemetry import latency_snapshot


router = APIRouter(prefix="/admin/observability", tags=["observability"])


@router.get(
    "/latency",
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def get_latency_metrics(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {
        "scope": "current-instance",
        "sample_limit_per_route": 1000,
        "routes": latency_snapshot(),
    }

