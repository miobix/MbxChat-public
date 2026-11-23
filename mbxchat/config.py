import os
from datetime import time

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mbxchat:mbxchat@127.0.0.1:5434/mbxchat")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8005"))

# MbxRead saved terms, read by `python -m mbxchat.importer` on the host.
MBXREAD_URL = os.getenv("MBXREAD_URL", "http://127.0.0.1:8002").strip()

# Capture model (SPEC §6, §7c). The ID is Ollama's digest prefix, checked at startup.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").strip()
CAPTURE_MODEL = os.getenv("CAPTURE_MODEL", "gemma4:e4b").strip()
CAPTURE_MODEL_ID = os.getenv("CAPTURE_MODEL_ID", "dc35e8d9c606").strip()
GRADER_MODEL = os.getenv("GRADER_MODEL", CAPTURE_MODEL).strip()

# AnkiConnect on the desktop (compose: host.docker.internal). Chunk cards go to ANKI_DECK.
ANKI_URL = os.getenv("ANKI_URL", "http://127.0.0.1:8765").strip()
ANKI_DECK = os.getenv("ANKI_DECK", "MbxChat").strip()
ANKI_RETRY_SECONDS = 60

# Practice pings, in local time (PRACTICE_TZ, an IANA zone such as Europe/Paris).
PRACTICE_TZ = os.getenv("PRACTICE_TZ", "UTC").strip() or "UTC"
PRACTICE_PINGS = [
    time.fromisoformat(t.strip()) for t in os.getenv("PRACTICE_PINGS", "10:00,13:00,17:00,21:00").split(",") if t.strip()
]

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
