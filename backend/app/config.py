"""Application settings, read from environment variables."""

from __future__ import annotations

import os
from pathlib import Path


class Settings:
    """Minimal env-driven settings object.

    A plain class is enough for the MVP; swap for pydantic-settings once the
    configuration grows.
    """

    def __init__(self) -> None:
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./smart_bins.db")
        self.storage_dir: Path = Path(os.getenv("STORAGE_DIR", "./storage"))
        self.offline_after_hours: float = float(os.getenv("OFFLINE_AFTER_HOURS", "6"))
        self.cv_mode: str = os.getenv("CV_MODE", "heuristic")  # heuristic | stub
        self.max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
        self.cors_origins: list[str] = [
            origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()
        ]


settings = Settings()
