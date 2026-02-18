from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
import asyncio
import logging
import json
import discord
from typing import Optional, List
from .config import Database
from .formatters import NotificationFormatter
from .utils import verify_webhook_signature, parse_repo_name, should_notify_branch, should_notify_label, should_notify_author

logger = logging.getLogger(__name__)


class WebhookServer:
    def __init__(self, db: Database, bot_instance=None):
        self.app = FastAPI(title="GitHub Webhook Server")
        self.db = db
        self.bot = bot_instance
        self.formatter = NotificationFormatter()
        self.setup_routes()

    def setup_routes(self):
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy"}

        @self.app.post("/webhook")
        async def webhook_handler(
            request: Request,
            x_github_event: Optional[str] = Header(None),
            x_github_delivery: Optional[str] = Header(None),
            x_hub_signature_256: Optional[str] = Header(None),
        ):
            try:
                payload = await request.body()
                payload_json = json.loads(payload.decode("utf-8"))
                
                repo_full_name = payload_json.get("repository", {}).get("full_name")
                if not repo_full_name:
                    logger.warning("No repository found in webhook payload")
                    return JSONResponse(
                        status_code=400,
                        content={"error": "No repository found in payload"},
                    )
                
                repos = await self.db.get_repositories_by_name(repo_full_name)
                
                if not repos:
                    logger.warning(f"Repository {repo_full_name} not found in database")
                    return JSONResponse(
                        status_code=404,
                        content={"error": "Repository not configured"},
                    )
                
                event_type = x_github_event
                if not event_type:
                    logger.warning("No event type in webhook headers")
                    return JSONResponse(
                        status_code=400,
                        content={"error": "No event type specified"},
                    )
                
                if not x_hub_signature_256:
                    logger.warning("Webhook request missing X-Hub-Signature-256 header")
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Missing signature"},
                    )

                repos_to_process = []
                for repo in repos:
                    if not repo.enabled:
                        logger.debug(f"Repository {repo_full_name} in guild {repo.guild_id} is disabled, skipping")
                        continue
                    
                    webhook_secret = repo.webhook_secret
                    if not verify_webhook_signature(payload, x_hub_signature_256, webhook_secret):
                        logger.warning(f"Invalid signature for {repo_full_name} in guild {repo.guild_id}")
                        continue
                    
                    repos_to_process.append(repo)
                
                if repos_to_process:
                    asyncio.create_task(self.process_webhooks_async(repos_to_process, event_type, payload_json))
                
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "accepted",
                        "event": event_type,
                        "repository": repo_full_name,
                        "guilds_queued": len(repos_to_process),
                    },
                )
            except json.JSONDecodeError:
                logger.error("Invalid JSON in webhook payload")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid JSON"},
                )
            except Exception as e:
                logger.error(f"Error processing webhook: {e}", exc_info=True)
                return JSONResponse(
                    status_code=500,
                    content={"error": "Internal server error"},
                )

    async def process_webhooks_async(self, repos: List, event_type: str, payload: dict):
        for repo in repos:
            try:
                await self.process_webhook(repo.id, repo.guild_id, event_type, payload)
            except Exception as e:
                logger.error(f"Error processing webhook for repo {repo.id}: {e}", exc_info=True)

    async def process_webhook(self, repo_id: int, guild_id: int, event_type: str, payload: dict):
        try:
            channel_id = await self.db.get_channel_for_event(repo_id, event_type)
            if not channel_id:
                logger.debug(f"No channel configured for {event_type} in repo {repo_id}")
                return
            
            config = await self.db.get_webhook_config(repo_id)
            config_dict = None
            if config:
                config_dict = {
                    "branch_filter": config.branch_filter,
                    "label_filter": config.label_filter,
                    "author_filter": config.author_filter,
                    "mention_roles": config.mention_roles,
                    "mention_users": config.mention_users,
                    "embed_color": config.embed_color,
                }
                
                if not self.should_process_event(event_type, payload, config_dict):
                    logger.debug(f"Event filtered out for repo {repo_id}")
                    return
            
            embed = self.formatter.format(event_type, payload, config_dict)
            if not embed:
                logger.warning(f"Could not format event type {event_type}")
                return
            
            if not self.bot:
                logger.error("Bot instance not available")
                return
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"Guild {guild_id} not found, bot may not be in that server")
                return
            
            channel = guild.get_channel(channel_id)
            if not channel:
                logger.error(f"Channel {channel_id} not found in guild {guild_id}")
                return
            
            content = ""
            if config_dict:
                if config_dict.get("mention_roles"):
                    roles = [role.strip() for role in config_dict["mention_roles"].split(",")]
                    role_mentions = []
                    for role_name in roles:
                        role = discord.utils.get(channel.guild.roles, name=role_name)
                        if role:
                            role_mentions.append(role.mention)
                    if role_mentions:
                        content += " ".join(role_mentions) + "\n"
                
                if config_dict.get("mention_users"):
                    users = [user.strip() for user in config_dict["mention_users"].split(",")]
                    user_mentions = []
                    for user_name in users:
                        member = discord.utils.get(channel.guild.members, name=user_name)
                        if member:
                            user_mentions.append(member.mention)
                    if user_mentions:
                        content += " ".join(user_mentions) + "\n"
            
            await channel.send(content=content if content else None, embed=embed)
            logger.info(f"Sent notification for {event_type} to channel {channel_id}")
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)

    def should_process_event(self, event_type: str, payload: dict, config: Optional[dict]) -> bool:
        if not config:
            return True
        
        if event_type == "push":
            ref = payload.get("ref", "")
            branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
            if not should_notify_branch(config.get("branch_filter"), branch):
                return False
            
            pusher = payload.get("pusher", {})
            author = pusher.get("name", "")
            if not should_notify_author(config.get("author_filter"), author):
                return False
        
        elif event_type == "pull_request":
            pr = payload.get("pull_request", {})
            base = pr.get("base", {})
            branch = base.get("ref", "")
            if not should_notify_branch(config.get("branch_filter"), branch):
                return False
            
            user = pr.get("user", {})
            author = user.get("login", "")
            if not should_notify_author(config.get("author_filter"), author):
                return False
            
            labels = pr.get("labels", [])
            if not should_notify_label(config.get("label_filter"), labels):
                return False
        
        elif event_type == "issues":
            issue = payload.get("issue", {})
            labels = issue.get("labels", [])
            if not should_notify_label(config.get("label_filter"), labels):
                return False
            
            user = issue.get("user", {})
            author = user.get("login", "")
            if not should_notify_author(config.get("author_filter"), author):
                return False
        
        return True


def create_app(db: Database, bot_instance=None) -> FastAPI:
    server = WebhookServer(db, bot_instance)
    return server.app
