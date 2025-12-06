# config.py
from pydantic_settings import BaseSettings
from typing import List
from enum import Enum

class LLMProvider(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    GEMINI = "gemini"
    GROK = "grok"

class Config(BaseSettings):
    LLM_PROVIDER: LLMProvider = LLMProvider.OPENAI
    LLM_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    XAI_API_KEY: str = ""
    DATABASE_URL: str
    GOOGLE_CREDENTIALS_FILE: str = "credentials.json"
    GOOGLE_DRIVE_FOLDER_ID: str
    EMAIL_SMTP_HOST: str | None = None
    EMAIL_SMTP_PORT: int = 587
    EMAIL_USERNAME: str | None = None
    EMAIL_PASSWORD: str | None = None
    EMAIL_FROM: str
    EMAIL_TO: List[str] = []

    class Config:
        env_file = ".env"
        case_sensitive = False