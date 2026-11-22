import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mbxchat:mbxchat@127.0.0.1:5434/mbxchat")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8005"))

# MbxRead saved terms, read by `python -m mbxchat.importer` on the host.
MBXREAD_URL = os.getenv("MBXREAD_URL", "http://127.0.0.1:8002").strip()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
_user = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
TELEGRAM_ALLOWED_USER_ID = int(_user) if _user.isdigit() else None


def bot_config_problems() -> list[str]:
    problems = []
    if not TELEGRAM_BOT_TOKEN:
        problems.append("TELEGRAM_BOT_TOKEN is empty (get one from @BotFather)")
    if TELEGRAM_ALLOWED_USER_ID is None:
        problems.append("TELEGRAM_ALLOWED_USER_ID is missing or not a number")
    return problems
