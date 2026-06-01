from unittest.mock import AsyncMock, patch
import pytest
import database


def pool(fetchrow=None, execute="UPDATE 1", fetch=None):
    p = AsyncMock()
    p.fetchrow = AsyncMock(return_value=fetchrow)
    p.fetch    = AsyncMock(return_value=fetch or [])
    p.execute  = AsyncMock(return_value=execute)
    return p


@pytest.mark.asyncio
async def test_add_account():
    row = {"id": 1, "identifier": "@MrBeast", "url": "https://youtube.com/@MrBeast/videos",
           "chat_id": 42, "comments_enabled": False, "comments_limit": None,
           "is_active": True, "is_paused": False, "added_at": None,
           "last_checked": None, "display_name": None}
    p = pool(fetchrow=row)
    with patch("database.get_pool", return_value=p):
        result = await database.add_account("@MrBeast", "https://youtube.com/@MrBeast/videos", 42)
    assert result["identifier"] == "@MrBeast"


@pytest.mark.asyncio
async def test_add_account_with_comments():
    row = {"id": 2, "identifier": "@MrBeast", "url": "https://youtube.com/@MrBeast/videos",
           "chat_id": 42, "comments_enabled": True, "comments_limit": 500,
           "is_active": True, "is_paused": False, "added_at": None,
           "last_checked": None, "display_name": None}
    p = pool(fetchrow=row)
    with patch("database.get_pool", return_value=p):
        result = await database.add_account("@MrBeast", "https://youtube.com/@MrBeast/videos",
                                            42, comments_enabled=True, comments_limit=500)
    assert result["comments_enabled"] is True
    assert result["comments_limit"] == 500


@pytest.mark.asyncio
async def test_video_was_sent_true():
    p = pool(fetchrow={"id": 5})
    with patch("database.get_pool", return_value=p):
        assert await database.video_was_sent("vid123", 1) is True


@pytest.mark.asyncio
async def test_video_was_sent_false():
    p = pool(fetchrow=None)
    with patch("database.get_pool", return_value=p):
        assert await database.video_was_sent("vid123", 1) is False


@pytest.mark.asyncio
async def test_remove_account_found():
    p = pool(execute="UPDATE 1")
    with patch("database.get_pool", return_value=p):
        assert await database.remove_account("https://youtube.com/@X/videos", 42) is True


@pytest.mark.asyncio
async def test_remove_account_not_found():
    p = pool(execute="UPDATE 0")
    with patch("database.get_pool", return_value=p):
        assert await database.remove_account("https://youtube.com/@X/videos", 42) is False


@pytest.mark.asyncio
async def test_get_active_accounts_empty():
    p = pool(fetch=[])
    with patch("database.get_pool", return_value=p):
        assert await database.get_active_accounts() == []


@pytest.mark.asyncio
async def test_mark_video_sent():
    p = pool()
    with patch("database.get_pool", return_value=p):
        await database.mark_video_sent("vid1", 3)
    sql = p.execute.call_args[0][0]
    assert "sent_at" in sql


@pytest.mark.asyncio
async def test_reset_account_sent():
    p = pool()
    with patch("database.get_pool", return_value=p):
        await database.reset_account_sent(5)
    sql = p.execute.call_args[0][0]
    assert "sent_at = NULL" in sql


@pytest.mark.asyncio
async def test_set_paused():
    p = pool()
    with patch("database.get_pool", return_value=p):
        await database.set_paused(3, True)
    args = p.execute.call_args[0]
    assert True in args
    assert 3 in args
