from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yt_dlp

import config

logger = logging.getLogger(__name__)


def _common_opts() -> dict:
    opts: dict = {"quiet": True, "no_warnings": True}
    if config.COOKIES_FILE:
        opts["cookiefile"] = config.COOKIES_FILE
    return opts


def normalize_url(identifier: str) -> str:
    """Turn a @handle, channel name or URL into a canonical yt-dlp URL."""
    s = identifier.strip()
    if s.startswith("http"):
        # Playlist URLs stay as-is; channel URLs get /videos appended
        if "playlist" in s or "/videos" in s or "/shorts" in s:
            return s
        # e.g. https://youtube.com/@MrBeast
        return s.rstrip("/") + "/videos"
    if s.startswith("@"):
        return f"https://www.youtube.com/{s}/videos"
    return f"https://www.youtube.com/@{s}/videos"


# ── Profile listing ───────────────────────────────────────────────────────────

def _fetch_entries(url: str) -> tuple[list[dict], str]:
    """Returns (entries, channel_name)."""
    opts = _common_opts() | {"extract_flat": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    name = (
        info.get("channel")
        or info.get("uploader")
        or info.get("title")
        or url
    )
    entries = info.get("entries", [])

    # YouTube channels return nested tabs when using the root URL;
    # /videos already returns a flat list, but handle both just in case.
    if entries and entries[0].get("_type") == "playlist":
        entries = entries[0].get("entries") or []

    return entries, name


async def fetch_profile_entries(url: str) -> tuple[list[dict], str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_entries, url)


# ── Full video metadata ───────────────────────────────────────────────────────

def _fetch_info(url: str, with_comments: bool, comment_limit: Optional[int]) -> Optional[dict]:
    opts = _common_opts()
    if with_comments:
        opts["getcomments"] = True
        opts["extractor_args"] = {
            "youtube": {
                "comment_sort": ["new"],
                **({"max_comments": [str(comment_limit)]} if comment_limit else {}),
            }
        }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:
        logger.error("fetch_info failed for %s: %s", url, exc)
        return None


async def fetch_video_info(
    url: str,
    with_comments: bool = False,
    comment_limit: Optional[int] = None,
) -> Optional[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _fetch_info, url, with_comments, comment_limit
    )


# ── Download ──────────────────────────────────────────────────────────────────

def _download(url: str, video_id: str) -> Optional[Path]:
    out = config.TEMP_DIR / f"{video_id}.%(ext)s"
    opts = _common_opts() | {
        "outtmpl": str(out),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "max_filesize": 49 * 1024 * 1024,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as exc:
        logger.error("download failed for %s: %s", url, exc)
        return None

    result = config.TEMP_DIR / f"{video_id}.mp4"
    return result if result.exists() else None


async def download_video(url: str, video_id: str) -> Optional[Path]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download, url, video_id)


# ── Metadata persistence ──────────────────────────────────────────────────────

def save_metadata(info: dict, video_id: str, account_label: str) -> Path:
    dest = config.METADATA_DIR / account_label
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{video_id}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(info, fh, ensure_ascii=False, indent=2)
    return path


# ── Comments TXT ─────────────────────────────────────────────────────────────

def _fmt_likes(n: Optional[int]) -> str:
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _ts(ts) -> str:
    if ts is None:
        return "—"
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)


def build_comments_txt(info: dict, limit: Optional[int] = None) -> str:
    raw: list[dict] = info.get("comments") or []

    # Split top-level and replies
    top = [c for c in raw if c.get("parent") == "root"]
    top.sort(key=lambda c: c.get("timestamp") or 0, reverse=True)   # newest first
    if limit:
        top = top[:limit]

    reply_map: dict[str, list[dict]] = {}
    for c in raw:
        pid = c.get("parent")
        if pid and pid != "root":
            reply_map.setdefault(pid, []).append(c)
    for lst in reply_map.values():
        lst.sort(key=lambda c: c.get("timestamp") or 0)  # replies oldest first

    upload_raw = info.get("upload_date", "")
    upload_fmt = (
        f"{upload_raw[:4]}-{upload_raw[4:6]}-{upload_raw[6:]}"
        if len(upload_raw) == 8 else upload_raw
    )

    header = [
        f"TÍTULO:    {info.get('title', '')}",
        f"CANAL:     {info.get('channel') or info.get('uploader', '')}",
        f"URL:       {info.get('webpage_url', '')}",
        f"FECHA:     {upload_fmt}",
        f"VISTAS:    {_fmt_likes(info.get('view_count'))}",
        f"LIKES:     {_fmt_likes(info.get('like_count'))}",
        f"COMENTARIOS: {len(raw)} totales / mostrando {len(top)}",
        f"GENERADO:  {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "=" * 72,
        "",
    ]

    body: list[str] = []
    for i, c in enumerate(top, 1):
        handle = f"@{c.get('author_id')}" if c.get("author_id") else c.get("author", "?")
        hearted = " ❤️" if c.get("is_favorited") else ""
        uploader_badge = " 📺" if c.get("author_is_uploader") else ""
        body.append(
            f"[{i}] {handle}{uploader_badge} · 👍 {_fmt_likes(c.get('like_count'))} · {_ts(c.get('timestamp'))}{hearted}"
        )
        # Indent multi-line text
        text = (c.get("text") or "").replace("\n", "\n    ")
        body.append(f"    {text}")
        body.append("")

        for j, r in enumerate(reply_map.get(c.get("id", ""), []), 1):
            r_handle = f"@{r.get('author_id')}" if r.get("author_id") else r.get("author", "?")
            r_hearted = " ❤️" if r.get("is_favorited") else ""
            r_badge = " 📺" if r.get("author_is_uploader") else ""
            body.append(
                f"  ↳ [{i}.{j}] {r_handle}{r_badge} · 👍 {_fmt_likes(r.get('like_count'))} · {_ts(r.get('timestamp'))}{r_hearted}"
            )
            r_text = (r.get("text") or "").replace("\n", "\n       ")
            body.append(f"       {r_text}")
            body.append("")

    body.append("=" * 72)
    return "\n".join(header + body)


def save_comments_txt(info: dict, video_id: str, account_label: str, limit: Optional[int]) -> Path:
    dest = config.COMMENTS_DIR / account_label
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{video_id}.txt"
    txt = build_comments_txt(info, limit)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(txt)
    return path
