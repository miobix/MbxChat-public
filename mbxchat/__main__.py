import logging
import sys
import threading

from telegram import Update

from mbxchat import config
from mbxchat.bot import build_app
from mbxchat.health import make_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx logs every request URL at INFO, and Telegram URLs contain the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("mbxchat")


def main() -> None:
    if problems := config.bot_config_problems():
        sys.exit("Cannot start: " + "; ".join(problems) + ". See .env.example.")
    server = make_server("0.0.0.0", config.HEALTH_PORT)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("health endpoint on :%s", config.HEALTH_PORT)
    build_app(config.TELEGRAM_BOT_TOKEN).run_polling(allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY])


if __name__ == "__main__":
    main()
