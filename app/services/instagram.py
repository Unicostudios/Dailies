"""
Instagram (Meta Graph API) integration.

Flow:
1. /instagram/connect redirects the user to Facebook's OAuth dialog.
2. Facebook redirects back to /instagram/callback with a short-lived code.
3. We exchange that for a long-lived token, find the user's Facebook Page,
   and the Instagram Business account linked to that page.
4. We store the long-lived token + IG business account id.
5. Scheduled posts are published later by a background loop (see scheduler.py)
   using the Graph API's two-step container -> publish flow.

Setup required (one-time, in Meta's developer dashboard):
- Create an app at developers.facebook.com
- Add the "Instagram Graph API" product
- Add yourself as a Tester/Admin on the app (this skips Meta's App Review
  entirely for personal use — review is only required for public/third-party use)
- Set a valid OAuth redirect URI matching META_REDIRECT_URI below
"""
import os
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

META_APP_ID = os.environ.get("META_APP_ID", "")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
META_REDIRECT_URI = os.environ.get("META_REDIRECT_URI", "")

GRAPH_BASE = "https://graph.facebook.com/v21.0"
OAUTH_DIALOG = "https://www.facebook.com/v21.0/dialog/oauth"

SCOPES = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"


def get_oauth_url(state: str) -> str:
    params = (
        f"client_id={META_APP_ID}"
        f"&redirect_uri={META_REDIRECT_URI}"
        f"&scope={SCOPES}"
        f"&state={state}"
        f"&response_type=code"
    )
    return f"{OAUTH_DIALOG}?{params}"


async def exchange_code_for_token(code: str) -> str:
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "redirect_uri": META_REDIRECT_URI,
                "code": code,
            },
        )
        res.raise_for_status()
        return res.json()["access_token"]


async def get_long_lived_token(short_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "fb_exchange_token": short_token,
            },
        )
        res.raise_for_status()
        data = res.json()
        expires_in = data.get("expires_in", 60 * 24 * 3600)  # default ~60 days
        return {
            "access_token": data["access_token"],
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        }


async def find_instagram_business_account(access_token: str) -> Optional[dict]:
    """Finds the first Facebook Page (and its linked Instagram Business account) the user manages, via their Business Manager."""
    async with httpx.AsyncClient() as client:
        biz_res = await client.get(
            f"{GRAPH_BASE}/me/businesses", params={"access_token": access_token}
        )
        biz_res.raise_for_status()
        businesses = biz_res.json().get("data", [])
        print(f"DEBUG: businesses found = {businesses}")

        for business in businesses:
            business_id = business["id"]
            pages_res = await client.get(
                f"{GRAPH_BASE}/{business_id}/owned_pages",
                params={
                    "fields": "id,name,instagram_business_account{id,username}",
                    "access_token": access_token,
                },
            )
            pages_res.raise_for_status()
            pages = pages_res.json().get("data", [])
            print(f"DEBUG: business_id={business_id} pages found = {pages}")

            for page in pages:
                page_id = page["id"]
                ig_account = page.get("instagram_business_account")
                if ig_account:
                    return {
                        "page_id": page_id,
                        "ig_business_id": ig_account["id"],
                        "ig_username": ig_account.get("username"),
                    }
    return None


async def publish_video(ig_business_id: str, access_token: str, video_url: str, caption: str) -> str:
    """
    Two-step publish: create a media container pointing at a public video URL,
    wait for Instagram to finish processing it, then publish the container.
    Returns the published media id.
    """
    async with httpx.AsyncClient(timeout=120) as client:
        create_res = await client.post(
            f"{GRAPH_BASE}/{ig_business_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": access_token,
            },
        )
        create_res.raise_for_status()
        creation_id = create_res.json()["id"]

        # poll until Instagram finishes processing the video
        import asyncio
        for _ in range(30):  # up to ~5 minutes
            status_res = await client.get(
                f"{GRAPH_BASE}/{creation_id}",
                params={"fields": "status_code", "access_token": access_token},
            )
            status_code = status_res.json().get("status_code")
            if status_code == "FINISHED":
                break
            if status_code == "ERROR":
                raise RuntimeError("Instagram failed to process the video")
            await asyncio.sleep(10)
        else:
            raise RuntimeError("Timed out waiting for Instagram to process the video")

        publish_res = await client.post(
            f"{GRAPH_BASE}/{ig_business_id}/media_publish",
            data={"creation_id": creation_id, "access_token": access_token},
        )
        publish_res.raise_for_status()
        return publish_res.json()["id"]
async def get_account_insights(ig_user_id: str, access_token: str) -> dict:
    """Fetches account-level metrics, time-series insights, and recent media performance."""
    async with httpx.AsyncClient() as client:
        # Account totals
        profile_res = await client.get(
            f"{GRAPH_BASE}/{ig_user_id}",
            params={
                "fields": "followers_count,media_count,username",
                "access_token": access_token,
            },
        )
        profile_res.raise_for_status()
        profile = profile_res.json()

        # Time-series insights (last 30 days, daily)
        insights_res = await client.get(
            f"{GRAPH_BASE}/{ig_user_id}/insights",
            params={
                "metric": "reach",
                "period": "day",
                "metric_type": "total_value",
                "access_token": access_token,
            },
        )
        print("META INSIGHTS ERROR:", insights_res.status_code, insights_res.text)
        insights_res.raise_for_status()
        insights_data = insights_res.json().get("data", [])

        # Recent media + per-post performance
        media_res = await client.get(
            f"{GRAPH_BASE}/{ig_user_id}/media",
            params={
                "fields": "id,caption,media_type,timestamp,permalink,like_count,comments_count",
                "limit": 10,
                "access_token": access_token,
            },
        )
        media_res.raise_for_status()
        media_items = media_res.json().get("data", [])

        return {
            "followers_count": profile.get("followers_count"),
            "media_count": profile.get("media_count"),
            "username": profile.get("username"),
            "trends": insights_data,
            "recent_media": media_items,
        }
