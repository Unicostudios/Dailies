from typing import Optional
import os
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from app.services.auth import get_current_user_id
from app.services.supabase_client import get_supabase
from app.services.storage import upload_video
from app.services import instagram as ig
from pydantic import BaseModel

router = APIRouter(prefix="/instagram", tags=["instagram"])

# short-lived in-memory map of oauth state -> user_id (fine for a single-process personal deployment)
_pending_states = {}


@router.get("/connect")
def connect(user_id: str = Depends(get_current_user_id)):
    state = user_id
    return {"oauth_url": ig.get_oauth_url(state)}


@router.get("/callback")
async def callback(code: str = None, state: str = None, error: str = None):
    if error:
        return HTMLResponse(f"<h3>Instagram connection failed</h3><p>{error}</p>")
    user_id = state
    if not user_id:
        return HTMLResponse("<h3>This connection link expired — go back and try again.</h3>")

    short_token = await ig.exchange_code_for_token(code)
    long_lived = await ig.get_long_lived_token(short_token)
    account = await ig.find_instagram_business_account(long_lived["access_token"])
    if not account:
        return HTMLResponse(
            "<h3>No Instagram Business account found</h3>"
            "<p>Make sure your Instagram is a Business/Creator account linked to a Facebook Page you manage.</p>"
        )

    sb = get_supabase()
    sb.table("instagram_accounts").upsert({
        "user_id": user_id,
        "ig_user_id": account["ig_business_id"],
        "ig_username": account.get("ig_username"),
        "access_token": long_lived["access_token"],
    }, on_conflict="user_id").execute()

    return HTMLResponse(
        "<h3>Instagram connected ✓</h3><p>You can close this tab and go back to Roughcut.</p>"
    )


@router.get("/status")
def status(user_id: str = Depends(get_current_user_id)):
    sb = get_supabase()
    res = sb.table("instagram_accounts").select("ig_username, connected_at").eq("user_id", user_id).execute()
    if not res.data:
        return {"connected": False}
    return {"connected": True, **res.data[0]}


@router.post("/upload-video")
async def upload(file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)):
    contents = await file.read()
    if len(contents) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="video too large (100MB limit)")
    url = upload_video(contents, file.content_type, user_id)
    return {"video_url": url}


class ScheduleRequest(BaseModel):
    caption: str
    video_url: str
    scheduled_for: str  # ISO datetime
    script_id: Optional[str] = None


@router.post("/schedule")
def schedule(body: ScheduleRequest, user_id: str = Depends(get_current_user_id)):
    sb = get_supabase()
    account = sb.table("instagram_accounts").select("id").eq("user_id", user_id).execute()
    if not account.data:
        raise HTTPException(status_code=400, detail="connect your Instagram account first")
    row = sb.table("scheduled_posts").insert({
        "user_id": user_id,
        "script_id": body.script_id,
        "caption": body.caption,
        "video_url": body.video_url,
        "scheduled_for": body.scheduled_for,
        "status": "pending",
    }).execute()
    return row.data[0]


@router.get("/scheduled")
def list_scheduled(user_id: str = Depends(get_current_user_id)):
    sb = get_supabase()
    res = (
        sb.table("scheduled_posts")
        .select("*")
        .eq("user_id", user_id)
        .order("scheduled_for", desc=False)
        .execute()
    )
    return res.data


@router.delete("/scheduled/{post_id}")
def cancel_scheduled(post_id: str, user_id: str = Depends(get_current_user_id)):
    sb = get_supabase()
    res = (
        sb.table("scheduled_posts")
        .update({"status": "canceled"})
        .eq("id", post_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="not found")
    return res.data[0]
@router.get("/insights")
async def insights(user_id: str = Depends(get_current_user_id)):
    sb = get_supabase()
    res = (
        sb.table("instagram_accounts")
        .select("ig_user_id, access_token")
        .eq("user_id", user_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=400, detail="connect your Instagram account first")

    account = res.data[0]
    data = await ig.get_account_insights(account["ig_user_id"], account["access_token"])
    return data