"""Video upload to Supabase Storage, so Instagram's API has a public URL to fetch from."""
import uuid
from app.services.supabase_client import get_supabase

BUCKET = "videos"


def upload_video(file_bytes: bytes, content_type: str, user_id: str) -> str:
    sb = get_supabase()
    filename = f"{user_id}/{uuid.uuid4()}.mp4"
    sb.storage.from_(BUCKET).upload(
        filename, file_bytes, file_options={"content-type": content_type or "video/mp4"}
    )
    return sb.storage.from_(BUCKET).get_public_url(filename)
