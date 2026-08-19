from app.core.supabase_client import supabase

def get_notifications_summary(last_seen_users: str = None, last_seen_feedbacks: str = None):
    sb = supabase()
    
    # Orders pending
    orders_count_res = sb.table("orders").select("id", count="exact").eq("status", "pending").execute()
    new_orders = orders_count_res.count or 0
    
    # New users
    new_users = 0
    if last_seen_users:
        users_count_res = sb.table("users").select("id", count="exact").gt("created_at", last_seen_users).execute()
        new_users = users_count_res.count or 0
        
    # New feedbacks
    new_feedbacks = 0
    if last_seen_feedbacks:
        feedbacks_count_res = sb.table("feedbacks").select("id", count="exact").gt("created_at", last_seen_feedbacks).execute()
        new_feedbacks = feedbacks_count_res.count or 0
        
    return {
        "new_orders": new_orders,
        "new_users": new_users,
        "new_feedbacks": new_feedbacks
    }
