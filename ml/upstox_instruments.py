import requests
import gzip
import json
from pathlib import Path


# ==========================================
# 1. PATH
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "ml" / "data"
DATA_DIR.mkdir(exist_ok=True)

FILE_PATH = DATA_DIR / "upstox_nse.json.gz"


# ==========================================
# 2. DOWNLOAD NSE INSTRUMENTS
# ==========================================

url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"

print("Downloading Upstox instrument master...")

response = requests.get(url)

print("Status:", response.status_code)

response.raise_for_status()


# ==========================================
# 3. SAVE FILE
# ==========================================

with open(FILE_PATH, "wb") as file:
    file.write(response.content)

print("Saved to:")
print(FILE_PATH)


# ==========================================
# 4. READ FILE
# ==========================================

print("\nReading instruments...")

with gzip.open(FILE_PATH, "rt", encoding="utf-8") as file:
    instruments = json.load(file)


print("Total instruments:", len(instruments))


# ==========================================
# 5. BASIC INSPECTION
# ==========================================

print("\nFirst instrument:")

print(instruments[0])