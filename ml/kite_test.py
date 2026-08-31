"""Print the Kite login URL using credentials from backend/.env."""

import os
from pathlib import Path

from dotenv import load_dotenv
from kiteconnect import KiteConnect

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / "backend" / ".env"
load_dotenv(ENV_FILE, override=True)

API_KEY = os.getenv("KITE_API_KEY")
API_SECRET = os.getenv("KITE_API_SECRET")
CLIENT_ID = os.getenv("KITE_CLIENT_ID")
REDIRECT_URL = os.getenv("KITE_REDIRECT_URL")
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN")

print("Loaded env from:", ENV_FILE)
print("API Key loaded:", bool(API_KEY))
print("API Secret loaded:", bool(API_SECRET))
print("Client ID loaded:", bool(CLIENT_ID))
print("Access token present:", bool(ACCESS_TOKEN))
print("Redirect URL:", REDIRECT_URL)

if not API_KEY or not API_SECRET:
    raise ValueError("Kite credentials missing in backend/.env")

kite = KiteConnect(api_key=API_KEY)

print("\n1. In another terminal, start the callback server:")
print("   python ml/kite_callback.py")
print("\n2. Open this login URL in the browser, log in as", CLIENT_ID or "your Kite user")
print(kite.login_url())
print("\n3. After login, Zerodha redirects to", REDIRECT_URL)
print("   The callback will print request_token and save KITE_ACCESS_TOKEN to backend/.env")
print("\nNote: request_token is NOT in .env. It only appears in the redirect URL after login.")
print("      KITE_ACCESS_TOKEN is created by exchanging that request_token.")
