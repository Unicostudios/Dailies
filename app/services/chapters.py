from typing import Optional
import calendar
from datetime import date
from app.services.supabase_client import get_supabase


def _month_label(d: date) -> str:
    return d.strftime("%Y-%m")


def get_or_create_current_chapter(user_id: str) -> dict:
    sb = get_supabase()
    today = date.today()
    label = _month_label(today)
    total_days = calendar.monthrange(today.year, today.month)[1]

    existing = (
        sb.table("chapters")
        .select("*")
        .eq("user_id", user_id)
        .eq("month_label", label)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    created = (
        sb.table("chapters")
        .insert(
            {
                "user_id": user_id,
                "month_label": label,
                "total_days": total_days,
                "completed_days": 0,
                "status": "active",
            }
        )
        .execute()
    )
    return created.data[0]


def log_action(user_id: str, script_id: Optional[str] = None) -> dict:
    """
    Marks today as a completed day in the current chapter.
    Idempotent: logging twice in a day doesn't double count.
    No penalty applied for past missed days — that's the whole point.
    """
    sb = get_supabase()
    today = date.today()
    chapter = get_or_create_current_chapter(user_id)

    existing = (
        sb.table("progress")
        .select("*")
        .eq("user_id", user_id)
        .eq("log_date", today.isoformat())
        .execute()
    )
    if existing.data:
        return {"chapter": chapter, "progress": existing.data[0], "already_logged": True}

    progress_row = (
        sb.table("progress")
        .insert(
            {
                "user_id": user_id,
                "chapter_id": chapter["id"],
                "log_date": today.isoformat(),
                "action_taken": True,
                "script_id": script_id,
            }
        )
        .execute()
    ).data[0]

    new_completed = chapter["completed_days"] + 1
    updated_chapter = (
        sb.table("chapters")
        .update({"completed_days": new_completed})
        .eq("id", chapter["id"])
        .execute()
    ).data[0]

    return {"chapter": updated_chapter, "progress": progress_row, "already_logged": False}


def get_chapter_summary(user_id: str) -> dict:
    chapter = get_or_create_current_chapter(user_id)
    pct = round(100 * chapter["completed_days"] / chapter["total_days"])
    return {**chapter, "completion_pct": pct}


_DEADPAN_LINES = [
    "no script. the app was open in a tab for four hours.",
    "nothing logged. topic was typed, then deleted, then not retyped.",
    "skipped. there was a thought, it left before it was written down.",
    "no entry. the day happened mostly elsewhere.",
    "blank. opened the camera roll instead, twice.",
    "nothing shot. a draft was reread instead of finished.",
    "no log. the topic existed only as a voice note.",
    "skipped without ceremony.",
]


def get_day_breakdown(user_id: str) -> dict:
    """
    Per-day status for the current month: which days have a logged shot,
    and for past days with nothing logged, a flat, deadpan one-liner —
    no guilt, just an observed fact about the gap.
    """
    sb = get_supabase()
    today = date.today()
    chapter = get_or_create_current_chapter(user_id)

    logged = (
        sb.table("progress")
        .select("log_date")
        .eq("user_id", user_id)
        .eq("chapter_id", chapter["id"])
        .execute()
    )
    logged_dates = {row["log_date"] for row in logged.data}

    days = []
    for day_num in range(1, today.day + 1):
        d = date(today.year, today.month, day_num)
        iso = d.isoformat()
        is_logged = iso in logged_dates
        entry = {"day": day_num, "date": iso, "logged": is_logged}
        if not is_logged and d < today:
            entry["note"] = _DEADPAN_LINES[day_num % len(_DEADPAN_LINES)]
        days.append(entry)

    return {"month_label": chapter["month_label"], "days": days}
