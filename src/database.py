from __future__ import annotations

import asyncpg
from datetime import date
from typing import Optional

import config

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ── Accounts ──────────────────────────────────────────────────────────────────

async def add_account(
    identifier: str,
    url: str,
    chat_id: int,
    comments_enabled: bool = False,
    comments_limit: Optional[int] = None,
) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO accounts (identifier, url, chat_id, comments_enabled, comments_limit)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (url, chat_id) DO UPDATE
          SET is_active = TRUE,
              comments_enabled = EXCLUDED.comments_enabled,
              comments_limit   = EXCLUDED.comments_limit
        RETURNING *
        """,
        identifier, url, chat_id, comments_enabled, comments_limit,
    )
    return dict(row)


async def update_display_name(account_id: int, name: str):
    pool = await get_pool()
    await pool.execute(
        "UPDATE accounts SET display_name = $1 WHERE id = $2", name, account_id
    )


async def remove_account(url: str, chat_id: int) -> bool:
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE accounts SET is_active = FALSE WHERE url = $1 AND chat_id = $2 AND is_active = TRUE",
        url, chat_id,
    )
    return result.split()[-1] != "0"


async def get_active_accounts() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM accounts WHERE is_active = TRUE ORDER BY added_at"
    )
    return [dict(r) for r in rows]


async def get_account_by_url_and_chat(url: str, chat_id: int) -> Optional[dict]:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM accounts WHERE url = $1 AND chat_id = $2", url, chat_id
    )
    return dict(row) if row else None


async def get_account_by_id(account_id: int) -> Optional[dict]:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM accounts WHERE id = $1", account_id)
    return dict(row) if row else None


async def set_paused(account_id: int, paused: bool):
    pool = await get_pool()
    await pool.execute(
        "UPDATE accounts SET is_paused = $1 WHERE id = $2", paused, account_id
    )


async def update_last_checked(account_id: int):
    pool = await get_pool()
    await pool.execute(
        "UPDATE accounts SET last_checked = NOW() WHERE id = $1", account_id
    )


async def get_account_video_count(account_id: int) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT COUNT(*) AS n FROM videos WHERE account_id = $1", account_id
    )
    return row["n"]


async def get_sent_video_count(account_id: int) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT COUNT(*) AS n FROM videos WHERE account_id = $1 AND sent_at IS NOT NULL",
        account_id,
    )
    return row["n"]


async def get_accounts_with_unsent_videos() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT DISTINCT ON (a.id) a.*
        FROM accounts a
        JOIN videos v ON v.account_id = a.id
        WHERE a.is_active = TRUE AND a.is_paused = FALSE AND v.sent_at IS NULL
        ORDER BY a.id, a.added_at
        """
    )
    return [dict(r) for r in rows]


# ── Videos ────────────────────────────────────────────────────────────────────

async def video_was_sent(video_id: str, account_id: int) -> bool:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id FROM videos WHERE video_id = $1 AND account_id = $2 AND sent_at IS NOT NULL",
        video_id, account_id,
    )
    return row is not None


async def add_video(
    *,
    video_id: str,
    account_id: int,
    url: str,
    title: Optional[str] = None,
    metadata_path: Optional[str] = None,
    upload_date: Optional[date] = None,
    description: Optional[str] = None,
    like_count: Optional[int] = None,
    view_count: Optional[int] = None,
    comment_count: Optional[int] = None,
) -> bool:
    pool = await get_pool()
    result = await pool.execute(
        """
        INSERT INTO videos
          (video_id, account_id, url, title, metadata_path, upload_date,
           description, like_count, view_count, comment_count)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        ON CONFLICT (video_id, account_id) DO NOTHING
        """,
        video_id, account_id, url, title, metadata_path, upload_date,
        description, like_count, view_count, comment_count,
    )
    return result.split()[-1] != "0"


async def mark_video_sent(video_id: str, account_id: int):
    pool = await get_pool()
    await pool.execute(
        "UPDATE videos SET sent_at = NOW() WHERE video_id = $1 AND account_id = $2",
        video_id, account_id,
    )


async def reset_account_sent(account_id: int):
    pool = await get_pool()
    await pool.execute(
        "UPDATE videos SET sent_at = NULL WHERE account_id = $1", account_id
    )
