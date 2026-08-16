"""Runtime configuration with a deliberately small secret surface."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://patientcapital:patientcapital@localhost:55432/patientcapital"
    )
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    moex_iss_base_url: str = "https://iss.moex.com/iss"
    moex_timeout_seconds: float = Field(default=10.0, gt=0, le=30)
    moex_max_age_seconds: int = Field(default=345_600, gt=0, le=604_800)
    monitor_schedule: str = "06:00,10:00,14:00,18:00"
    monitor_timezone: str = "Europe/Moscow"
    upload_max_bytes: int = Field(default=8_388_608, gt=0, le=20_000_000)
    upload_max_pixels: int = Field(default=20_000_000, gt=0, le=40_000_000)
    ocr_timeout_seconds: float = Field(default=20.0, gt=0, le=60)
    upload_temp_directory: Path = Path("/tmp")
    gigachat_enabled: bool = False
    gigachat_api_key: SecretStr | None = None
    gigachat_client_id: SecretStr | None = None
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat-2"
    gigachat_ca_bundle: Path = Path("certs/russian_trusted_root_ca_pem.crt")
    gigachat_auth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_base_url: str = "https://api.giga.chat/v1"
    gigachat_timeout_seconds: float = Field(default=30.0, gt=0, le=120)

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]
