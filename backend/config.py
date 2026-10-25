from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    GEMINI_API_KEY: str = "your_key_here"
    GEMINI_MODEL: str = "gemini-3.8-flash"
    DATABASE_URL: str = "sqlite:///./skillbridge.db"
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    MAX_QUESTIONS_PER_REQUEST: int = 10
    GENERATION_TEMPERATURE: float = 0.3
    UPLOAD_DIR: str = "./uploads"
    MOCK_GEMINI_ON_MISSING_KEY: bool = True
    VECTOR_STORE: str = "chroma"
    QDRANT_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "skillbridge_materials"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIMENSION: int = 768

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

if os.environ.get("VERCEL") == "1":
    missing_settings = []
    for name in ("DATABASE_URL", "QDRANT_URL", "QDRANT_API_KEY", "GEMINI_API_KEY"):
        if not os.environ.get(name):
            missing_settings.append(name)
    if settings.VECTOR_STORE != "qdrant":
        missing_settings.append("VECTOR_STORE=qdrant")
    if not os.environ.get("BLOB_READ_WRITE_TOKEN") and not os.environ.get("BLOB_STORE_ID"):
        missing_settings.append("BLOB_READ_WRITE_TOKEN or BLOB_STORE_ID")
    if missing_settings:
        raise RuntimeError(
            "Missing required Vercel deployment settings: " + ", ".join(missing_settings)
        )
else:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    if settings.VECTOR_STORE == "chroma":
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
