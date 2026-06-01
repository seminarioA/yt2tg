from bot import _parse_add_args


class TestParseAddArgs:
    def test_just_handle(self):
        identifier, comments, limit = _parse_add_args(["@MrBeast"])
        assert identifier == "@MrBeast"
        assert comments is False
        assert limit is None

    def test_url(self):
        identifier, comments, limit = _parse_add_args(["https://youtube.com/@MrBeast"])
        assert identifier == "https://youtube.com/@MrBeast"
        assert comments is False

    def test_comments_flag(self):
        _, comments, limit = _parse_add_args(["@MrBeast", "--comments"])
        assert comments is True
        assert limit is None

    def test_comments_with_limit(self):
        _, comments, limit = _parse_add_args(["@MrBeast", "--comments", "-500"])
        assert comments is True
        assert limit == 500

    def test_comments_limit_1(self):
        _, comments, limit = _parse_add_args(["@X", "--comments", "-1"])
        assert limit == 1

    def test_comments_large_limit(self):
        _, comments, limit = _parse_add_args(["@X", "--comments", "-10000"])
        assert limit == 10000

    def test_no_comments_flag_no_limit(self):
        _, comments, limit = _parse_add_args(["@X", "--comments"])
        assert comments is True
        assert limit is None

    def test_invalid_limit_ignored(self):
        # "-abc" is not a digit string → limit stays None
        _, comments, limit = _parse_add_args(["@X", "--comments", "-abc"])
        assert comments is True
        assert limit is None
