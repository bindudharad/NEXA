from functools import lru_cache
from pathlib import Path

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_prefix="NEXA_")

    app_name: str = "Nexa"
    environment: str = "development"
    database_url: str = "sqlite:///./nexa.db"
    log_dir: Path = Path("backend/logs")
    dangerous_actions_require_confirmation: bool = True
    allowed_base_path: Path = Path.home()
    ai_provider: str = "groq"
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    api_key: str | None = None



@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings
