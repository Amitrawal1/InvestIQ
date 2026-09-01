import os
from pathlib import Path

import pandas as pd
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
# 3. FETCH NSE INSTRUMENTS
# ==========================================

print("Fetching NSE instruments...")

instruments = kite.instruments("NSE")

print("Total NSE instruments:", len(instruments))


# ==========================================
# 4. CONVERT TO DATAFRAME
# ==========================================

df = pd.DataFrame(instruments)

print("\n========== COLUMNS ==========")
print(df.columns.tolist())


print("\n========== FIRST 10 RECORDS ==========")
print(df.head(10).to_string())


print("\n========== DATA TYPES ==========")
print(df.dtypes)


print("\n========== INSTRUMENT TYPES ==========")
print(df["instrument_type"].value_counts())


print("\n========== EXCHANGES ==========")
print(df["exchange"].value_counts())


# ==========================================
# 5. CHECK COMPANY MAPPING
# ==========================================

# Only NSE equity instruments
nse_equity = df[
    (df["exchange"] == "NSE") &
    (df["instrument_type"] == "EQ")
].copy()

print("\nNSE Equity instruments:", len(nse_equity))


# ==========================================
# 6. LOAD COMPANIES FROM MYSQL
# ==========================================

import mysql.connector

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

db = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)

cursor = db.cursor(dictionary=True)

cursor.execute("""
    SELECT
        id,
        name,
        symbol,
        exchange,
        instrument_token
    FROM companies
    WHERE exchange = 'NSE'
""")

companies = cursor.fetchall()

companies_df = pd.DataFrame(companies)

print("\n========== COMPANY DATA ==========")
print("NSE companies:", len(companies_df))
print(companies_df.head())


# ==========================================
# 7. MAP SYMBOLS
# ==========================================

mapping = companies_df.merge(
    nse_equity[
        [
            "instrument_token",
            "tradingsymbol",
            "name",
            "exchange"
        ]
    ],
    left_on=["symbol", "exchange"],
    right_on=["tradingsymbol", "exchange"],
    how="left",
    suffixes=("_company", "_kite")
)


# ==========================================
# 8. MAPPING VALIDATION
# ==========================================

mapping["matched"] = mapping["instrument_token_kite"].notna()

print("\n========== MAPPING RESULT ==========")

print("Total companies:", len(mapping))
print("Matched:", mapping["matched"].sum())
print("Unmatched:", (~mapping["matched"]).sum())

print("\n========== SAMPLE MATCHES ==========")
print(
    mapping[
        mapping["matched"]
    ][
        [
            "id",
            "symbol",
            "name_company",
            "instrument_token_kite"
        ]
    ].head(20).to_string(index=False)
)

print("\n========== SAMPLE UNMATCHED ==========")
print(
    mapping[
        ~mapping["matched"]
    ][
        [
            "id",
            "symbol",
            "name_company"
        ]
    ].head(20).to_string(index=False)
)