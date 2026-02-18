import asyncio
import logging
import os
from dotenv import load_dotenv
import uvicorn
from src.config import Database
from src.bot import setup_bot
from src.webhook_server import create_app

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main():
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    if not discord_token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is required")
    
    db_path = os.getenv("DATABASE_PATH", "./data/bot.db")
    db = Database(db_path)
    await db.initialize()
    
    webhook_server_url = os.getenv("WEBHOOK_SERVER_URL")
    bot = await setup_bot(db, discord_token, webhook_server_url)
    
    webhook_host = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    webhook_port = int(os.getenv("WEBHOOK_PORT", "8000"))
    
    app = create_app(db, bot)
    
    async def run_bot():
        try:
            await bot.start(discord_token)
        except Exception as e:
            logger.error(f"Bot error: {e}", exc_info=True)
            raise
    
    async def run_webhook():
        try:
            config = uvicorn.Config(
                app,
                host=webhook_host,
                port=webhook_port,
                log_level=os.getenv("LOG_LEVEL", "info").lower(),
            )
            server = uvicorn.Server(config)
            await server.serve()
        except Exception as e:
            logger.error(f"Webhook server error: {e}", exc_info=True)
            raise
    
    try:
        await asyncio.gather(run_bot(), run_webhook())
    finally:
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
