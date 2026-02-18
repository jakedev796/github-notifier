# GitHub Notifier Discord Bot

[![Invite Bot](https://img.shields.io/badge/Invite%20Bot-Discord-5865F2?style=for-the-badge&logo=discord)](https://discord.com/api/oauth2/authorize?client_id=1473707174403379332&permissions=268437504&scope=bot%20applications.commands)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue.svg)](https://github.com/Rapptz/discord.py)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

A Discord bot that receives GitHub webhooks and sends formatted notifications to configured channels. Features per-repo configuration, automatic channel creation, and slash commands for easy setup.

> **💡 Prefer not to host it yourself?** [Invite the public bot](https://discord.com/api/oauth2/authorize?client_id=1473707174403379332&permissions=268437504&scope=bot%20applications.commands) to your server - each server's config is fully isolated.

## Features

- **Multi-Guild Support** — each server's repositories are completely isolated
- **Per-Repository Configuration** — independent notification channels and settings per repo
- **Automatic Channel Creation** — creates categories and channels during `/setup`
- **Rich Notifications** — embeds for pushes, PRs, issues, releases, deployments, workflow runs, stars, and forks
- **Flexible Filtering** — filter by branch, label, or author
- **Webhook Security** — HMAC SHA256 signature verification
- **Docker & Unraid Ready** — containerized with CI/CD to GHCR

## Quick Start

### 1. Configure Environment

```bash
cp .env.example .env
```

```env
DISCORD_BOT_TOKEN=your_discord_bot_token_here
WEBHOOK_SECRET=your_default_webhook_secret_here
WEBHOOK_SERVER_URL=http://your-server:8000
DATABASE_PATH=./data/bot.db
WEBHOOK_PORT=8000
WEBHOOK_HOST=0.0.0.0
LOG_LEVEL=INFO
```

### 2. Run

**Docker Compose (recommended):**
```bash
docker-compose up -d
```

**Docker:**
```bash
docker build -t github-notifier .
docker run -d --name github-notifier \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  github-notifier
```

**Local:**
```bash
pip install -r requirements.txt
python main.py
```

## Discord Bot Setup

1. Create an application at the [Discord Developer Portal](https://discord.com/developers/applications)
2. Add a bot and enable **MESSAGE CONTENT INTENT** under Privileged Gateway Intents
3. Copy the bot token into your `.env`
4. [Invite the bot](https://discord.com/api/oauth2/authorize?client_id=1473707174403379332&permissions=268437504&scope=bot%20applications.commands) to your server (requires Manage Channels, Send Messages, Embed Links, Use Slash Commands)

## Usage

### Setting Up a Repository

```
/setup repo_name:owner/repository-name
```

The bot will generate a webhook secret, create a category and channels for your selected notification types, and display the webhook URL and secret. Follow the provided link to add the webhook in GitHub (set content type to `application/json`).

### Commands

| Command | Description |
|---------|-------------|
| `/setup repo_name <name>` | Set up a new repository with notification channels |
| `/configure notifications <repo>` | Configure branch/label/author filters, mention roles, embed color |
| `/list repos` | List configured repositories and their status |
| `/remove repo <name>` | Remove a repository and its channels |
| `/test webhook <repo>` | Send a test notification |
| `/export config` | Export all configurations as JSON |
| `/stats` | Show bot statistics |

## Supported Events

Push, Pull Requests, Issues, Releases, Deployments, Workflow Runs, Stars, Forks

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DISCORD_BOT_TOKEN` | Discord bot token | Yes | — |
| `WEBHOOK_SECRET` | Default webhook secret | No | — |
| `WEBHOOK_SERVER_URL` | Public URL of your webhook server | No | `http://localhost:8000` |
| `DATABASE_PATH` | Path to SQLite database | No | `./data/bot.db` |
| `WEBHOOK_PORT` | Webhook server port | No | `8000` |
| `WEBHOOK_HOST` | Webhook server host | No | `0.0.0.0` |
| `LOG_LEVEL` | Logging level | No | `INFO` |

## Troubleshooting

**`PrivilegedIntentsRequired` error** — Enable MESSAGE CONTENT INTENT in the [Developer Portal](https://discord.com/developers/applications) under Bot → Privileged Gateway Intents.

**Commands not appearing** — Slash commands can take up to an hour to sync globally. Restart the bot to force a sync.

**Webhooks not working** — Verify the webhook URL is publicly accessible, the secret matches between GitHub and the bot, and the repo is configured (`/list repos`).

**502 Bad Gateway (Cloudflare)** — If using Cloudflare proxy (orange cloud), disable it for your webhook endpoint (set DNS to "DNS only" / gray cloud). The webhook handler processes requests asynchronously to avoid timeout issues, but Cloudflare's proxy can still cause problems.

**Missing notifications** — Check that the event type is enabled for the repo and that filters aren't excluding the event.

## License

MIT