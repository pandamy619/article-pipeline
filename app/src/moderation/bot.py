"""Telegram-бот модерации (aiogram 3): черновики -> кнопки -> публикация."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import settings
from src.db.base import get_session
from src.db.models import RunLog
from src.feeds import service as feeds_service
from src.llm.client import OllamaClient
from src.moderation import service
from src.moderation.keyboards import review_keyboard
from src.pipeline import PipelineResult, run_all_channels
from src.publisher.telegram import publish

router = Router()
log = logging.getLogger(__name__)


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


@router.message(Command("feeds"))
async def cmd_feeds(message: Message) -> None:
    if message.from_user and message.from_user.id != _admin_id():
        return
    with get_session() as session:
        db_feeds = feeds_service.list_feeds(session)
    env_lines = [f"• {u}" for u in settings.rss_feed_list] or ["  (нет)"]
    db_lines = [f"#{f.id} {'✅' if f.enabled else '🚫'} {f.url}" for f in db_feeds] or [
        "  (нет)"
    ]
    await message.answer(
        "📡 Базовые ленты (.env, правятся в файле):\n"
        + "\n".join(env_lines)
        + "\n\n🗂 Ленты в БД (/delfeed <id>):\n"
        + "\n".join(db_lines)
        + "\n\nДобавить: /addfeed <url>"
    )


@router.message(Command("addfeed"))
async def cmd_addfeed(message: Message, command: CommandObject) -> None:
    if message.from_user and message.from_user.id != _admin_id():
        return
    url = (command.args or "").strip()
    if not url:
        await message.answer("Использование: /addfeed <url>")
        return
    with get_session() as session:
        feed = feeds_service.add_feed(session, url)
        reply = f"Добавлено #{feed.id}: {feed.url}" if feed else "Не вышло"
    await message.answer(reply)


@router.message(Command("delfeed"))
async def cmd_delfeed(message: Message, command: CommandObject) -> None:
    if message.from_user and message.from_user.id != _admin_id():
        return
    raw = (command.args or "").strip()
    if not raw.isdigit():
        await message.answer("Использование: /delfeed <id> (id см. в /feeds)")
        return
    with get_session() as session:
        ok = feeds_service.remove_feed(session, int(raw))
    await message.answer("Удалено ✅" if ok else "Лента не найдена")


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
        from src.settings_store import apply_overrides

        with get_session() as session:
            apply_overrides(session)
            return run_all_channels(session, OllamaClient())

    try:
        result = await asyncio.to_thread(_process)
    except Exception as exc:  # noqa: BLE001 — мониторинг: логируем и зовём админа
        log.exception("scheduled run failed")
        with get_session() as session:
            session.add(RunLog(ok=False, error=str(exc)[:500]))
        try:
            await bot.send_message(_admin_id(), f"⚠️ Прогон пайплайна упал:\n{exc}")
        except Exception:  # noqa: BLE001
            log.exception("failed to notify admin about run failure")
        return

    log.info("scheduled run ok: %s", result)
    sent = await send_drafts(bot)
    if sent:
        await bot.send_message(_admin_id(), f"Новых черновиков на модерацию: {sent}")


async def _publish_due(bot: Bot) -> None:
    """Публикует статьи из очереди, у которых подошло время."""
    from src.publisher.queue import due_article_ids

    with get_session() as session:
        ids = due_article_ids(session)
    if ids:
        log.info("publish-due: %d article(s) ready", len(ids))
    for aid in ids:
        with get_session() as session:
            post = service.get_post_text(session, aid)
            image = service.get_image(session, aid)
        if not post:
            continue
        try:
            mid = await publish(
                bot, settings.telegram_channel_id, post, image_url=image
            )
        except Exception:  # noqa: BLE001 — одна статья не должна ронять остальные
            log.exception("scheduled publish failed for article %s", aid)
            continue
        with get_session() as session:
            service.mark_published(session, aid, mid)
        log.info("published scheduled article %s", aid)


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
    scheduler.add_job(_publish_due, "interval", minutes=1, args=[bot])
    scheduler.start()
    log.info(
        "scheduler started: pipeline every %s min, publish-due every 1 min",
        settings.run_interval_minutes,
    )
    await build_dispatcher().start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
