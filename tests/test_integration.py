"""
Integration tests — hit real YouTube via yt-dlp.

Run locally:
    INTEGRATION_TESTS=1 pytest tests/test_integration.py -v

These are skipped by default in CI unless the INTEGRATION_TESTS env var is set.
If COOKIES_FILE is also set, tests that need authentication will run too.
"""
import os
import sys
import pytest

# ── Skip guard ────────────────────────────────────────────────────────────────

SKIP = not os.getenv("INTEGRATION_TESTS")
SKIP_REASON = "Set INTEGRATION_TESTS=1 to run integration tests"

COOKIES = os.getenv("COOKIES_FILE")
NEEDS_COOKIES = pytest.mark.skipif(not COOKIES, reason="Set COOKIES_FILE=/path/to/cookies.txt")

# ── Known fixtures ────────────────────────────────────────────────────────────
# Small, stable public channel — YouTube's own help channel (few videos, always public)
TEST_CHANNEL_HANDLE = "@YouTubeCreators"
# First video ever uploaded to YouTube — guaranteed to exist
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
TEST_VIDEO_ID = "jNQXAC9IVRw"
TEST_VIDEO_TITLE_FRAGMENT = "zoo"


# ── URL normalization (no network needed) ─────────────────────────────────────

@pytest.mark.skipif(SKIP, reason=SKIP_REASON)
class TestNormalizeIntegration:
    """normalize_url produces URLs that yt-dlp can actually resolve."""

    def test_handle_produces_valid_url(self):
        from downloader import normalize_url
        url = normalize_url("@MrBeast")
        assert "youtube.com" in url
        assert "@MrBeast" in url
        assert url.endswith("/videos")

    def test_http_url_unchanged(self):
        from downloader import normalize_url
        url = "https://www.youtube.com/playlist?list=PLbpi6ZahtOH6Ar_3GPy3workdMiKuZQYC"
        assert normalize_url(url) == url

    def test_handle_without_at(self):
        from downloader import normalize_url
        url = normalize_url("MrBeast")
        assert "@MrBeast" in url


# ── Real network calls ────────────────────────────────────────────────────────

@pytest.mark.skipif(SKIP, reason=SKIP_REASON)
class TestFetchProfileEntries:
    """fetch_profile_entries returns real data from YouTube."""

    @pytest.mark.asyncio
    async def test_returns_entries(self):
        from downloader import fetch_profile_entries, normalize_url
        url = normalize_url(TEST_CHANNEL_HANDLE)
        entries, name = await fetch_profile_entries(url)
        assert isinstance(entries, list)
        assert len(entries) > 0, "Expected at least one video entry"

    @pytest.mark.asyncio
    async def test_returns_channel_name(self):
        from downloader import fetch_profile_entries, normalize_url
        url = normalize_url(TEST_CHANNEL_HANDLE)
        _, name = await fetch_profile_entries(url)
        assert name
        assert isinstance(name, str)
        assert len(name) > 0

    @pytest.mark.asyncio
    async def test_entries_have_ids(self):
        from downloader import fetch_profile_entries, normalize_url
        url = normalize_url(TEST_CHANNEL_HANDLE)
        entries, _ = await fetch_profile_entries(url)
        ids = [e.get("id") for e in entries if e.get("id")]
        assert len(ids) > 0, "Entries should have video IDs"

    @pytest.mark.asyncio
    async def test_entries_have_urls(self):
        from downloader import fetch_profile_entries, normalize_url
        url = normalize_url(TEST_CHANNEL_HANDLE)
        entries, _ = await fetch_profile_entries(url)
        urls = [
            e.get("webpage_url") or e.get("url")
            for e in entries
            if e.get("webpage_url") or e.get("url")
        ]
        assert len(urls) > 0


