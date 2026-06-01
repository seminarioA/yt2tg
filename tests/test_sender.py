from datetime import date
from sender import _fmt_num, _fmt_date, build_caption


class TestFmtNum:
    def test_none(self):          assert _fmt_num(None) == "—"
    def test_zero(self):          assert _fmt_num(0) == "0"
    def test_small(self):         assert _fmt_num(500) == "500"
    def test_thousands(self):     assert _fmt_num(12400) == "12.4K"
    def test_exact_thousand(self):assert _fmt_num(1000) == "1.0K"
    def test_millions(self):      assert _fmt_num(1_500_000) == "1.5M"


class TestFmtDate:
    def test_none(self):          assert _fmt_date(None) == "—"
    def test_ytdlp_string(self):  assert _fmt_date("20250530") == "2025-05-30"
    def test_date_object(self):   assert _fmt_date(date(2025, 5, 30)) == "2025-05-30"
    def test_unknown(self):       assert _fmt_date("unknown") == "unknown"


class TestBuildCaption:
    def test_full(self):
        cap = build_caption(
            channel="MrBeast",
            title="I Gave Away $1,000,000",
            upload_date="20250530",
            like_count=500_000,
            view_count=10_000_000,
            comment_count=25_000,
            description="Amazing video",
            url="https://youtube.com/watch?v=abc",
        )
        assert "🎬 I Gave Away $1,000,000" in cap
        assert "📺 MrBeast" in cap
        assert "📅 2025-05-30" in cap
        assert "👁️ 10.0M" in cap
        assert "❤️ 500.0K" in cap
        assert "💬 25.0K" in cap
        assert "💬 Amazing video" in cap
        assert "🔗 https://youtube.com/watch?v=abc" in cap

    def test_long_title_truncated(self):
        cap = build_caption(channel="X", title="A" * 100)
        assert "…" in cap

    def test_no_description(self):
        cap = build_caption(channel="X")
        assert cap.count("💬") == 1  # only the count line, not description

    def test_long_description_truncated(self):
        cap = build_caption(channel="X", description="D" * 400)
        assert "…" in cap
