import os
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv


# ==========================================
# LOAD ENV
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / "backend" / ".env"

load_dotenv(ENV_FILE, override=True)

CLIENT_ID = os.getenv("UPSTOX_CLIENT_ID")
REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")


# ==========================================
# GENERATE LOGIN URL
# ==========================================

params = {
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "response_type": "code",
}

login_url = (
    "https://api.upstox.com/v2/login/authorization/dialog?"
    + urlencode(params)
)


print("========== UPSTOX LOGIN ==========")
print("\nOpen this URL in your browser:\n")
print(login_url)
print("\nAfter login, you will be redirected to:")
print(REDIRECT_URI)