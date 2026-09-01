import os
from pathlib import Path

from dotenv import load_dotenv
from kiteconnect import KiteConnect


# ==========================================
# 1. LOAD .ENV
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / "backend" / ".env"

load_dotenv(ENV_FILE, override=True)


# ==========================================
# 2. KITE CREDENTIALS
# ==========================================

API_KEY = os.getenv("KITE_API_KEY")
API_SECRET = os.getenv("KITE_API_SECRET")

kite = KiteConnect(api_key=API_KEY)


# ==========================================
# 3. REQUEST TOKEN
# ==========================================

request_token = input("Paste request token: ").strip()


# ==========================================
# 4. GENERATE SESSION
# ==========================================

session_data = kite.generate_session(
    request_token,
    api_secret=API_SECRET
)


# ==========================================
# 5. ACCESS TOKEN
# ==========================================

access_token = session_data["access_token"]

print("\n========== KITE SESSION ==========")
print("Session generated successfully")
print("Access token received:", bool(access_token))


# ==========================================
# 6. SAVE ACCESS TOKEN
# ==========================================

TOKEN_FILE = BASE_DIR / "ml" / "kite_access_token.txt"

with open(TOKEN_FILE, "w") as file:
    file.write(access_token)

print("Access token saved to:", TOKEN_FILE)