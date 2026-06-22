"""Публикация поста в Telegram-канал (с картинкой, если есть)."""

from __future__ import annotations

from typing import Protocol

TELEGRAM_LIMIT = 4096
CAPTION_LIMIT = 1024  # лимит подписи под фото в Telegram


class Sender(Protocol):
    async def send_message(self, chat_id: int | str, text: str): ...
    async def send_photo(self, chat_id: int | str, photo: str, caption: str): ...


def resolve_chat_id(value: int | str) -> int | str:
    """Числовой id (в т.ч. -100…) -> int, иначе оставляем как есть (@username)."""
    if isinstance(value, int):
        return value
    v = value.strip()
    return int(v) if v.lstrip("-").isdigit() else v


def split_text(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Режет длинный текст на части <= limit по переносам/пробелам."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return chunks


async def publish(
    bot: Sender, chat_id: int | str, text: str, image_url: str | None = None
) -> int | None:
    """Шлёт пост в канал. Если есть картинка и пост влезает в подпись — фото с
    подписью; иначе текстом (длинный — частями). Возвращает message_id первой части.
    """
    target = resolve_chat_id(chat_id)

    if image_url and len(text) <= CAPTION_LIMIT:
        try:
            msg = await bot.send_photo(target, image_url, caption=text)
            return getattr(msg, "message_id", None)
        except Exception:  # noqa: BLE001 — картинка не зашла, шлём текстом
            pass

    first_id: int | None = None
    for part in split_text(text):
        msg = await bot.send_message(target, part)
        if first_id is None:
            first_id = getattr(msg, "message_id", None)
    return first_id
