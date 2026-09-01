import os
from pathlib import Path

from dotenv import load_dotenv
from kiteconnect import KiteConnect


# ==========================================
# 1. LOAD ENV
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
# 3. FETCH QUOTE
# ==========================================

symbols = [
    "NSE:RELIANCE"
]

print("Fetching market quote...")

data = kite.quote(symbols)


# ==========================================
# 4. DISPLAY
# ==========================================

print("\n========== KITE QUOTE RESPONSE ==========")

for symbol, quote in data.items():

    print("\nSymbol:", symbol)

    print("Last Price:", quote.get("last_price"))
    print("Volume:", quote.get("volume"))
    print("Average Price:", quote.get("average_price"))

    print("\nOHLC:")
    print(quote.get("ohlc"))

    print("\n52 Week:")
    print(quote.get("52_week"))

    print("\nBuy Quantity:", quote.get("buy_quantity"))
    print("Sell Quantity:", quote.get("sell_quantity"))

    print("\nFull Response:")
    print(quote)