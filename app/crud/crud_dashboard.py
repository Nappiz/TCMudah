from app.core.rpc import unwrap_rpc_object
from app.core.supabase_client import supabase


def get_dashboard_overview(
    start_at: str | None = None,
    end_at: str | None = None,
    days: int = 14,
):
    response = supabase().rpc(
        "admin_dashboard_overview",
        {
            "p_start_at": start_at,
            "p_end_at": end_at,
            "p_days": max(1, min(days, 90)),
        },
    ).execute()
    return unwrap_rpc_object(response.data, rpc_name="admin_dashboard_overview")
