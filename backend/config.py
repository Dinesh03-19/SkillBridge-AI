from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    GEMINI_API_KEY: str = "your_key_here"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    DATABASE_URL: str = "sqlite:///./skillbridge.db"
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    MAX_QUESTIONS_PER_REQUEST: int = 10
    GENERATION_TEMPERATURE: float = 0.3
    UPLOAD_DIR: str = "./uploads"
    MOCK_GEMINI_ON_MISSING_KEY: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
