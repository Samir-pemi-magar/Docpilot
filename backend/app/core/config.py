from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "DocPilot API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False

    database_url: str

    storage_path: Path = PROJECT_ROOT / "data" / "storage"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # OpenAI-compatible LLM server; configured independently of embeddings.
    llm_base_url: str = "http://127.0.0.1:3000/v1"
    llm_api_key: str | None = None
    llm_model: str = "docpilot-qwen3-4b"
    llm_timeout_seconds: float = 60.0
    llm_thinking_mode: str = "auto"  # auto | always | never
    llm_thinking_timeout_seconds: float = 75.0
    llm_thinking_max_tokens: int = 3000
    llm_max_tokens: int = 700

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()