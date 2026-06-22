"""Telegram-бот модерации (aiogram 3): черновики -> кнопки -> публикация."""

from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import settings
from src.db.base import get_session
from src.llm.client import OllamaClient
from src.moderation import service
from src.moderation.keyboards import review_keyboard
from src.pipeline import PipelineResult, run_pipeline
from src.publisher.telegram import publish

router = Router()


class EditState(StatesGroup):
    waiting_text = State()


def _admin_id() -> int:
    return int(settings.admin_user_id)


async def send_drafts(bot: Bot) -> int:
    """Шлёт админу все черновики с кнопками, помечает их pending."""
    sent = 0
    with get_session() as session:
        for rec in service.get_drafts(session):
            await bot.send_message(
                _admin_id(),
                rec.post_text or "(пустой пост)",
                reply_markup=review_keyboard(rec.id),
            )
            service.mark_pending(session, rec.id)
            sent += 1
    return sent


@router.message(Command("review"))
async def cmd_review(message: Message, bot: Bot) -> None:
    if message.from_user and message.from_user.id != _admin_id():
        return
    n = await send_drafts(bot)
    await message.answer(f"На модерацию отправлено: {n}")


@router.callback_query(F.data.startswith(f"{service.CALLBACK_PREFIX}:"))
async def on_action(query: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    parsed = service.parse_callback(query.data or "")
    if not parsed:
        await query.answer("Неизвестное действие")
        return
    action, article_id = parsed

    if action == "reject":
        with get_session() as session:
            service.reject(session, article_id)
        if isinstance(query.message, Message):
            await query.message.edit_reply_markup(reply_markup=None)
        await query.answer("Отклонено ❌")

    elif action == "edit":
        await state.set_state(EditState.waiting_text)
        await state.update_data(article_id=article_id)
        if isinstance(query.message, Message):
            await query.message.answer(
                "Пришли исправленный текст поста одним сообщением."
            )
        await query.answer()

    elif action == "approve":
        with get_session() as session:
            post = service.get_post_text(session, article_id)
            image = service.get_image(session, article_id)
        if not post:
            await query.answer("Пост пуст")
            return
        try:
            message_id = await publish(
                bot, settings.telegram_channel_id, post, image_url=image
            )
        except Exception:
            await query.answer("Ошибка публикации")
            return
        with get_session() as session:
            service.mark_published(session, article_id, message_id)
        if isinstance(query.message, Message):
            await query.message.edit_reply_markup(reply_markup=None)
        await query.answer("Опубликовано ✅")


@router.message(EditState.waiting_text)
async def on_edit_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    article_id = int(data["article_id"])
    await state.clear()
    new_text = message.text or ""
    with get_session() as session:
        service.set_post_text(session, article_id, new_text)
    # по выбору пользователя: после правки — снова показываем кнопки
    await message.answer(new_text, reply_markup=review_keyboard(article_id))


async def _scheduled_run(bot: Bot) -> None:
    """Гоняет пайплайн в отдельном потоке и шлёт новые черновики на модерацию."""

    def _process() -> PipelineResult:
        client = OllamaClient()
        with get_session() as session:
            return run_pipeline(session, client)

    await asyncio.to_thread(_process)
    sent = await send_drafts(bot)
    if sent:
        await bot.send_message(_admin_id(), f"Новых черновиков на модерацию: {sent}")


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp


async def run() -> None:
    bot = Bot(settings.telegram_bot_token)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _scheduled_run,
        "interval",
        minutes=settings.run_interval_minutes,
        args=[bot],
    )
    scheduler.start()
    await build_dispatcher().start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
