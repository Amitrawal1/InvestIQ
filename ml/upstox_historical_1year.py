import os
from pathlib import Path
from datetime import datetime, timedelta

import requests
import mysql.connector
from dotenv import load_dotenv


# ==========================================
# 1. ENV
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / "backend" / ".env"

load_dotenv(ENV_FILE, override=True)


# ==========================================
# 2. ACCESS TOKEN
# ==========================================

TOKEN_FILE = BASE_DIR / "ml" / "upstox_access_token.txt"

with open(TOKEN_FILE, "r") as file:
    access_token = file.read().strip()


# ==========================================
# 3. DATABASE
# ==========================================

db = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)

cursor = db.cursor(dictionary=True)


# ==========================================
# 4. COMPANY
# ==========================================

cursor.execute("""
    SELECT
        id,
        symbol,
        name,
        upstox_instrument_key
    FROM companies
    WHERE symbol = 'RELIANCE'
    LIMIT 1
""")

company = cursor.fetchone()

if not company:
    print("RELIANCE not found.")
    exit()


company_id = company["id"]
instrument_key = company["upstox_instrument_key"]

print("========== COMPANY ==========")
print("Company ID:", company_id)
print("Symbol:", company["symbol"])
print("Name:", company["name"])
print("Instrument:", instrument_key)


# ==========================================
# 5. DATE RANGE
# ==========================================

to_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
from_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

print("\n========== DATE RANGE ==========")
print("From:", from_date)
print("To:", to_date)


# ==========================================
# 6. UPSTOX API
# ==========================================

url = (
    f"https://api.upstox.com/v3/historical-candle/"
    f"{instrument_key}/days/1/{to_date}/{from_date}"
)

headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {access_token}",
}


print("\nFetching historical data...")

response = requests.get(
    url,
    headers=headers,
    timeout=30
)

print("API Status:", response.status_code)

if response.status_code != 200:
    print(response.text)
    cursor.close()
    db.close()
    exit()


result = response.json()

candles = result.get("data", {}).get("candles", [])

print("Candles received:", len(candles))


# ==========================================
# 7. INSERT
# ==========================================

inserted = 0
skipped = 0

for candle in candles:

    timestamp = candle[0]
    open_price = candle[1]
    high_price = candle[2]
    low_price = candle[3]
    close_price = candle[4]
    volume = candle[5]

    price_date = datetime.fromisoformat(
        timestamp.replace("Z", "+00:00")
    ).replace(tzinfo=None)

    cursor.execute("""
        INSERT IGNORE INTO stock_prices (
            company_id,
            price_date,
            open_price,
            high_price,
            low_price,
            close_price,
            volume
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        company_id,
        price_date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume
    ))

    if cursor.rowcount == 1:
        inserted += 1
    else:
        skipped += 1


# ==========================================
# 8. COMMIT
# ==========================================

db.commit()


print("\n========== IMPORT COMPLETE ==========")
print("Candles received:", len(candles))
print("New records inserted:", inserted)
print("Existing records skipped:", skipped)


# ==========================================
# 9. DATABASE TOTAL
# ==========================================

cursor.execute("""
    SELECT COUNT(*) AS total
    FROM stock_prices
    WHERE company_id = %s
""", (company_id,))

total = cursor.fetchone()["total"]

print("\nTotal RELIANCE price records in DB:", total)


# ==========================================
# 10. CLOSE
# ==========================================

cursor.close()
db.close()