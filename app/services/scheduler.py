"""
Background loop that publishes scheduled Instagram posts when their time arrives.
Runs as an asyncio task inside the same FastAPI process — fine for a personal-scale tool.
"""
import asyncio
from datetime import datetime, timezone
from app.services.supabase_client import get_supabase
from app.services import instagram as ig

CHECK_INTERVAL_SECONDS = 60


async def run_scheduler_loop():
    while True:
        try:
            await _publish_due_posts()
        except Exception as e:
            print(f"[scheduler] error: {e}")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def _publish_due_posts():
    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()
    due = (
        sb.table("scheduled_posts")
        .select("*")
        .eq("status", "pending")
        .lte("scheduled_for", now_iso)
        .execute()
    )
    for post in due.data:
        await _publish_one(sb, post)


async def _publish_one(sb, post: dict):
    post_id = post["id"]
    user_id = post["user_id"]
    sb.table("scheduled_posts").update({"status": "publishing"}).eq("id", post_id).execute()

    account = sb.table("instagram_accounts").select("*").eq("user_id", user_id).execute()
    if not account.data:
        sb.table("scheduled_posts").update({
            "status": "failed", "error": "Instagram account not connected"
        }).eq("id", post_id).execute()
        return

    acct = account.data[0]
    try:
        media_id = await ig.publish_video(
            acct["ig_business_id"], acct["access_token"], post["video_url"], post["caption"]
        )
        sb.table("scheduled_posts").update({
            "status": "published",
            "ig_media_id": media_id,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", post_id).execute()
    except Exception as e:
        sb.table("scheduled_posts").update({"status": "failed", "error": str(e)}).eq("id", post_id).execute()
