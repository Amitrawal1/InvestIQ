import requests
import json

URL = "https://www.nseindia.com/api/corporates-financial-results"

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/151.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results",
    "Accept-Language": "en-US,en;q=0.9"
}

session = requests.Session()

params = {
    "index": "equities",
    "symbol": "RELIANCE",
    "period": "Quarterly"
}

response = session.get(
    URL,
    params=params,
    headers=headers,
    timeout=30
)

print("Status:", response.status_code)
print("URL:", response.url)

if response.status_code != 200:
    print(response.text[:2000])
    exit()

data = response.json()

print("\n========== RESULTS ==========")
print("Type:", type(data))
print("Total records:", len(data))

if data:
    print("\n========== FIRST RECORD ==========")
    print(json.dumps(data[0], indent=4))
else:
    print("No records returned.")