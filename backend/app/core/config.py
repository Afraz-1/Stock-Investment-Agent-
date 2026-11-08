"""Typed application configuration loaded from the environment."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Values that can be overridden with EQUITYIQ_ environment variables."""

    app_name: str = "EquityIQ API"
    app_version: str = "0.1.0"
    debug: bool = False
    database_url: SecretStr | None = Field(default=None, repr=False)

    model_config = SettingsConfigDict(
        env_prefix="EQUITYIQ_",
        env_file=PROJECT_ROOT / ".env",
        extra="ignore",
    )
