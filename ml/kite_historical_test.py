import os
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv
from kiteconnect import KiteConnect


# ==========================================
# 1. LOAD CONFIG
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / "backend" / ".env"

load_dotenv(ENV_FILE, override=True)

API_KEY = os.getenv("KITE_API_KEY")

TOKEN_FILE = BASE_DIR / "ml" / "kite_access_token.txt"


# ==========================================
# 2. INITIALIZE KITE
# ==========================================

kite = KiteConnect(api_key=API_KEY)

with open(TOKEN_FILE, "r") as file:
    access_token = file.read().strip()

kite.set_access_token(access_token)


# ==========================================
# 3. TEST INSTRUMENT
# ==========================================

# Example: Reliance
instrument_token = 738561

from_date = "2026-08-25"
to_date = "2026-08-27"


print("========== HISTORICAL DATA TEST ==========")
print("Instrument token:", instrument_token)
print("From:", from_date)
print("To:", to_date)


# ==========================================
# 4. FETCH HISTORICAL DATA
# ==========================================

data = kite.historical_data(
    instrument_token=instrument_token,
    from_date=from_date,
    to_date=to_date,
    interval="day"
)


# ==========================================
# 5. DISPLAY RESPONSE
# ==========================================

print("\n========== API RESPONSE ==========")

print("Records:", len(data))

for row in data:
    print(row)
    