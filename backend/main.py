import os
import time
import logging
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.database import init_db
from backend.api.routes import router as api_router

# In-memory simple sliding-window rate limiter for generation endpoint
RATE_LIMIT_RECORD = {}
MAX_REQUESTS_PER_MINUTE = 15

app = FastAPI(
    title="SkillBridge AI — Quiz/MCQ Generation Engine",
    version="1.0.0",
    description="Standalone, production-grade Quiz/MCQ Generation module powered by Google Gemini API & Sentence Transformers."
)

import json

logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled request error for %s %s", request.method, request.url.path)
    return Response(
        content=json.dumps({"detail": "Internal server error"}),
        status_code=500,
        media_type="application/json"
    )

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple in-memory rate limiter on /api/quizzes/generate endpoint (15 req/min)."""
    if request.url.path == "/api/quizzes/generate" and request.method == "POST":
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        timestamps = RATE_LIMIT_RECORD.get(client_ip, [])
        # keep timestamps within the last 60 seconds
        timestamps = [t for t in timestamps if now - t < 60]
        if len(timestamps) >= MAX_REQUESTS_PER_MINUTE:
            return Response(
                content='{"detail": "Rate limit exceeded (max 15 generation requests/minute). Please slow down."}',
                status_code=429,
                media_type="application/json"
            )
        timestamps.append(now)
        RATE_LIMIT_RECORD[client_ip] = timestamps

    response = await call_next(request)
    return response

# Initialize Database tables
init_db()

# Include API routes
app.include_router(api_router)

# Mount frontend static directory if exists
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"status": "online", "message": "SkillBridge AI Quiz Generation Engine API is running. Access /docs for API documentation."}

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "gemini_model": settings.GEMINI_MODEL,
        "database": settings.DATABASE_URL.split(":")[0],
        "vector_store": settings.VECTOR_STORE
    }

@app.get("/api/runtime-config")
def runtime_config():
    return {"direct_blob_uploads": os.environ.get("VERCEL") == "1"}
