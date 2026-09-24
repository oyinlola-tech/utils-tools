from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Utils-tool"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    max_upload_size_mb: int = 100
    # Hard cap on any request body, enforced before it is read into
    # memory (batches may carry several files, hence above the per-file
    # limits).
    max_request_body_mb: int = 250
    upload_directory: str = "storage/uploads"
    processed_directory: str = "storage/processed"
    compressed_directory: str = "storage/compressed"
    temp_directory: str = "storage/temp"
    job_directory: str = "storage/jobs"
    download_directory: str = "storage/downloads"
    job_ttl_minutes: int = 30
    # Public origin used in canonical links, the sitemap and robots.txt.
    public_site_url: str = "https://tools.oyinlola.site"

    max_image_width: int = 8000
    max_image_height: int = 8000
    max_image_pixels: int = 89_478_485

    storage_driver: str = "local"
    blob_read_write_token: str = ""
    # Access mode of the connected Vercel Blob store: "public" or "private"
    blob_access_mode: str = "public"

    rembg_model: str = "silueta"

    blob_store_id: str = ""
    blob_webhook_public_key: str = ""

    rate_limit_max_requests: int = 120
    rate_limit_window_seconds: int = 60

    cors_origins: str = "http://127.0.0.1:8000,http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("storage_driver")
    @classmethod
    def validate_storage_driver(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"local", "vercel"}:
            raise ValueError(
                "STORAGE_DRIVER must be 'local' or 'vercel', "
                f"got '{value}'."
            )
        return normalized

    @field_validator("blob_access_mode")
    @classmethod
    def validate_blob_access_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"public", "private"}:
            raise ValueError(
                "BLOB_ACCESS_MODE must be 'public' or 'private', "
                f"got '{value}'."
            )
        return normalized

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {
            "development",
            "production",
            "test",
        }:
            raise ValueError(
                "APP_ENV must be 'development', 'production' "
                f"or 'test', got '{value}'."
            )
        return normalized

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_directory)

    @property
    def processed_path(self) -> Path:
        return Path(self.processed_directory)

    @property
    def compressed_path(self) -> Path:
        return Path(self.compressed_directory)

    @property
    def temp_path(self) -> Path:
        return Path(self.temp_directory)

    @property
    def job_path(self) -> Path:
        return Path(self.job_directory)

    @property
    def download_path(self) -> Path:
        return Path(self.download_directory)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
