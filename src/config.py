import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
DATABASE_URL: str = os.environ["DATABASE_URL"]

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
METADATA_DIR  = DATA_DIR / "metadata"
TEMP_DIR      = DATA_DIR / "temp"
COMMENTS_DIR  = DATA_DIR / "comments"

POLL_INTERVAL_MIN = int(os.getenv("POLL_INTERVAL_MIN", "15"))
POLL_INTERVAL_MAX = int(os.getenv("POLL_INTERVAL_MAX", "20"))

COOKIES_FILE: str | None = os.getenv("COOKIES_FILE")

for d in (METADATA_DIR, TEMP_DIR, COMMENTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
