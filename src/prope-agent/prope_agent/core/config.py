"""Configuration for prope-agent.

Reads from environment variables. Defaults to a Mock LLM provider so the
service can run without an API key for development / demo.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderKind(str, Enum):
    OPENAI = "openai"
    MOCK = "mock"


class Settings(BaseSettings):
    """Runtime settings. Override with environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="PROPE_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: ProviderKind = Field(default=ProviderKind.MOCK)
    openai_api_key: Optional[str] = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")
    openai_base_url: Optional[str] = Field(default=None)

    max_optimization_passes: int = Field(default=2, ge=1, le=10)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=64, le=8192)

    # Quality gate thresholds (deterministic; LLM does NOT decide pass/fail).
    token_warning_threshold: float = Field(default=15.0)
    cost_warning_threshold: float = Field(default=15.0)
    min_improvement_threshold: float = Field(default=0.01)

    # Eval dataset size for the local synthetic comparison.
    synthetic_eval_cases: int = Field(default=5, ge=1, le=50)

    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Cached settings accessor."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
