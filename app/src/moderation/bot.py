"""Telegram-бот модерации (aiogram 3): черновики -> кнопки -> публикация."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from src.bot_factory import make_bot
from src.channels.service import ensure_default_channel, get_channel, list_channels
from src.config import settings
from src.db.base import get_session
from src.db.models import ArticleRecord, CollectJob, CollectJobStatus, RunLog
from src.feeds import service as feeds_service
from src.llm.client import OllamaClient
from src.moderation import service
from src.moderation.keyboards import review_keyboard
from src.pipeline import PipelineResult, run_all_channels, run_pipeline
from src.publisher.telegram import publish

router = Router()
log = logging.getLogger(__name__)


class EditState(StatesGroup):
    waiting_text = State()


def _to_admin_id(raw: str) -> int | None:
    return int(raw) if raw and raw.lstrip("-").isdigit() else None


def _admin_id() -> int | None:
    return _to_admin_id(settings.admin_user_id)


def _admin_id_for(channel) -> int | None:
    raw = channel.admin_user_id if channel and channel.admin_user_id else ""
    return _to_admin_id(raw) or _admin_id()


async def _notify_admin(text: str) -> None:
    admin = _admin_id()
    if not admin or not settings.telegram_bot_token:
        return
    bot = make_bot(settings.telegram_bot_token)
    try:
        await bot.send_message(admin, text)
    except Exception:  # noqa: BLE001
        log.exception("notify admin failed")
    finally:
        await bot.session.close()


async def _send_drafts_for(channel_id: int) -> int:
    """Черновики одного канала — его админу через его бота."""
    with get_session() as session:
        ch = get_channel(session, channel_id)
        token = ch.bot_token if ch else ""
        admin = _admin_id_for(ch) if ch else None
    if not token or not admin:
        return 0
    with get_session() as session:
        drafts = [
            (d.id, d.post_text or "(пустой пост)")
            for d in service.get_drafts(session, channel_id=channel_id)
        ]
    if not drafts:
        return 0
    bot = make_bot(token)
    sent = 0
    try:
        for aid, post in drafts:
            await bot.send_message(admin, post, reply_markup=review_keyboard(aid))
            with get_session() as session:
                service.mark_pending(session, aid)
            sent += 1
    finally:
        await bot.session.close()
    return sent


async def send_drafts_all() -> int:
    """Каждому каналу — его черновики его админу через его бота."""
    with get_session() as session:
        channel_ids = [c.id for c in list_channels(session) if c.bot_token]
    sent = 0
    for cid in channel_ids:
        sent += await _send_drafts_for(cid)
    return sent


@router.message(Command("review"))
async def cmd_review(message: Message) -> None:
    if message.from_user and message.from_user.id != _admin_id():
        return
    n = await send_drafts_all()
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
            rec = session.get(ArticleRecord, article_id)
            ch = (
                get_channel(session, rec.channel_id) if rec and rec.channel_id else None
            )
            chat = (
                ch.channel_id if ch and ch.channel_id else settings.telegram_channel_id
            )
        if not post:
            await query.answer("Пост пуст")
            return
        try:
            message_id = await publish(bot, chat, post, image_url=image)
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


def _set_next_collect(channel_id: int, minutes: int | None) -> None:
    """Пишем в БД время следующего планового сбора (подсказка для админки)."""
    with get_session() as session:
        ch = get_channel(session, channel_id)
        if ch:
            ch.next_collect_at = (
                datetime.now(timezone.utc) + timedelta(minutes=minutes)
                if minutes
                else None
            )


async def _run_channel(channel_id: int) -> None:
    """Плановый сбор по одному каналу + рассылка его черновиков на модерацию."""
    # задача только что сработала — следующий запуск примерно через интервал
    minutes = _collect_intervals.get(channel_id)
    if minutes:
        _set_next_collect(channel_id, minutes)

    def _process() -> PipelineResult | None:
        from src.settings_store import apply_overrides

        with get_session() as session:
            apply_overrides(session)
            ch = get_channel(session, channel_id)
            if not ch or not ch.enabled or not ch.collect_enabled:
                return None
            return run_pipeline(session, OllamaClient(), ch)

    try:
        result = await asyncio.to_thread(_process)
    except Exception as exc:  # noqa: BLE001 — мониторинг: логируем и зовём админа
        log.exception("scheduled collect failed for channel %s", channel_id)
        with get_session() as session:
            session.add(RunLog(ok=False, error=str(exc)[:500]))
        await _notify_admin(f"⚠️ Сбор по проекту #{channel_id} упал:\n{exc}")
        return

    if result is None:
        return
    log.info("scheduled collect ok ch=%s: %s", channel_id, result)
    await _send_drafts_for(channel_id)


# чему равен интервал уже заведённой задачи сбора (чтобы не пересоздавать зря)
_collect_intervals: dict[int, int] = {}


async def _sync_collect_jobs(scheduler: AsyncIOScheduler) -> None:
    """Сверяет задачи сбора с таблицей каналов — расписание правится из админки вживую."""
    with get_session() as session:
        wanted = {
            c.id: c.collect_interval_minutes
            for c in list_channels(session)
            if c.enabled and c.collect_enabled and c.collect_interval_minutes > 0
        }
    for cid, minutes in wanted.items():
        if _collect_intervals.get(cid) == minutes:
            continue  # уже заведена с тем же интервалом
        scheduler.add_job(
            _run_channel,
            "interval",
            minutes=minutes,
            args=[cid],
            id=f"collect:{cid}",
            replace_existing=True,
            max_instances=1,  # один прогон проекта за раз — без самоналожения
            coalesce=True,  # пропущенные срабатывания схлопываем в одно
            next_run_time=datetime.now() + timedelta(minutes=minutes),
        )
        _collect_intervals[cid] = minutes
        _set_next_collect(cid, minutes)
        log.info("collect job ch=%s: каждые %s мин", cid, minutes)
    for cid in list(_collect_intervals):
        if cid not in wanted:
            try:
                scheduler.remove_job(f"collect:{cid}")
            except Exception:  # noqa: BLE001 — задачи могло уже не быть
                pass
            _collect_intervals.pop(cid, None)
            _set_next_collect(cid, None)
            log.info("collect job ch=%s снята (выключен автосбор)", cid)


_STALE_RUNNING = timedelta(minutes=30)


async def _drain_collect_jobs() -> None:
    """Бот = воркер: берёт одну очередную задачу ручного сбора и выполняет её."""

    def _claim() -> int | None:
        now = datetime.now(timezone.utc)
        with get_session() as session:
            # подвисшие running (воркер падал в процессе) — отпускаем как error
            stale = session.scalars(
                select(CollectJob).where(
                    CollectJob.status == CollectJobStatus.running,
                    CollectJob.started_at < now - _STALE_RUNNING,
                )
            ).all()
            for j in stale:
                j.status = CollectJobStatus.error
                j.error = "воркер перезапустился во время выполнения"
                j.finished_at = now
            job = session.scalars(
                select(CollectJob)
                .where(CollectJob.status == CollectJobStatus.queued)
                .order_by(CollectJob.created_at)
                .limit(1)
            ).first()
            if not job:
                return None
            job.status = CollectJobStatus.running
            job.started_at = now
            return job.id

    job_id = await asyncio.to_thread(_claim)
    if job_id is None:
        return

    def _process() -> tuple[int | None, dict]:
        from src.settings_store import apply_overrides

        with get_session() as session:
            job = session.get(CollectJob, job_id)
            channel_id = job.channel_id if job else None
            apply_overrides(session)
            if channel_id is not None:
                ch = get_channel(session, channel_id)
                if not ch:
                    raise RuntimeError(f"проект #{channel_id} не найден")
                res = run_pipeline(session, OllamaClient(), ch)
            else:
                res = run_all_channels(session, OllamaClient())
            return channel_id, {
                "collected": res.collected,
                "added": res.added,
                "duplicates": res.duplicates,
                "semantic_duplicates": res.semantic_duplicates,
                "filtered": res.filtered,
                "rejected": res.rejected,
                "drafted": res.drafted,
            }

    channel_id: int | None = None
    summary: dict | None = None
    error: str | None = None
    try:
        channel_id, summary = await asyncio.to_thread(_process)
    except Exception as exc:  # noqa: BLE001 — помечаем задачу error + зовём админа
        log.exception("collect job %s failed", job_id)
        error = str(exc)[:500]

    def _finish() -> None:
        with get_session() as session:
            job = session.get(CollectJob, job_id)
            if not job:
                return
            if error is None:
                job.status = CollectJobStatus.done
                job.result = json.dumps(summary)
            else:
                job.status = CollectJobStatus.error
                job.error = error
            job.finished_at = datetime.now(timezone.utc)

    await asyncio.to_thread(_finish)

    if error is None:
        log.info("collect job %s done: %s", job_id, summary)
        if channel_id is not None:
            await _send_drafts_for(channel_id)
        else:
            await send_drafts_all()
    else:
        with get_session() as session:
            session.add(RunLog(ok=False, error=error))
        await _notify_admin(f"⚠️ Ручной сбор (job {job_id}) упал:\n{error}")


async def _publish_due() -> None:
    """Публикует статьи из очереди, у которых подошло время (через бот канала)."""
    from src.channels.service import get_channel
    from src.publisher.queue import due_article_ids

    with get_session() as session:
        ids = due_article_ids(session)
    if ids:
        log.info("publish-due: %d article(s) ready", len(ids))
    for aid in ids:
        with get_session() as session:
            rec = session.get(ArticleRecord, aid)
            post = rec.post_text if rec else None
            image = rec.image_url if rec else None
            ch = (
                get_channel(session, rec.channel_id) if rec and rec.channel_id else None
            )
            token = ch.bot_token if ch and ch.bot_token else settings.telegram_bot_token
            chat = (
                ch.channel_id if ch and ch.channel_id else settings.telegram_channel_id
            )
        if not post:
            continue
        pub_bot = make_bot(token)
        try:
            mid = await publish(pub_bot, chat, post, image_url=image)
        except Exception:  # noqa: BLE001 — одна статья не должна ронять остальные
            log.exception("scheduled publish failed for article %s", aid)
            continue
        finally:
            await pub_bot.session.close()
        with get_session() as session:
            service.mark_published(session, aid, mid)
        log.info("published scheduled article %s", aid)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp


async def run() -> None:
    with get_session() as session:
        ensure_default_channel(session)
        tokens: list[str] = []
        for c in list_channels(session):
            if c.enabled and c.bot_token and c.bot_token not in tokens:
                tokens.append(c.bot_token)
    if not tokens and settings.telegram_bot_token:
        tokens = [settings.telegram_bot_token]

    scheduler = AsyncIOScheduler()
    # на старте заводим задачи сбора по каждому каналу и дальше синхроним раз в минуту,
    # чтобы правки интервала/автосбора из админки подхватывались без перезапуска
    await _sync_collect_jobs(scheduler)
    scheduler.add_job(_sync_collect_jobs, "interval", minutes=1, args=[scheduler])
    scheduler.add_job(_publish_due, "interval", minutes=1)
    # ручной сбор из админки: разбираем очередь задач каждые 5 c (по одной за раз)
    scheduler.add_job(
        _drain_collect_jobs,
        "interval",
        seconds=5,
        id="collect-drain",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info(
        "scheduler started: per-channel collect (синхр. раз в минуту), "
        "publish-due 1 min, collect-drain 5 s; moderation bots: %d",
        len(tokens),
    )

    if not tokens:
        log.warning("no bot tokens configured — only scheduler runs")
        while True:
            await asyncio.sleep(3600)

    # ретрай: если Telegram/прокси недоступны, не роняем процесс, а пробуем снова
    dp = build_dispatcher()
    while True:
        bots: list[Bot] = []
        try:
            bots = [make_bot(t) for t in tokens]
            await dp.start_polling(*bots)
            break
        except Exception:  # noqa: BLE001 — сеть/Telegram/прокси: ждём и пробуем
            log.exception("polling failed (Telegram/proxy unreachable?); retry in 30s")
            await asyncio.sleep(30)
        finally:
            for b in bots:
                try:
                    await b.session.close()
                except Exception:  # noqa: BLE001
                    pass


if __name__ == "__main__":
    asyncio.run(run())
