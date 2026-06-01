import os, sys

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456789:AAFakeTokenForTesting")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("DATA_DIR", "/tmp/yt2tg_test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
