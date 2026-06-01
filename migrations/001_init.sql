CREATE TABLE IF NOT EXISTS accounts (
    id               SERIAL PRIMARY KEY,
    identifier       TEXT NOT NULL,           -- URL or @handle as given
    url              TEXT NOT NULL,           -- normalized URL for yt-dlp
    display_name     TEXT,                    -- channel/playlist name (filled after first fetch)
    chat_id          BIGINT NOT NULL,
    comments_enabled BOOLEAN DEFAULT FALSE,
    comments_limit   INT,                     -- NULL = all comments
    added_at         TIMESTAMPTZ DEFAULT NOW(),
    last_checked     TIMESTAMPTZ,
    is_active        BOOLEAN DEFAULT TRUE,
    is_paused        BOOLEAN DEFAULT FALSE,
    CONSTRAINT accounts_url_chat_key UNIQUE (url, chat_id)
);

CREATE TABLE IF NOT EXISTS videos (
    id             SERIAL PRIMARY KEY,
    video_id       VARCHAR(20) NOT NULL,
    account_id     INT REFERENCES accounts(id) ON DELETE CASCADE,
    url            TEXT NOT NULL,
    title          TEXT,
    metadata_path  TEXT,
    upload_date    DATE,
    description    TEXT,
    like_count     INT,
    view_count     INT,
    comment_count  INT,
    discovered_at  TIMESTAMPTZ DEFAULT NOW(),
    sent_at        TIMESTAMPTZ,
    CONSTRAINT videos_video_id_account_key UNIQUE (video_id, account_id)
);

CREATE INDEX IF NOT EXISTS idx_videos_account_id ON videos(account_id);
CREATE INDEX IF NOT EXISTS idx_videos_sent_at    ON videos(sent_at);
CREATE INDEX IF NOT EXISTS idx_accounts_active   ON accounts(is_active);
