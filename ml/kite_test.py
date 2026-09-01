import os
from pathlib import Path

from dotenv import load_dotenv
from kiteconnect import KiteConnect


# ==========================================
# 1. LOAD CONFIG
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / "backend" / ".env"

load_dotenv(ENV_FILE, override=True)

API_KEY = os.getenv("KITE_API_KEY")


# ==========================================
# 2. INITIALIZE KITE
# ==========================================

kite = KiteConnect(api_key=API_KEY)


# ==========================================
# 3. LOAD ACCESS TOKEN
# ==========================================

TOKEN_FILE = BASE_DIR / "ml" / "kite_access_token.txt"

with open(TOKEN_FILE, "r") as file:
    access_token = file.read().strip()

kite.set_access_token(access_token)


# ==========================================
# 4. TEST PROFILE API
# ==========================================

profile = kite.profile()

print("========== KITE API TEST ==========")

print("API connected successfully")
print("User ID:", profile["user_id"])
print("User name:", profile["user_name"])
print("Email:", profile["email"])