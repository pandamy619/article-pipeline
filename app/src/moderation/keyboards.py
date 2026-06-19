"""Инлайн-клавиатура модерации."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.moderation.service import build_callback


def review_keyboard(article_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=build_callback("approve", article_id),
                ),
                InlineKeyboardButton(
                    text="✏️ Править",
                    callback_data=build_callback("edit", article_id),
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=build_callback("reject", article_id),
                ),
            ]
        ]
    )
