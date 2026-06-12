"""Application settings, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./routeiq.db"
    anthropic_api_key: str = ""
    routeiq_ai_model: str = "claude-opus-4-7"
    frontend_origin: str = "http://localhost:5173"

    max_request_bytes: int = 64_000  # reject larger request bodies
    nl_rate_per_minute: int = 20  # cap on the AI-backed order endpoint per client

    # Snowflake analytics warehouse (OLAP tier). All five must be set to enable it.
    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_password: str = ""
    snowflake_database: str = ""
    snowflake_warehouse: str = ""
    snowflake_schema: str = "PUBLIC"
    snowflake_role: str = ""

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    @property
    def snowflake_enabled(self) -> bool:
        return all(
            v.strip()
            for v in (
                self.snowflake_account,
                self.snowflake_user,
                self.snowflake_password,
                self.snowflake_database,
                self.snowflake_warehouse,
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
