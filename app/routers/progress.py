from fastapi import APIRouter, Depends
from app.services.auth import get_current_user_id
from app.services.chapters import log_action, get_chapter_summary, get_day_breakdown
from app.models.schemas import LogActionRequest

router = APIRouter(prefix="/progress", tags=["progress"])


@router.post("/log")
def log(body: LogActionRequest, user_id: str = Depends(get_current_user_id)):
    return log_action(user_id, body.script_id)


@router.get("/chapter")
def chapter_summary(user_id: str = Depends(get_current_user_id)):
    return get_chapter_summary(user_id)


@router.get("/days")
def day_breakdown(user_id: str = Depends(get_current_user_id)):
    """Per-day log for the current month — which days had a shot logged, which didn't."""
    return get_day_breakdown(user_id)
