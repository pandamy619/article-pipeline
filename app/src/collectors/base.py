"""Единый формат материала из любого источника."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Article:
    title: str
    url: str
    text: str
    source: str
    published_at: datetime | None = None
