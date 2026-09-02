import json
import gzip
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
import os


# ==========================================
# 1. PATHS + ENV
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

ENV_FILE = BASE_DIR / "backend" / ".env"
load_dotenv(ENV_FILE, override=True)

INSTRUMENT_FILE = BASE_DIR / "ml" / "data" / "upstox_nse.json.gz"


# ==========================================
# 2. LOAD UPSTOX INSTRUMENTS
# ==========================================

print("Loading Upstox instruments...")

with gzip.open(INSTRUMENT_FILE, "rt", encoding="utf-8") as file:
    instruments = json.load(file)

print("Total instruments:", len(instruments))


# ==========================================
# 3. CREATE ISIN → INSTRUMENT KEY MAP
# ==========================================

upstox_map = {}

for item in instruments:

    if item.get("segment") != "NSE_EQ":
        continue

    isin = item.get("isin")

    if isin:
        upstox_map[isin] = item.get("instrument_key")


print("NSE Equity mappings:", len(upstox_map))


# ==========================================
# 4. CONNECT MYSQL
# ==========================================

db = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)

cursor = db.cursor()


# ==========================================
# 5. GET COMPANIES
# ==========================================

cursor.execute("""
    SELECT id, isin
    FROM companies
    WHERE isin IS NOT NULL
      AND isin != ''
""")

companies = cursor.fetchall()

print("Companies with ISIN:", len(companies))


# ==========================================
# 6. UPDATE MAPPING
# ==========================================

matched = 0
unmatched = 0

for company_id, isin in companies:

    instrument_key = upstox_map.get(isin)

    if instrument_key:

        cursor.execute("""
            UPDATE companies
            SET upstox_instrument_key = %s
            WHERE id = %s
        """, (instrument_key, company_id))

        matched += 1

    else:
        unmatched += 1


# ==========================================
# 7. COMMIT
# ==========================================

db.commit()


print("\n========== MAPPING COMPLETE ==========")

print("Matched:", matched)
print("Unmatched:", unmatched)


# ==========================================
# 8. CLOSE
# ==========================================

cursor.close()
db.close()