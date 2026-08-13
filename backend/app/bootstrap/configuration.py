"""Runtime configuration. No business policy belongs in this module."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    smart_ao_env: str = "development"
    smart_ao_log_level: str = "INFO"
    smart_ao_database_url: str
