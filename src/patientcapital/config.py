"""Runtime configuration with a deliberately small secret surface."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://patientcapital:patientcapital@localhost:55432/patientcapital"
    )
    api_host: str = "127.0.0.1"
    api_port: int = 8000
