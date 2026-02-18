import aiosqlite
import os
import logging
from pathlib import Path
from typing import Optional, List
from .models import Repository, NotificationChannel, WebhookConfig

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_db_dir()

    def _ensure_db_dir(self):
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
            with open(schema_path, "r") as f:
                schema = f.read()
            await db.executescript(schema)
            await db.commit()
            logger.info(f"Database initialized at {self.db_path}")

    async def get_repository(self, repo_name: str, guild_id: int) -> Optional[Repository]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM repositories WHERE repo_name = ? AND guild_id = ?", (repo_name, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Repository.from_row(tuple(row))
                return None
    
    async def get_repositories_by_name(self, repo_name: str) -> List[Repository]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM repositories WHERE repo_name = ?", (repo_name,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [Repository.from_row(tuple(row)) for row in rows]

    async def get_repository_by_id(self, repo_id: int) -> Optional[Repository]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM repositories WHERE id = ?", (repo_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Repository.from_row(tuple(row))
                return None

    async def create_repository(
        self,
        repo_name: str,
        guild_id: int,
        webhook_secret: str,
        discord_category_id: Optional[int] = None,
    ) -> Repository:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO repositories (repo_name, guild_id, webhook_secret, discord_category_id)
                   VALUES (?, ?, ?, ?)""",
                (repo_name, guild_id, webhook_secret, discord_category_id),
            )
            await db.commit()
            repo = await self.get_repository(repo_name, guild_id)
            if not repo:
                raise ValueError("Failed to create repository")
            return repo

    async def update_repository(
        self,
        repo_id: int,
        webhook_secret: Optional[str] = None,
        discord_category_id: Optional[int] = None,
        enabled: Optional[bool] = None,
    ):
        updates = []
        params = []
        if webhook_secret is not None:
            updates.append("webhook_secret = ?")
            params.append(webhook_secret)
        if discord_category_id is not None:
            updates.append("discord_category_id = ?")
            params.append(discord_category_id)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(int(enabled))
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(repo_id)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    f"UPDATE repositories SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
                await db.commit()

    async def delete_repository(self, repo_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
            await db.commit()

    async def list_repositories(self, guild_id: int) -> List[Repository]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM repositories WHERE guild_id = ? ORDER BY repo_name", (guild_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [Repository.from_row(tuple(row)) for row in rows]

    async def get_notification_channel(
        self, repo_id: int, event_type: str
    ) -> Optional[NotificationChannel]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM notification_channels WHERE repo_id = ? AND event_type = ?",
                (repo_id, event_type),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return NotificationChannel.from_row(tuple(row))
                return None

    async def get_notification_channels(self, repo_id: int) -> List[NotificationChannel]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM notification_channels WHERE repo_id = ?", (repo_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [NotificationChannel.from_row(tuple(row)) for row in rows]

    async def create_notification_channel(
        self, repo_id: int, event_type: str, channel_id: int
    ) -> NotificationChannel:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO notification_channels 
                   (repo_id, event_type, channel_id) VALUES (?, ?, ?)""",
                (repo_id, event_type, channel_id),
            )
            await db.commit()
            channel = await self.get_notification_channel(repo_id, event_type)
            if not channel:
                raise ValueError("Failed to create notification channel")
            return channel

    async def update_notification_channel(
        self, repo_id: int, event_type: str, channel_id: Optional[int] = None, enabled: Optional[bool] = None
    ):
        updates = []
        params = []
        if channel_id is not None:
            updates.append("channel_id = ?")
            params.append(channel_id)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(int(enabled))
        if updates:
            params.extend([repo_id, event_type])
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    f"UPDATE notification_channels SET {', '.join(updates)} WHERE repo_id = ? AND event_type = ?",
                    params,
                )
                await db.commit()

    async def delete_notification_channel(self, repo_id: int, event_type: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM notification_channels WHERE repo_id = ? AND event_type = ?",
                (repo_id, event_type),
            )
            await db.commit()

    async def get_webhook_config(self, repo_id: int) -> Optional[WebhookConfig]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM webhook_configs WHERE repo_id = ?", (repo_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return WebhookConfig.from_row(tuple(row))
                return None

    async def create_webhook_config(
        self,
        repo_id: int,
        branch_filter: Optional[str] = None,
        label_filter: Optional[str] = None,
        author_filter: Optional[str] = None,
        mention_roles: Optional[str] = None,
        mention_users: Optional[str] = None,
        embed_color: str = "0x5865F2",
    ) -> WebhookConfig:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO webhook_configs 
                   (repo_id, branch_filter, label_filter, author_filter, mention_roles, mention_users, embed_color)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    repo_id,
                    branch_filter,
                    label_filter,
                    author_filter,
                    mention_roles,
                    mention_users,
                    embed_color,
                ),
            )
            await db.commit()
            config = await self.get_webhook_config(repo_id)
            if not config:
                raise ValueError("Failed to create webhook config")
            return config

    async def update_webhook_config(
        self,
        repo_id: int,
        branch_filter: Optional[str] = None,
        label_filter: Optional[str] = None,
        author_filter: Optional[str] = None,
        mention_roles: Optional[str] = None,
        mention_users: Optional[str] = None,
        embed_color: Optional[str] = None,
    ):
        updates = []
        params = []
        if branch_filter is not None:
            updates.append("branch_filter = ?")
            params.append(branch_filter)
        if label_filter is not None:
            updates.append("label_filter = ?")
            params.append(label_filter)
        if author_filter is not None:
            updates.append("author_filter = ?")
            params.append(author_filter)
        if mention_roles is not None:
            updates.append("mention_roles = ?")
            params.append(mention_roles)
        if mention_users is not None:
            updates.append("mention_users = ?")
            params.append(mention_users)
        if embed_color is not None:
            updates.append("embed_color = ?")
            params.append(embed_color)
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(repo_id)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    f"UPDATE webhook_configs SET {', '.join(updates)} WHERE repo_id = ?",
                    params,
                )
                await db.commit()

    async def get_channel_for_event(self, repo_id: int, event_type: str) -> Optional[int]:
        channel = await self.get_notification_channel(repo_id, event_type)
        if channel and channel.enabled:
            return channel.channel_id
        return None
