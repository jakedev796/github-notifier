import discord
from discord import app_commands
from discord.ext import commands
import os
import logging
import secrets
import json
from typing import Optional, List
from .config import Database
from .models import Repository, NotificationChannel, WebhookConfig

logger = logging.getLogger(__name__)


class NotificationBot(commands.Bot):
    def __init__(self, db: Database, webhook_server_url: Optional[str] = None):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        
        super().__init__(command_prefix="!", intents=intents)
        self.db = db
        self.webhook_server_url = webhook_server_url or "http://localhost:8000"
        self.formatter = None

    async def setup_hook(self):
        logger.info("Syncing commands to Discord...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} command(s) to Discord")
            for cmd in synced:
                logger.debug(f"  - /{cmd.name}")
        except Exception as e:
            logger.error(f"Error syncing commands: {e}", exc_info=True)

    async def on_ready(self):
        logger.info(f"Bot logged in as {self.user}")
        await self.db.initialize()


class NotificationSetupView(discord.ui.View):
    def __init__(self, bot: NotificationBot, repo_name: str, webhook_secret: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.repo_name = repo_name
        self.webhook_secret = webhook_secret
        self.webhook_url = f"{bot.webhook_server_url.rstrip('/')}/webhook"
        self.event_types = [
            "push",
            "pull_request",
            "issues",
            "release",
            "deployment",
            "workflow_run",
            "star",
            "fork",
        ]

    @discord.ui.select(
        placeholder="Select notification types...",
        min_values=1,
        max_values=len(["push", "pull_request", "issues", "release", "deployment", "workflow_run", "star", "fork"]),
        options=[
            discord.SelectOption(label="Push", value="push", description="Code pushes"),
            discord.SelectOption(label="Pull Requests", value="pull_request", description="PR events"),
            discord.SelectOption(label="Issues", value="issues", description="Issue events"),
            discord.SelectOption(label="Releases", value="release", description="Release events"),
            discord.SelectOption(label="Deployments", value="deployment", description="Deployment events"),
            discord.SelectOption(label="Workflow Runs", value="workflow_run", description="CI/CD workflows"),
            discord.SelectOption(label="Stars", value="star", description="Repository stars"),
            discord.SelectOption(label="Forks", value="fork", description="Repository forks"),
        ],
    )
    async def select_notifications(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        await interaction.response.defer()
        
        try:
            if not interaction.guild:
                await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
                return
            
            repo = await self.bot.db.get_repository(self.repo_name, interaction.guild.id)
            if not repo:
                await interaction.followup.send("Repository not found. Please run `/setup repo` again.", ephemeral=True)
                return
            
            category = None
            if repo.discord_category_id:
                category = interaction.guild.get_channel(repo.discord_category_id)
            
            if not category:
                category = await interaction.guild.create_category(name=f"📦 {self.repo_name}")
                await self.bot.db.update_repository(repo.id, discord_category_id=category.id)
            
            created_channels = []
            for event_type in select.values:
                channel_name = event_type.replace("_", "-")
                channel = await category.create_text_channel(name=channel_name)
                await self.bot.db.create_notification_channel(repo.id, event_type, channel.id)
                created_channels.append(f"#{channel.name}")
            
            webhook_url = self.webhook_url
            github_webhook_url = f"https://github.com/{self.repo_name}/settings/hooks/new"
            
            embed = discord.Embed(
                title="Setup Complete!",
                description=f"Repository **{self.repo_name}** has been configured.",
                color=0x2ECC71,
            )
            embed.add_field(name="Category", value=category.name, inline=True)
            embed.add_field(name="Channels Created", value=", ".join(created_channels), inline=False)
            embed.add_field(
                name="Webhook URL",
                value=f"`{webhook_url}`\n\nCopy this URL for your GitHub webhook configuration.",
                inline=False,
            )
            embed.add_field(
                name="Webhook Secret",
                value=f"`{self.webhook_secret}`\n\nUse this secret when configuring your GitHub webhook.",
                inline=False,
            )
            embed.add_field(
                name="GitHub Webhook Settings",
                value=f"[Configure webhook for {self.repo_name}]({github_webhook_url})",
                inline=False,
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            self.stop()
        except Exception as e:
            logger.error(f"Error setting up notifications: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class EventTypesAdjustView(discord.ui.View):
    def __init__(self, bot: NotificationBot, repo_name: str, existing_event_types: set):
        super().__init__(timeout=300)
        self.bot = bot
        self.repo_name = repo_name
        self.event_types = [
            "push",
            "pull_request",
            "issues",
            "release",
            "deployment",
            "workflow_run",
            "star",
            "fork",
        ]
        
        options = [
            discord.SelectOption(label="Push", value="push", description="Code pushes", default="push" in existing_event_types),
            discord.SelectOption(label="Pull Requests", value="pull_request", description="PR events", default="pull_request" in existing_event_types),
            discord.SelectOption(label="Issues", value="issues", description="Issue events", default="issues" in existing_event_types),
            discord.SelectOption(label="Releases", value="release", description="Release events", default="release" in existing_event_types),
            discord.SelectOption(label="Deployments", value="deployment", description="Deployment events", default="deployment" in existing_event_types),
            discord.SelectOption(label="Workflow Runs", value="workflow_run", description="CI/CD workflows", default="workflow_run" in existing_event_types),
            discord.SelectOption(label="Stars", value="star", description="Repository stars", default="star" in existing_event_types),
            discord.SelectOption(label="Forks", value="fork", description="Repository forks", default="fork" in existing_event_types),
        ]
        
        self.select = discord.ui.Select(
            placeholder="Select notification types...",
            min_values=0,
            max_values=len(options),
            options=options,
        )
        self.select.callback = self.select_notifications
        self.add_item(self.select)

    async def select_notifications(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        await interaction.response.defer()
        
        try:
            if not interaction.guild:
                await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
                return
            
            repo = await self.bot.db.get_repository(self.repo_name, interaction.guild.id)
            if not repo:
                await interaction.followup.send("Repository not found.", ephemeral=True)
                return
            
            existing_channels = await self.bot.db.get_notification_channels(repo.id)
            existing_event_types = {ch.event_type for ch in existing_channels}
            selected_event_types = set(select.values)
            
            event_types_to_add = selected_event_types - existing_event_types
            event_types_to_remove = existing_event_types - selected_event_types
            
            category = None
            if repo.discord_category_id:
                category = interaction.guild.get_channel(repo.discord_category_id)
            
            if not category:
                category = await interaction.guild.create_category(name=f"📦 {self.repo_name}")
                await self.bot.db.update_repository(repo.id, discord_category_id=category.id)
            
            created_channels = []
            deleted_channels = []
            
            for event_type in event_types_to_add:
                channel_name = event_type.replace("_", "-")
                channel = await category.create_text_channel(name=channel_name)
                await self.bot.db.create_notification_channel(repo.id, event_type, channel.id)
                created_channels.append(f"#{channel.name}")
            
            for event_type in event_types_to_remove:
                channel_config = await self.bot.db.get_notification_channel(repo.id, event_type)
                if channel_config:
                    channel = interaction.guild.get_channel(channel_config.channel_id)
                    if channel:
                        try:
                            await channel.delete()
                            deleted_channels.append(f"#{channel.name}")
                        except Exception as e:
                            logger.error(f"Error deleting channel {channel.id}: {e}")
                    await self.bot.db.delete_notification_channel(repo.id, event_type)
            
            embed = discord.Embed(
                title="Event Types Updated",
                description=f"Event types for **{self.repo_name}** have been updated.",
                color=0x2ECC71,
            )
            
            if created_channels:
                embed.add_field(name="Channels Created", value=", ".join(created_channels), inline=False)
            if deleted_channels:
                embed.add_field(name="Channels Deleted", value=", ".join(deleted_channels), inline=False)
            if not created_channels and not deleted_channels:
                embed.add_field(name="No Changes", value="Event types remain the same.", inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            self.stop()
        except Exception as e:
            logger.error(f"Error adjusting event types: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class NotificationConfigModal(discord.ui.Modal, title="Configure Notifications"):
    branch_filter = discord.ui.TextInput(
        label="Branch Filter",
        placeholder="main,develop (leave empty for all)",
        required=False,
        max_length=200,
    )
    
    label_filter = discord.ui.TextInput(
        label="Label Filter",
        placeholder="bug,enhancement (leave empty for all)",
        required=False,
        max_length=200,
    )
    
    mention_roles = discord.ui.TextInput(
        label="Mention Roles",
        placeholder="role1,role2 (leave empty for none)",
        required=False,
        max_length=200,
    )
    
    embed_color = discord.ui.TextInput(
        label="Embed Color",
        placeholder="0x5865F2 (hex color)",
        required=False,
        max_length=10,
    )

    def __init__(self, bot: NotificationBot, repo_name: str):
        super().__init__()
        self.bot = bot
        self.repo_name = repo_name

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            if not interaction.guild:
                await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
                return
            
            repo = await self.bot.db.get_repository(self.repo_name, interaction.guild.id)
            if not repo:
                await interaction.followup.send("Repository not found.", ephemeral=True)
                return
            
            config = await self.bot.db.get_webhook_config(repo.id)
            if not config:
                await self.bot.db.create_webhook_config(
                    repo.id,
                    branch_filter=self.branch_filter.value or None,
                    label_filter=self.label_filter.value or None,
                    mention_roles=self.mention_roles.value or None,
                    embed_color=self.embed_color.value or "0x5865F2",
                )
            else:
                await self.bot.db.update_webhook_config(
                    repo.id,
                    branch_filter=self.branch_filter.value if self.branch_filter.value else None,
                    label_filter=self.label_filter.value if self.label_filter.value else None,
                    mention_roles=self.mention_roles.value if self.mention_roles.value else None,
                    embed_color=self.embed_color.value if self.embed_color.value else None,
                )
            
            embed = discord.Embed(
                title="Configuration Updated",
                description=f"Settings for **{self.repo_name}** have been updated.",
                color=0x2ECC71,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error updating config: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)


class NotificationBotCommands(commands.Cog):
    def __init__(self, bot: NotificationBot):
        self.bot = bot

    async def repo_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        if not interaction.guild:
            return []
        repos = await self.bot.db.list_repositories(interaction.guild.id)
        choices = [
            app_commands.Choice(name=repo.repo_name, value=repo.repo_name)
            for repo in repos
            if current.lower() in repo.repo_name.lower()
        ]
        return choices[:25]

    @app_commands.command(name="setup", description="Set up a new repository for notifications")
    @app_commands.describe(repo_name="Repository name (e.g., owner/repo)")
    async def setup_repo(self, interaction: discord.Interaction, repo_name: str):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        try:
            existing = await self.bot.db.get_repository(repo_name, interaction.guild.id)
            if existing:
                await interaction.followup.send(
                    f"Repository **{repo_name}** is already configured. Use `/configure` to modify settings.",
                    ephemeral=True,
                )
                return
            
            webhook_secret = secrets.token_urlsafe(32)
            repo = await self.bot.db.create_repository(repo_name, interaction.guild.id, webhook_secret)
            
            view = NotificationSetupView(self.bot, repo_name, webhook_secret)
            embed = discord.Embed(
                title="Repository Setup",
                description=f"Select which notification types you want for **{repo_name}**.",
                color=0x5865F2,
            )
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error setting up repo: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)

    @app_commands.command(name="configure", description="Configure notification settings for a repository")
    @app_commands.describe(repo_name="Repository name")
    @app_commands.autocomplete(repo_name=repo_autocomplete)
    async def configure_repo(self, interaction: discord.Interaction, repo_name: str):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        repo = await self.bot.db.get_repository(repo_name, interaction.guild.id)
        if not repo:
            await interaction.response.send_message("Repository not found. Use `/setup` first.", ephemeral=True)
            return
        
        config = await self.bot.db.get_webhook_config(repo.id)
        modal = NotificationConfigModal(self.bot, repo_name)
        
        if config:
            modal.branch_filter.default = config.branch_filter or ""
            modal.label_filter.default = config.label_filter or ""
            modal.mention_roles.default = config.mention_roles or ""
            modal.embed_color.default = config.embed_color or "0x5865F2"
        
        await interaction.response.send_modal(modal)

    @app_commands.command(name="list", description="List all configured repositories")
    async def list_repos(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        repos = await self.bot.db.list_repositories(interaction.guild.id)
        if not repos:
            await interaction.followup.send("No repositories configured.", ephemeral=True)
            return
        
        embed = discord.Embed(title="Configured Repositories", color=0x5865F2)
        for repo in repos:
            status = "Enabled" if repo.enabled else "Disabled"
            channels = await self.bot.db.get_notification_channels(repo.id)
            channel_count = len([c for c in channels if c.enabled])
            embed.add_field(
                name=repo.repo_name,
                value=f"Status: {status}\nChannels: {channel_count}",
                inline=True,
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="remove", description="Remove a repository configuration")
    @app_commands.describe(repo_name="Repository name to remove")
    @app_commands.autocomplete(repo_name=repo_autocomplete)
    async def remove_repo(self, interaction: discord.Interaction, repo_name: str):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        repo = await self.bot.db.get_repository(repo_name, interaction.guild.id)
        if not repo:
            await interaction.followup.send("Repository not found.", ephemeral=True)
            return
        
        await self.bot.db.delete_repository(repo.id)
        
        if repo.discord_category_id:
            category = interaction.guild.get_channel(repo.discord_category_id)
            if category:
                for channel in category.channels:
                    await channel.delete()
                await category.delete()
        
        embed = discord.Embed(
            title="Repository Removed",
            description=f"**{repo_name}** has been removed and all associated channels deleted.",
            color=0xE74C3C,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="stats", description="Show bot statistics")
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        repos = await self.bot.db.list_repositories(interaction.guild.id)
        total_channels = 0
        for repo in repos:
            channels = await self.bot.db.get_notification_channels(repo.id)
            total_channels += len([c for c in channels if c.enabled])
        
        embed = discord.Embed(title="Bot Statistics", color=0x5865F2)
        embed.add_field(name="Repositories", value=str(len(repos)), inline=True)
        embed.add_field(name="Total Channels", value=str(total_channels), inline=True)
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="test", description="Send a test notification for a repository")
    @app_commands.describe(repo_name="Repository name")
    @app_commands.autocomplete(repo_name=repo_autocomplete)
    async def test_webhook(self, interaction: discord.Interaction, repo_name: str):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        repo = await self.bot.db.get_repository(repo_name, interaction.guild.id)
        if not repo:
            await interaction.followup.send("Repository not found.", ephemeral=True)
            return
        
        channels = await self.bot.db.get_notification_channels(repo.id)
        if not channels:
            await interaction.followup.send("No notification channels configured.", ephemeral=True)
            return
        
        test_embed = discord.Embed(
            title="Test Notification",
            description=f"This is a test notification for **{repo_name}**.",
            color=0x5865F2,
            timestamp=discord.utils.utcnow(),
        )
        test_embed.set_footer(text=repo_name)
        
        sent_count = 0
        for channel_config in channels:
            if channel_config.enabled:
                channel = self.bot.get_channel(channel_config.channel_id)
                if channel:
                    try:
                        await channel.send(embed=test_embed)
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Error sending test to {channel.id}: {e}")
        
        await interaction.followup.send(
            f"Test notification sent to {sent_count} channel(s).",
            ephemeral=True,
        )

    @app_commands.command(name="events", description="Adjust which event types are tracked for a repository")
    @app_commands.describe(repo_name="Repository name")
    @app_commands.autocomplete(repo_name=repo_autocomplete)
    async def adjust_event_types(self, interaction: discord.Interaction, repo_name: str):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        repo = await self.bot.db.get_repository(repo_name, interaction.guild.id)
        if not repo:
            await interaction.response.send_message("Repository not found. Use `/setup` first.", ephemeral=True)
            return
        
        existing_channels = await self.bot.db.get_notification_channels(repo.id)
        existing_event_types = {ch.event_type for ch in existing_channels}
        
        view = EventTypesAdjustView(self.bot, repo_name, existing_event_types)
        
        embed = discord.Embed(
            title="Adjust Event Types",
            description=f"Select which event types you want to track for **{repo_name}**.\n\nCurrently tracked: {', '.join(sorted(existing_event_types)) if existing_event_types else 'None'}",
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="export", description="Export configuration as JSON")
    async def export_config(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        repos = await self.bot.db.list_repositories(interaction.guild.id)
        config_data = []
        
        for repo in repos:
            channels = await self.bot.db.get_notification_channels(repo.id)
            config = await self.bot.db.get_webhook_config(repo.id)
            
            repo_data = {
                "repo_name": repo.repo_name,
                "webhook_secret": repo.webhook_secret,
                "discord_category_id": repo.discord_category_id,
                "enabled": repo.enabled,
                "channels": [
                    {
                        "event_type": ch.event_type,
                        "channel_id": ch.channel_id,
                        "enabled": ch.enabled,
                    }
                    for ch in channels
                ],
            }
            
            if config:
                repo_data["config"] = {
                    "branch_filter": config.branch_filter,
                    "label_filter": config.label_filter,
                    "author_filter": config.author_filter,
                    "mention_roles": config.mention_roles,
                    "mention_users": config.mention_users,
                    "embed_color": config.embed_color,
                }
            
            config_data.append(repo_data)
        
        json_data = json.dumps(config_data, indent=2)
        file = discord.File(
            fp=json_data.encode(),
            filename="config_export.json",
        )
        
        await interaction.followup.send(
            "Configuration exported.",
            file=file,
            ephemeral=True,
        )


async def setup_bot(db: Database, token: str, webhook_server_url: Optional[str] = None) -> NotificationBot:
    bot = NotificationBot(db, webhook_server_url)
    await bot.add_cog(NotificationBotCommands(bot))
    bot.token = token
    return bot
