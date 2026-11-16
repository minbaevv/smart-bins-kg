"""Local image storage. Swap for S3/MinIO by replacing :func:`save_image`."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .config import settings

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_SUFFIX = ".jpg"


def save_image(data: bytes, original_name: str | None) -> tuple[str, Path]:
    """Persist bytes under the storage dir and return (public_url, path)."""
    suffix = Path(original_name or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        suffix = DEFAULT_SUFFIX

    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{suffix}"
    path = settings.storage_dir / filename
    path.write_bytes(data)
    return f"/media/{filename}", path
