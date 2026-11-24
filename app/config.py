from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["anthropic", "anthropic_vertex", "gemini_vertex"] = "anthropic"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"

    gcp_project: str | None = None
    gcp_region: str = "us-east5"
    vertex_claude_model: str = "claude-sonnet-4-5@20250929"
    vertex_gemini_model: str = "gemini-2.5-pro"

    data_dir: Path = Path("./data")
    agent_max_steps: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()