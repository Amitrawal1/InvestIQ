import os
from pathlib import Path

import requests
from dotenv import load_dotenv


# ==========================================
# 1. LOAD ENV
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / "backend" / ".env"

load_dotenv(ENV_FILE, override=True)


# ==========================================
# 2. LOAD ACCESS TOKEN
# ==========================================

TOKEN_FILE = BASE_DIR / "ml" / "upstox_access_token.txt"

with open(TOKEN_FILE, "r") as file:
    access_token = file.read().strip()


# ==========================================
# 3. TEST INSTRUMENT
# ==========================================

# Reliance Industries
instrument_key = "NSE_EQ|INE002A01018"

from_date = "2026-08-25"
to_date = "2026-08-29"


# ==========================================
# 4. API URL
# ==========================================

url = (
    f"https://api.upstox.com/v3/historical-candle/"
    f"{instrument_key}/days/1/{to_date}/{from_date}"
)


headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {access_token}",
}


# ==========================================
# 5. REQUEST
# ==========================================

print("========== UPSTOX HISTORICAL TEST ==========")

print("Instrument:", instrument_key)
print("From:", from_date)
print("To:", to_date)

response = requests.get(
    url,
    headers=headers
)


# ==========================================
# 6. RESPONSE
# ==========================================

print("\nStatus:", response.status_code)

if response.status_code != 200:
    print("\nAPI Error:")
    print(response.text)
    exit()


result = response.json()

print("\nAPI Status:")
print(result.get("status"))

candles = result.get("data", {}).get("candles", [])

print("\nTotal candles:", len(candles))

print("\n========== CANDLES ==========")

for candle in candles:
    print(candle)