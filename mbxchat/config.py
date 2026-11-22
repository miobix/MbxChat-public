import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mbxchat:mbxchat@127.0.0.1:5434/mbxchat")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8005"))
