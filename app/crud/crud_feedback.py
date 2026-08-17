from app.core.supabase_client import supabase

def get_feedback_by_user_and_class(user_id: str, class_id: str):
    sb = supabase()
    existing = (
        sb.table("feedbacks")
        .select("id")
        .eq("user_id", user_id)
        .eq("class_id", class_id)
        .limit(1)
        .execute()
    )
    return existing.data[0] if existing.data else None

def update_feedback(fid: str, text: str, rating: int):
    sb = supabase()
    up = (
        sb.table("feedbacks")
        .update({"text": text, "rating": rating})
        .eq("id", fid)
        .execute()
    )
    return up.data[0] if up.data else None

def create_feedback(user_id: str, class_id: str, text: str, rating: int):
    sb = supabase()
    ins = (
        sb.table("feedbacks")
        .insert({
            "user_id": user_id,
            "class_id": class_id,
            "text": text,
            "rating": rating,
        })
        .execute()
    )
    return ins.data[0] if ins.data else None

def upsert_feedback(user_id: str, class_id: str, text: str, rating: int):
    sb = supabase()
    res = (
        sb.table("feedbacks")
        .upsert({
            "user_id": user_id,
            "class_id": class_id,
            "text": text,
            "rating": rating,
        }, on_conflict="user_id,class_id")
        .execute()
    )
    return res.data[0] if res.data else None

def get_my_feedbacks(user_id: str):
    sb = supabase()
    res = (
        sb.table("feedbacks")
        .select("id, class_id, text, rating, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

def get_admin_feedbacks(class_id: str = ""):
    sb = supabase()
    q = sb.table("feedbacks").select("id, class_id, text, rating, created_at").order("created_at", desc=True)
    if class_id:
        q = q.eq("class_id", class_id)
    res = q.execute()
    return res.data or []

def get_class_titles(cids: list[str]):
    sb = supabase()
    if not cids:
        return {}
    c = sb.table("classes").select("id,title").in_("id", cids).execute()
    return {row["id"]: row.get("title", "") for row in (c.data or [])}

def delete_feedback(fid: str):
    sb = supabase()
    delres = sb.table("feedbacks").delete().eq("id", fid).execute()
    return delres.data if delres.data else None
