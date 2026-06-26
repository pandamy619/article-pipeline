"""Локальное хранилище картинок постов (загруженных/сгенерированных).

Файлы лежат в settings.media_dir (в проде — отдельный том), отдаются админкой по
префиксу MEDIA_URL_PREFIX. image_url локальной картинки = '/api/media/<file>'.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from src.config import settings

MEDIA_URL_PREFIX = "/api/media/"

_EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
_ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif"}


def media_dir() -> Path:
    p = Path(settings.media_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_local(image_url: str | None) -> bool:
    return bool(image_url) and image_url.startswith(MEDIA_URL_PREFIX)


def local_path(image_url: str) -> Path:
    """Путь к файлу по его image_url (только basename — без обхода каталога)."""
    name = os.path.basename(image_url[len(MEDIA_URL_PREFIX) :])
    return media_dir() / name


def _ext(filename: str, mime: str) -> str:
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower()
    if ext in _ALLOWED_EXT:
        return "jpg" if ext == "jpeg" else ext
    return _EXT_BY_MIME.get((mime or "").lower(), "jpg")


def save_bytes(data: bytes, *, filename: str = "", mime: str = "") -> str:
    """Сохраняет картинку, возвращает её image_url ('/api/media/<file>')."""
    name = f"{uuid.uuid4().hex}.{_ext(filename, mime)}"
    (media_dir() / name).write_bytes(data)
    return MEDIA_URL_PREFIX + name
