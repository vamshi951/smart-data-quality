from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BackendLogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "smart_data_quality.db"
DEFAULT_STORAGE_PATH = Path(__file__).resolve().parents[2] / "data" / "uploads"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Smart Data Quality API"
    log_level: BackendLogLevel = "INFO"
    database_url: str = Field(
        default=f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}",
        validation_alias="DATABASE_URL",
    )
    data_storage_dir: Path = Field(
        default=DEFAULT_STORAGE_PATH,
        validation_alias="DATA_STORAGE_DIR",
    )
    max_upload_size_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    max_csv_rows: int = Field(default=100_000, gt=0)
    max_csv_columns: int = Field(default=1_000, gt=0)
    max_preview_rows: int = Field(default=100, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