@pytest.mark.skipif(SKIP, reason=SKIP_REASON)
class TestFetchVideoInfo:
    """fetch_video_info returns metadata for a real video.
    Most videos need cookies on modern YouTube — the first test
    uses a well-known public video that usually works without them.
    """

    @NEEDS_COOKIES
    @pytest.mark.asyncio
    async def test_returns_info(self):
        from downloader import fetch_video_info
        info = await fetch_video_info(TEST_VIDEO_URL)
        assert info is not None, "fetch_video_info returned None — cookies may be needed"

    @NEEDS_COOKIES
    @pytest.mark.asyncio
    async def test_correct_video_id(self):
        from downloader import fetch_video_info
        info = await fetch_video_info(TEST_VIDEO_URL)
        assert info is not None
        assert info.get("id") == TEST_VIDEO_ID

    @NEEDS_COOKIES
    @pytest.mark.asyncio
    async def test_has_title(self):
        from downloader import fetch_video_info
        info = await fetch_video_info(TEST_VIDEO_URL)
        assert info is not None
        title = info.get("title") or ""
        assert TEST_VIDEO_TITLE_FRAGMENT.lower() in title.lower()

    @NEEDS_COOKIES
    @pytest.mark.asyncio
    async def test_has_upload_date(self):
        from downloader import fetch_video_info
        info = await fetch_video_info(TEST_VIDEO_URL)
        assert info is not None
        upload_date = info.get("upload_date", "")
        assert len(upload_date) == 8   # yt-dlp YYYYMMDD format
        assert upload_date.startswith("2005")  # "Me at the zoo" was 2005


@pytest.mark.skipif(SKIP, reason=SKIP_REASON)
class TestFetchVideoComments:
    """fetch_video_info with comments enabled."""

    @NEEDS_COOKIES
    @pytest.mark.asyncio
    async def test_comments_returned(self):
        from downloader import fetch_video_info
        info = await fetch_video_info(TEST_VIDEO_URL, with_comments=True, comment_limit=10)
        assert info is not None
        comments = info.get("comments")
        assert comments is not None, "Expected comments list"
        assert isinstance(comments, list)

    @NEEDS_COOKIES
    @pytest.mark.asyncio
    async def test_comments_have_required_fields(self):
        from downloader import fetch_video_info
        info = await fetch_video_info(TEST_VIDEO_URL, with_comments=True, comment_limit=5)
        assert info is not None
        comments = info.get("comments") or []
        top_level = [c for c in comments if c.get("parent") == "root"]
        assert len(top_level) > 0
        first = top_level[0]
        assert "text" in first
        assert "author" in first or "author_id" in first

    @NEEDS_COOKIES
    @pytest.mark.asyncio
    async def test_comment_limit_respected(self):
        from downloader import fetch_video_info
        info = await fetch_video_info(TEST_VIDEO_URL, with_comments=True, comment_limit=3)
        assert info is not None
        comments = info.get("comments") or []
        top_level = [c for c in comments if c.get("parent") == "root"]
        assert len(top_level) <= 3


@pytest.mark.skipif(SKIP, reason=SKIP_REASON)
class TestCommentsTxtWithRealData:
    """build_comments_txt + save_comments_txt with real YouTube data."""

    @NEEDS_COOKIES
    @pytest.mark.asyncio
    async def test_txt_contains_comments(self, tmp_path):
        import config
        config.COMMENTS_DIR = tmp_path

        from downloader import fetch_video_info, build_comments_txt
        info = await fetch_video_info(TEST_VIDEO_URL, with_comments=True, comment_limit=5)
        assert info is not None

        txt = build_comments_txt(info, limit=5)
        assert "Me at the zoo" in txt or "zoo" in txt.lower()
        assert "👍" in txt
        assert "=" * 10 in txt

    @NEEDS_COOKIES
    @pytest.mark.asyncio
    async def test_txt_file_saved(self, tmp_path):
        import config
        config.COMMENTS_DIR = tmp_path

        from downloader import fetch_video_info, save_comments_txt
        info = await fetch_video_info(TEST_VIDEO_URL, with_comments=True, comment_limit=3)
        assert info is not None

        path = save_comments_txt(info, TEST_VIDEO_ID, "test_channel", limit=3)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100
