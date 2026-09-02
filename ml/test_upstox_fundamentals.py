import os
import requests
from dotenv import load_dotenv

load_dotenv("../backend/.env")

ACCESS_TOKEN_FILE = "upstox_access_token.txt"

with open(ACCESS_TOKEN_FILE, "r") as f:
    access_token = f.read().strip()

ISIN = "INE002A01018"

BASE_URL = "https://api.upstox.com/v2/fundamentals"

headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {access_token}"
}


def get_fundamental(endpoint, params=None):

    url = f"{BASE_URL}/{ISIN}/{endpoint}"

    response = requests.get(
        url,
        headers=headers,
        params=params
    )

    print("\n========================================")
    print(f"Endpoint : {endpoint}")
    print(f"Status   : {response.status_code}")
    print("========================================")

    try:
        data = response.json()
        print(data)
        return data

    except Exception:
        print(response.text)
        return None


# Income Statement
get_fundamental(
    "income-statement",
    {
        "type": "consolidated",
        "time_period": "quarterly",
        "fs": "true"
    }
)


# Balance Sheet
get_fundamental(
    "balance-sheet",
    {
        "type": "consolidated",
        "fs": "true"
    }
)


# Cash Flow
get_fundamental(
    "cash-flow",
    {
        "type": "consolidated",
        "fs": "true"
    }
)