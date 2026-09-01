import os
from pathlib import Path

from dotenv import load_dotenv


# ==========================================
# LOAD .ENV
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / "backend" / ".env"

load_dotenv(ENV_FILE, override=True)


# ==========================================
# READ UPSTOX CONFIG
# ==========================================

CLIENT_ID = os.getenv("UPSTOX_CLIENT_ID")
CLIENT_SECRET = os.getenv("UPSTOX_CLIENT_SECRET")
REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")


# ==========================================
# CHECK
# ==========================================

print("========== UPSTOX CONFIG ==========")

print("Client ID loaded:", bool(CLIENT_ID))
print("Client Secret loaded:", bool(CLIENT_SECRET))
print("Redirect URI:", REDIRECT_URI)