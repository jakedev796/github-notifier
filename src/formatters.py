import discord
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def hex_to_int(color: str) -> int:
    if color.startswith("0x"):
        return int(color, 16)
    if color.startswith("#"):
        return int(color[1:], 16)
    return int(color, 16)


class NotificationFormatter:
    def __init__(self, embed_color: str = "0x5865F2"):
        self.default_color = hex_to_int(embed_color)

    def format_push(self, payload: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> discord.Embed:
        ref = payload.get("ref", "")
        branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
        commits = payload.get("commits", [])
        pusher = payload.get("pusher", {})
        repo = payload.get("repository", {})
        
        embed = discord.Embed(
            title=f"Push to {branch}",
            url=payload.get("compare", ""),
            color=self.default_color,
            timestamp=datetime.utcnow(),
        )
        
        embed.set_author(
            name=pusher.get("name", "Unknown"),
            icon_url=pusher.get("avatar_url", ""),
        )
        
        embed.add_field(name="Repository", value=repo.get("full_name", "Unknown"), inline=True)
        embed.add_field(name="Branch", value=branch, inline=True)
        embed.add_field(name="Commits", value=str(len(commits)), inline=True)
        
        if commits:
            commit_messages = []
            for commit in commits[:5]:
                message = commit.get("message", "").split("\n")[0]
                author = commit.get("author", {}).get("name", "Unknown")
                commit_id = commit.get("id", "")[:7]
                commit_messages.append(f"`{commit_id}` {message} - {author}")
            
            if len(commits) > 5:
                commit_messages.append(f"... and {len(commits) - 5} more")
            
            embed.add_field(name="Recent Commits", value="\n".join(commit_messages), inline=False)
        
        embed.set_footer(text=repo.get("full_name", ""))
        return embed

    def format_pull_request(self, payload: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> discord.Embed:
        pr = payload.get("pull_request", {})
        action = payload.get("action", "")
        repo = payload.get("repository", {})
        
        color_map = {
            "opened": 0x2ECC71,
            "closed": 0xE74C3C,
            "merged": 0x9B59B6,
            "reopened": 0x3498DB,
        }
        color = color_map.get(action, self.default_color)
        
        embed = discord.Embed(
            title=f"Pull Request #{pr.get('number')}: {pr.get('title', 'Untitled')}",
            url=pr.get("html_url", ""),
            description=pr.get("body", "")[:500] + ("..." if len(pr.get("body", "")) > 500 else ""),
            color=color,
            timestamp=datetime.fromisoformat(pr.get("updated_at", "").replace("Z", "+00:00")),
        )
        
        user = pr.get("user", {})
        embed.set_author(
            name=user.get("login", "Unknown"),
            icon_url=user.get("avatar_url", ""),
            url=user.get("html_url", ""),
        )
        
        embed.add_field(name="Action", value=action.title(), inline=True)
        embed.add_field(name="State", value=pr.get("state", "").title(), inline=True)
        embed.add_field(name="Repository", value=repo.get("full_name", "Unknown"), inline=True)
        
        if pr.get("draft"):
            embed.add_field(name="Draft", value="Yes", inline=True)
        
        if pr.get("merged"):
            embed.add_field(name="Merged", value="Yes", inline=True)
        
        if pr.get("base") and pr.get("head"):
            embed.add_field(
                name="Branch",
                value=f"{pr['base']['ref']} ← {pr['head']['ref']}",
                inline=False,
            )
        
        if pr.get("labels"):
            labels = [label.get("name") for label in pr.get("labels", [])]
            if labels:
                embed.add_field(name="Labels", value=", ".join(labels[:10]), inline=False)
        
        embed.set_footer(text=repo.get("full_name", ""))
        return embed

    def format_issue(self, payload: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> discord.Embed:
        issue = payload.get("issue", {})
        action = payload.get("action", "")
        repo = payload.get("repository", {})
        
        color_map = {
            "opened": 0x2ECC71,
            "closed": 0xE74C3C,
            "reopened": 0x3498DB,
        }
        color = color_map.get(action, self.default_color)
        
        embed = discord.Embed(
            title=f"Issue #{issue.get('number')}: {issue.get('title', 'Untitled')}",
            url=issue.get("html_url", ""),
            description=issue.get("body", "")[:500] + ("..." if len(issue.get("body", "")) > 500 else ""),
            color=color,
            timestamp=datetime.fromisoformat(issue.get("updated_at", "").replace("Z", "+00:00")),
        )
        
        user = issue.get("user", {})
        embed.set_author(
            name=user.get("login", "Unknown"),
            icon_url=user.get("avatar_url", ""),
            url=user.get("html_url", ""),
        )
        
        embed.add_field(name="Action", value=action.title(), inline=True)
        embed.add_field(name="State", value=issue.get("state", "").title(), inline=True)
        embed.add_field(name="Repository", value=repo.get("full_name", "Unknown"), inline=True)
        
        if issue.get("assignee"):
            assignee = issue.get("assignee", {})
            embed.add_field(
                name="Assignee",
                value=f"[{assignee.get('login', 'Unknown')}]({assignee.get('html_url', '')})",
                inline=True,
            )
        
        if issue.get("labels"):
            labels = [label.get("name") for label in issue.get("labels", [])]
            if labels:
                embed.add_field(name="Labels", value=", ".join(labels[:10]), inline=False)
        
        embed.set_footer(text=repo.get("full_name", ""))
        return embed

    def format_release(self, payload: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> discord.Embed:
        release = payload.get("release", {})
        action = payload.get("action", "")
        repo = payload.get("repository", {})
        
        color = 0xF39C12 if action == "published" else self.default_color
        
        embed = discord.Embed(
            title=f"Release: {release.get('name', release.get('tag_name', 'Untitled'))}",
            url=release.get("html_url", ""),
            description=release.get("body", "")[:1000] + ("..." if len(release.get("body", "")) > 1000 else ""),
            color=color,
            timestamp=datetime.fromisoformat(release.get("published_at", "").replace("Z", "+00:00")),
        )
        
        embed.add_field(name="Action", value=action.title(), inline=True)
        embed.add_field(name="Tag", value=release.get("tag_name", ""), inline=True)
        embed.add_field(name="Repository", value=repo.get("full_name", "Unknown"), inline=True)
        
        if release.get("prerelease"):
            embed.add_field(name="Pre-release", value="Yes", inline=True)
        
        if release.get("draft"):
            embed.add_field(name="Draft", value="Yes", inline=True)
        
        embed.set_footer(text=repo.get("full_name", ""))
        return embed

    def format_deployment(self, payload: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> discord.Embed:
        deployment = payload.get("deployment", {})
        repo = payload.get("repository", {})
        
        embed = discord.Embed(
            title=f"Deployment: {deployment.get('environment', 'Unknown')}",
            url=deployment.get("url", ""),
            color=self.default_color,
            timestamp=datetime.utcnow(),
        )
        
        embed.add_field(name="Environment", value=deployment.get("environment", "Unknown"), inline=True)
        embed.add_field(name="Ref", value=deployment.get("ref", ""), inline=True)
        embed.add_field(name="Repository", value=repo.get("full_name", "Unknown"), inline=True)
        
        if deployment.get("description"):
            embed.add_field(name="Description", value=deployment.get("description", ""), inline=False)
        
        embed.set_footer(text=repo.get("full_name", ""))
        return embed

    def format_workflow_run(self, payload: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> discord.Embed:
        workflow_run = payload.get("workflow_run", {})
        action = payload.get("action", "")
        repo = payload.get("repository", {})
        
        status = workflow_run.get("status", "")
        conclusion = workflow_run.get("conclusion", "")
        
        color_map = {
            "success": 0x2ECC71,
            "failure": 0xE74C3C,
            "cancelled": 0x95A5A6,
        }
        color = color_map.get(conclusion, self.default_color)
        
        embed = discord.Embed(
            title=f"Workflow: {workflow_run.get('name', 'Unknown')}",
            url=workflow_run.get("html_url", ""),
            color=color,
            timestamp=datetime.utcnow(),
        )
        
        embed.add_field(name="Status", value=status.title(), inline=True)
        if conclusion:
            embed.add_field(name="Conclusion", value=conclusion.title(), inline=True)
        embed.add_field(name="Repository", value=repo.get("full_name", "Unknown"), inline=True)
        
        if workflow_run.get("head_branch"):
            embed.add_field(name="Branch", value=workflow_run.get("head_branch", ""), inline=True)
        
        embed.set_footer(text=repo.get("full_name", ""))
        return embed

    def format_star(self, payload: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> discord.Embed:
        action = payload.get("action", "")
        repo = payload.get("repository", {})
        sender = payload.get("sender", {})
        
        embed = discord.Embed(
            title=f"Repository {action.title()}",
            url=repo.get("html_url", ""),
            description=f"{sender.get('login', 'Someone')} {action} {repo.get('full_name', 'this repository')}",
            color=0xF39C12 if action == "created" else self.default_color,
            timestamp=datetime.utcnow(),
        )
        
        embed.set_author(
            name=sender.get("login", "Unknown"),
            icon_url=sender.get("avatar_url", ""),
            url=sender.get("html_url", ""),
        )
        
        embed.add_field(name="Stars", value=str(repo.get("stargazers_count", 0)), inline=True)
        embed.set_footer(text=repo.get("full_name", ""))
        return embed

    def format_fork(self, payload: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> discord.Embed:
        forkee = payload.get("forkee", {})
        repo = payload.get("repository", {})
        sender = payload.get("sender", {})
        
        embed = discord.Embed(
            title=f"Repository Forked",
            url=forkee.get("html_url", ""),
            description=f"{sender.get('login', 'Someone')} forked {repo.get('full_name', 'this repository')}",
            color=self.default_color,
            timestamp=datetime.utcnow(),
        )
        
        embed.set_author(
            name=sender.get("login", "Unknown"),
            icon_url=sender.get("avatar_url", ""),
            url=sender.get("html_url", ""),
        )
        
        embed.add_field(name="Fork", value=forkee.get("full_name", ""), inline=True)
        embed.set_footer(text=repo.get("full_name", ""))
        return embed

    def format(self, event_type: str, payload: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Optional[discord.Embed]:
        formatter_map = {
            "push": self.format_push,
            "pull_request": self.format_pull_request,
            "issues": self.format_issue,
            "release": self.format_release,
            "deployment": self.format_deployment,
            "workflow_run": self.format_workflow_run,
            "star": self.format_star,
            "fork": self.format_fork,
        }
        
        formatter = formatter_map.get(event_type)
        if formatter:
            try:
                if config and config.get("embed_color"):
                    self.default_color = hex_to_int(config["embed_color"])
                return formatter(payload, config)
            except Exception as e:
                logger.error(f"Error formatting {event_type}: {e}", exc_info=True)
                return None
        
        logger.warning(f"Unknown event type: {event_type}")
        return None
