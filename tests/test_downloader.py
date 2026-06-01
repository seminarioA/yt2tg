import pytest
from downloader import normalize_url, build_comments_txt


class TestNormalizeUrl:
    def test_handle(self):
        assert normalize_url("@MrBeast") == "https://www.youtube.com/@MrBeast/videos"

    def test_handle_with_at(self):
        url = normalize_url("@MrBeast")
        assert url.startswith("https://")
        assert "/videos" in url

    def test_full_url_passthrough(self):
        url = "https://www.youtube.com/playlist?list=PLxxx"
        assert normalize_url(url) == url

    def test_channel_url_gets_videos(self):
        url = normalize_url("https://www.youtube.com/@MrBeast")
        assert url.endswith("/videos")

    def test_already_has_videos(self):
        url = "https://www.youtube.com/@MrBeast/videos"
        assert normalize_url(url) == url

    def test_no_at_prefix(self):
        url = normalize_url("MrBeast")
        assert "youtube.com/@MrBeast" in url


class TestBuildCommentsTxt:
    def _make_info(self, comments):
        return {
            "title": "Test Video",
            "channel": "Test Channel",
            "webpage_url": "https://youtube.com/watch?v=test",
            "upload_date": "20250530",
            "view_count": 1000,
            "like_count": 100,
            "comments": comments,
        }

    def test_empty_comments(self):
        txt = build_comments_txt(self._make_info([]))
        assert "Test Video" in txt
        assert "0 totales" in txt

    def test_top_level_comment(self):
        comments = [{
            "id": "c1", "parent": "root", "text": "Great video!",
            "author": "User1", "author_id": "user1",
            "like_count": 50, "timestamp": 1700000000,
            "is_favorited": False, "author_is_uploader": False,
        }]
        txt = build_comments_txt(self._make_info(comments))
        assert "@user1" in txt
        assert "Great video!" in txt
        assert "👍 50" in txt

    def test_reply_indented(self):
        comments = [
            {"id": "c1", "parent": "root", "text": "Parent",
             "author": "User1", "author_id": "u1",
             "like_count": 10, "timestamp": 1700000100,
             "is_favorited": False, "author_is_uploader": False},
            {"id": "c2", "parent": "c1", "text": "Reply here",
             "author": "User2", "author_id": "u2",
             "like_count": 5, "timestamp": 1700000200,
             "is_favorited": False, "author_is_uploader": False},
        ]
        txt = build_comments_txt(self._make_info(comments))
        assert "↳" in txt
        assert "Reply here" in txt

    def test_limit_applied(self):
        comments = [
            {"id": f"c{i}", "parent": "root", "text": f"Comment {i}",
             "author": f"User{i}", "author_id": f"u{i}",
             "like_count": i, "timestamp": 1700000000 + i,
             "is_favorited": False, "author_is_uploader": False}
            for i in range(10)
        ]
        txt = build_comments_txt(self._make_info(comments), limit=3)
        assert "mostrando 3" in txt

    def test_hearted_comment(self):
        comments = [{
            "id": "c1", "parent": "root", "text": "Hearted!",
            "author": "Fan", "author_id": "fan",
            "like_count": 0, "timestamp": 1700000000,
            "is_favorited": True, "author_is_uploader": False,
        }]
        txt = build_comments_txt(self._make_info(comments))
        assert "❤️" in txt

    def test_uploader_badge(self):
        comments = [{
            "id": "c1", "parent": "root", "text": "Creator reply",
            "author": "Creator", "author_id": "creator",
            "like_count": 0, "timestamp": 1700000000,
            "is_favorited": False, "author_is_uploader": True,
        }]
        txt = build_comments_txt(self._make_info(comments))
        assert "📺" in txt
