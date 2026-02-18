from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Repository:
    id: int
    repo_name: str
    guild_id: int
    webhook_secret: str
    discord_category_id: Optional[int]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: tuple) -> "Repository":
        return cls(
            id=row[0],
            repo_name=row[1],
            guild_id=row[2],
            webhook_secret=row[3],
            discord_category_id=row[4],
            enabled=bool(row[5]),
            created_at=datetime.fromisoformat(row[6]) if isinstance(row[6], str) else row[6],
            updated_at=datetime.fromisoformat(row[7]) if isinstance(row[7], str) else row[7],
        )


@dataclass
class NotificationChannel:
    id: int
    repo_id: int
    event_type: str
    channel_id: int
    enabled: bool
    created_at: datetime

    @classmethod
    def from_row(cls, row: tuple) -> "NotificationChannel":
        return cls(
            id=row[0],
            repo_id=row[1],
            event_type=row[2],
            channel_id=row[3],
            enabled=bool(row[4]),
            created_at=datetime.fromisoformat(row[5]) if isinstance(row[5], str) else row[5],
        )


@dataclass
class WebhookConfig:
    id: int
    repo_id: int
    branch_filter: Optional[str]
    label_filter: Optional[str]
    author_filter: Optional[str]
    mention_roles: Optional[str]
    mention_users: Optional[str]
    embed_color: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: tuple) -> "WebhookConfig":
        return cls(
            id=row[0],
            repo_id=row[1],
            branch_filter=row[2],
            label_filter=row[3],
            author_filter=row[4],
            mention_roles=row[5],
            mention_users=row[6],
            embed_color=row[7] or "0x5865F2",
            created_at=datetime.fromisoformat(row[8]) if isinstance(row[8], str) else row[8],
            updated_at=datetime.fromisoformat(row[9]) if isinstance(row[9], str) else row[9],
        )
