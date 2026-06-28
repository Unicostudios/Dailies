import asyncio
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routers import scripts, progress, instagram
from app.services.scheduler import run_scheduler_loop
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI(title="ReelStreak API")

class NoCompressionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Encoding"] = "identity"
        return response

app.add_middleware(NoCompressionMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before any real launch
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scripts.router)
app.include_router(progress.router)
app.include_router(instagram.router)


@app.on_event("startup")
async def start_background_scheduler():
    asyncio.create_task(run_scheduler_loop())


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def serve_frontend():
    return FileResponse("frontend.html")
