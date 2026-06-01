from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


def _fmt_num(n: Optional[int]) -> str:
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _fmt_date(raw) -> str:
    if raw is None:
        return "—"
    if isinstance(raw, date):
        return raw.strftime("%Y-%m-%d")
    if isinstance(raw, str) and len(raw) == 8:
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return str(raw)


def build_caption(
    channel: str,
    title: Optional[str] = None,
    upload_date=None,
    like_count: Optional[int] = None,
    view_count: Optional[int] = None,
    comment_count: Optional[int] = None,
    description: Optional[str] = None,
    url: Optional[str] = None,
) -> str:
    parts = []
    if title:
        t = title[:80] + "…" if len(title) > 80 else title
        parts.append(f"🎬 {t}")
    parts.append(f"📺 {channel}")
    parts.append(f"📅 {_fmt_date(upload_date)}")
    parts.append(f"👁️ {_fmt_num(view_count)}  ❤️ {_fmt_num(like_count)}  💬 {_fmt_num(comment_count)}")
    if description:
        desc = description[:300] + "…" if len(description) > 300 else description
        parts.append(f"💬 {desc}")
    if url:
        parts.append(f"🔗 {url}")
    return "\n".join(parts)


async def send_video(bot: Bot, chat_id: int, path: Path, caption: str) -> bool:
    try:
        with open(path, "rb") as fh:
            await bot.send_video(
                chat_id=chat_id,
                video=fh,
                caption=caption,
                supports_streaming=True,
                read_timeout=120,
                write_timeout=120,
                connect_timeout=30,
            )
        return True
    except TelegramError as exc:
        logger.error("send_video to %s failed: %s", chat_id, exc)
        return False


async def send_document(bot: Bot, chat_id: int, path: Path, caption: str) -> bool:
    try:
        with open(path, "rb") as fh:
            await bot.send_document(
                chat_id=chat_id,
                document=fh,
                filename=path.name,
                caption=caption,
                read_timeout=60,
                write_timeout=60,
            )
        return True
    except TelegramError as exc:
        logger.error("send_document to %s failed: %s", chat_id, exc)
        return False


async def send_text(bot: Bot, chat_id: int, text: str):
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except TelegramError as exc:
        logger.error("send_text to %s failed: %s", chat_id, exc)
