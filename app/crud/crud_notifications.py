from app.core.supabase_client import supabase
from app.core.rpc import unwrap_rpc_object

def get_notifications_summary(last_seen_users: str = None, last_seen_feedbacks: str = None):
    sb = supabase()
    response = sb.rpc(
        "admin_notification_summary",
        {
            "p_last_seen_users": last_seen_users,
            "p_last_seen_feedbacks": last_seen_feedbacks,
        },
    ).execute()
    return unwrap_rpc_object(response.data, rpc_name="admin_notification_summary")
