"""Remove abandoned private payment proofs whose upload intents have expired."""

from collections import defaultdict
from datetime import datetime, timezone

from app.core.supabase_client import close_supabase_client, supabase


def cleanup_expired_uploads(limit: int = 500) -> int:
    client = supabase()
    response = (
        client.table("payment_upload_intents")
        .select("path,bucket_id")
        .is_("consumed_at", "null")
        .lt("expires_at", datetime.now(timezone.utc).isoformat())
        .limit(max(1, min(limit, 1000)))
        .execute()
    )
    rows = response.data or []
    paths_by_bucket: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        paths_by_bucket[row["bucket_id"]].append(row["path"])

    removed_paths: list[str] = []
    for bucket_id, paths in paths_by_bucket.items():
        client.storage.from_(bucket_id).remove(paths)
        removed_paths.extend(paths)

    if removed_paths:
        (
            client.table("payment_upload_intents")
            .delete()
            .in_("path", removed_paths)
            .execute()
        )
    return len(removed_paths)


if __name__ == "__main__":
    try:
        print(f"Removed {cleanup_expired_uploads()} expired payment upload(s).")
    finally:
        close_supabase_client()
