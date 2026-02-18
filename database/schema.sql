CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_name TEXT NOT NULL,
    guild_id INTEGER NOT NULL,
    webhook_secret TEXT NOT NULL,
    discord_category_id INTEGER,
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(repo_name, guild_id)
);

CREATE TABLE IF NOT EXISTS notification_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    channel_id INTEGER NOT NULL,
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    UNIQUE(repo_id, event_type)
);

CREATE TABLE IF NOT EXISTS webhook_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    branch_filter TEXT,
    label_filter TEXT,
    author_filter TEXT,
    mention_roles TEXT,
    mention_users TEXT,
    embed_color TEXT DEFAULT '0x5865F2',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    UNIQUE(repo_id)
);

CREATE INDEX IF NOT EXISTS idx_repositories_name ON repositories(repo_name);
CREATE INDEX IF NOT EXISTS idx_repositories_guild ON repositories(guild_id);
CREATE INDEX IF NOT EXISTS idx_notification_channels_repo ON notification_channels(repo_id);
CREATE INDEX IF NOT EXISTS idx_notification_channels_event ON notification_channels(event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_configs_repo ON webhook_configs(repo_id);
