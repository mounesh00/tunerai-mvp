"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "TunerAI"
    app_env: str = "development"
    app_debug: bool = True
    secret_key: str = Field(default="change-me-in-production-please")
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://tunerai:tunerai_dev_password@localhost:5432/tunerai"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # CORS
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")

    # JWT
    jwt_secret_key: str = Field(default="change-me-jwt-secret-key")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # Storage
    s3_endpoint_url: str | None = None
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "tunerai"
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = False

    # Upload
    max_upload_size_mb: int = 100
    allowed_upload_extensions: str = ".jsonl,.json"

    # Feature flags
    enable_registration: bool = True
    enable_gpu_training: bool = False

    # Logging
    log_level: str = "INFO"
    structured_logging: bool = True

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in ("development", "dev", "local")

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.allowed_upload_extensions.split(",") if ext.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
