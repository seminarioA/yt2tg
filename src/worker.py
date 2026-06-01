from __future__ import annotations

import asyncio
import logging
import random
from datetime import date
from typing import Optional

from telegram import Bot

import database as db
import downloader
from sender import build_caption, send_video, send_document, send_text
import config

logger = logging.getLogger(__name__)

_archiving: set[str] = set()


def _akey(account: dict) -> str:
    return f"{account['url']}:{account['chat_id']}"


async def pause_account(account: dict):
    await db.set_paused(account["id"], True)


async def resume_account(account: dict):
    await db.set_paused(account["id"], False)


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if raw and len(raw) == 8:
        try:
            return date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
        except ValueError:
            pass
    return None


def _account_label(account: dict) -> str:
    return account.get("display_name") or account.get("identifier") or str(account["id"])


async def _process_video(bot: Bot, account: dict, url: str, info: dict) -> bool:
    video_id = str(info.get("id", ""))
    if not video_id:
        return False

    chat_id = account["chat_id"]
    upload_date = _parse_date(info.get("upload_date"))
    label = _account_label(account)

    # Metadata JSON
    meta_path = downloader.save_metadata(info, video_id, label)

    await db.add_video(
        video_id=video_id,
        account_id=account["id"],
        url=url,
        title=info.get("title"),
        metadata_path=str(meta_path),
        upload_date=upload_date,
        description=info.get("description"),
        like_count=info.get("like_count"),
        view_count=info.get("view_count"),
        comment_count=info.get("comment_count"),
    )

    # Download video
    video_path = await downloader.download_video(url, video_id)
    if not video_path:
        logger.warning("Could not download %s", url)
        return False

    channel = info.get("channel") or info.get("uploader") or label
    caption = build_caption(
        channel=channel,
        title=info.get("title"),
        upload_date=upload_date,
        like_count=info.get("like_count"),
        view_count=info.get("view_count"),
        comment_count=info.get("comment_count"),
        description=info.get("description"),
        url=info.get("webpage_url") or url,
    )

    sent = await send_video(bot, chat_id, video_path, caption)
    try:
        video_path.unlink(missing_ok=True)
    except Exception:
        pass

    if not sent:
        return False

    # Comments TXT (if enabled and comments were fetched)
    if account["comments_enabled"] and info.get("comments") is not None:
        limit = account.get("comments_limit")
        txt_path = downloader.save_comments_txt(info, video_id, label, limit)
        await send_document(
            bot, chat_id, txt_path,
            caption=f"💬 Comentarios — {info.get('title', video_id)}",
        )

    await db.mark_video_sent(video_id, account["id"])
    return True


async def _iter_new_videos(bot: Bot, account: dict, entries: list[dict]) -> int:
    sent = 0
    for entry in entries:
        # Re-check paused state from DB each iteration
        fresh = await db.get_account_by_id(account["id"])
        if fresh and fresh.get("is_paused"):
            logger.info("Account %s paused — stopping", _account_label(account))
            break

        url = entry.get("webpage_url") or entry.get("url")
        if not url:
            continue

        video_id = str(entry.get("id", ""))
        if video_id and await db.video_was_sent(video_id, account["id"]):
            continue

        # Fetch full info (with comments if enabled)
        info = await downloader.fetch_video_info(
            url,
            with_comments=account["comments_enabled"],
            comment_limit=account.get("comments_limit"),
        )
        if not info:
            continue

        ok = await _process_video(bot, account, url, info)
        if ok:
            sent += 1

        await asyncio.sleep(random.uniform(3, 7))

    return sent


async def archive_account(bot: Bot, account: dict, resuming: bool = False):
    key = _akey(account)
    if key in _archiving:
        logger.warning("Already archiving %s — skipped", _account_label(account))
        return

    _archiving.add(key)
    label = _account_label(account)
    chat_id = account["chat_id"]

    try:
        await send_text(bot, chat_id, f"🔍 Obteniendo videos de {label}…")

        try:
            entries, channel_name = await downloader.fetch_profile_entries(account["url"])
            await db.update_display_name(account["id"], channel_name)
            account = await db.get_account_by_id(account["id"]) or account
        except Exception as exc:
            logger.error("fetch_profile_entries failed for %s: %s", label, exc)
            await send_text(bot, chat_id, f"❌ Error al obtener videos de {label}:\n{exc}")
            return

        total = len(entries)

        if resuming:
            already_sent = await db.get_sent_video_count(account["id"])
            pending = total - already_sent
            await send_text(
                bot, chat_id,
                f"▶️ {label}\n{pending} videos pendientes de {total} totales\n📤 Continuando…",
            )
        else:
            comments_info = ""
            if account["comments_enabled"]:
                lim = account.get("comments_limit")
                comments_info = f"\n💬 Comentarios: {'todos' if not lim else f'top {lim}'}"
            await send_text(
                bot, chat_id,
                f"📦 Canal registrado: {label}\n{total} videos encontrados{comments_info}\n📤 Enviando…",
            )

        sent = await _iter_new_videos(bot, account, list(reversed(entries)))
        await db.update_last_checked(account["id"])

        fresh = await db.get_account_by_id(account["id"])
        if fresh and fresh.get("is_paused"):
            await send_text(
                bot, chat_id,
                f"⏸️ {label} — pausado ({sent} enviados). Usá /resume para continuar.",
            )
        else:
            await send_text(
                bot, chat_id,
                f"✅ {label} — {sent} videos enviados\n🔄 Monitoreando nuevos videos…",
            )

    finally:
        _archiving.discard(key)


async def check_new_videos(bot: Bot, account: dict):
    key = _akey(account)
    if key in _archiving:
        return

    label = _account_label(account)
    logger.info("Polling %s", label)

    try:
        entries, channel_name = await downloader.fetch_profile_entries(account["url"])
        if channel_name:
            await db.update_display_name(account["id"], channel_name)
            account = await db.get_account_by_id(account["id"]) or account
    except Exception as exc:
        logger.error("Polling failed for %s: %s", label, exc)
        return

    sent = await _iter_new_videos(bot, account, entries)
    await db.update_last_checked(account["id"])

    if sent:
        logger.info("Sent %d new video(s) from %s", sent, label)


async def polling_loop(bot: Bot):
    logger.info(
        "Polling loop started (interval %d–%d min)",
        config.POLL_INTERVAL_MIN, config.POLL_INTERVAL_MAX,
    )
    while True:
        for account in await db.get_active_accounts():
            try:
                await check_new_videos(bot, account)
            except Exception as exc:
                logger.error("Unhandled error for %s: %s", _account_label(account), exc)
            await asyncio.sleep(random.uniform(15, 30))

        interval = random.randint(
            config.POLL_INTERVAL_MIN * 60,
            config.POLL_INTERVAL_MAX * 60,
        )
        logger.info("Next poll in %ds", interval)
        await asyncio.sleep(interval)
