"""Application configuration via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local")
    log_level: str = Field(default="INFO")
    allowed_origins: str = Field(default="*")

    azure_openai_endpoint: str = Field(default="")
    azure_openai_realtime_deployment: str = Field(default="gpt-realtime-2")
    azure_openai_realtime_api_version: str = Field(default="2025-04-01-preview")
    azure_openai_realtime_fallback_deployment: str = Field(default="gpt-4o-realtime-preview")
    azure_openai_api_key: str = Field(default="")

    applicationinsights_connection_string: str = Field(default="")

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def use_managed_identity(self) -> bool:
        return not self.azure_openai_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
