from fastapi import APIRouter, Depends, HTTPException
from app.services.auth import get_current_user_id
from app.services.supabase_client import get_supabase
from app.services.script_gen import generate_script, revise_script, generate_discover_cards
from app.models.schemas import GenerateScriptRequest, ReviseScriptRequest
import random
from datetime import date

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.post("/generate")
def create_script(body: GenerateScriptRequest, user_id: str = Depends(get_current_user_id)):
    generated = generate_script(body.topic, body.tone_override)
    sb = get_supabase()
    row = (
        sb.table("scripts")
        .insert(
            {
                "user_id": user_id,
                "topic": body.topic,
                "hook": generated.get("hook", ""),
                "body": generated.get("body", ""),
                "cta": generated.get("cta", ""),
                "caption": generated.get("caption", ""),
                "status": "draft",
            }
        )
        .execute()
    ).data[0]
    return row


@router.get("")
def list_scripts(user_id: str = Depends(get_current_user_id)):
    sb = get_supabase()
    res = (
        sb.table("scripts")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


@router.post("/{script_id}/revise")
def revise(script_id: str, body: ReviseScriptRequest, user_id: str = Depends(get_current_user_id)):
    sb = get_supabase()
    existing = (
        sb.table("scripts")
        .select("*")
        .eq("id", script_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="script not found")

    current = existing.data[0]
    revised = revise_script(current, body.instruction)

    updated = (
        sb.table("scripts")
        .update(
            {
                "hook": revised.get("hook", current.get("hook", "")),
                "body": revised.get("body", current.get("body", "")),
                "cta": revised.get("cta", current.get("cta", "")),
                "caption": revised.get("caption", current.get("caption", "")),
            }
        )
        .eq("id", script_id)
        .eq("user_id", user_id)
        .execute()
    ).data[0]
    return updated


@router.patch("/{script_id}/status")
def update_status(script_id: str, status: str, user_id: str = Depends(get_current_user_id)):
    if status not in {"draft", "shot", "posted", "discarded"}:
        raise HTTPException(status_code=400, detail="invalid status")
    sb = get_supabase()
    update = {"status": status}
    if status == "shot":
        update["shot_at"] = "now()"
    if status == "posted":
        update["posted_at"] = "now()"
    res = (
        sb.table("scripts")
        .update(update)
        .eq("id", script_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="script not found")
    return res.data[0]


@router.get("/specimen")
def monthly_specimen(user_id: str = Depends(get_current_user_id)):
    """
    Surfaces one random shot/posted script from this month —
    a small resurfaced artifact rather than a stats summary.
    """
    sb = get_supabase()
    month_start = date.today().replace(day=1).isoformat()
    res = (
        sb.table("scripts")
        .select("*")
        .eq("user_id", user_id)
        .in_("status", ["shot", "posted"])
        .gte("created_at", month_start)
        .execute()
    )
    if not res.data:
        return None
    return random.choice(res.data)


@router.get("/discover")
def discover_cards(category: str = None, include_history: bool = True, user_id: str = Depends(get_current_user_id)):
    """
    Topic cards for swiping — mix of fresh angles on past topics and
    current trending ideas pulled via web search, in the user's voice.
    Optionally filtered to a single category, and optionally excluding
    the user's own history entirely (pure trending, nothing personal).
    """
    past_topics = []
    if include_history:
        sb = get_supabase()
        history = (
            sb.table("scripts")
            .select("topic")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(30)
            .execute()
        )
        past_topics = [row["topic"] for row in history.data]
    cards = generate_discover_cards(past_topics, category, include_history)
    return cards
