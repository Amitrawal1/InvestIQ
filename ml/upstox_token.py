import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from dotenv import load_dotenv


# ==========================================
# LOAD ENV
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / "backend" / ".env"

load_dotenv(ENV_FILE, override=True)

CLIENT_ID = os.getenv("UPSTOX_CLIENT_ID")
CLIENT_SECRET = os.getenv("UPSTOX_CLIENT_SECRET")
REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")


# ==========================================
# GET AUTHORIZATION CODE
# ==========================================

redirected_url = input(
    "Paste the FULL redirected URL from browser: "
).strip()

parsed_url = urlparse(redirected_url)
query_params = parse_qs(parsed_url.query)

code = query_params.get("code", [None])[0]


if not code:
    print("Authorization code not found.")
    exit()


# ==========================================
# EXCHANGE CODE FOR ACCESS TOKEN
# ==========================================

url = "https://api.upstox.com/v2/login/authorization/token"

data = {
    "code": code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
}

headers = {
    "accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
}

response = requests.post(
    url,
    data=data,
    headers=headers
)


# ==========================================
# RESPONSE
# ==========================================

print("\n========== UPSTOX TOKEN RESPONSE ==========")
print("Status:", response.status_code)

result = response.json()

if response.status_code != 200:
    print(result)
    exit()


access_token = result.get("access_token")

if not access_token:
    print("Access token not found.")
    print(result)
    exit()


print("Access token received:", True)


# ==========================================
# SAVE TOKEN
# ==========================================

TOKEN_FILE = BASE_DIR / "ml" / "upstox_access_token.txt"

with open(TOKEN_FILE, "w") as file:
    file.write(access_token)

print("Access token saved to:")
print(TOKEN_FILE)