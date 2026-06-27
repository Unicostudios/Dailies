from typing import Optional
from pydantic import BaseModel


class GenerateScriptRequest(BaseModel):
    topic: str
    tone_override: Optional[str] = None


class ScriptOut(BaseModel):
    id: str
    topic: str
    hook: Optional[str]
    body: Optional[str]
    cta: Optional[str]
    caption: Optional[str]
    status: str


class LogActionRequest(BaseModel):
    script_id: Optional[str] = None


class ReviseScriptRequest(BaseModel):
    instruction: str
