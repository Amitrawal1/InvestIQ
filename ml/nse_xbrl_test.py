import requests
from bs4 import BeautifulSoup

XBRL_URL = "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117298_1348254_16012025082021.xml"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/"
}

response = requests.get(
    XBRL_URL,
    headers=headers,
    timeout=30
)

print("Status:", response.status_code)
print("Content-Type:", response.headers.get("Content-Type"))
print("Size:", len(response.content), "bytes")

if response.status_code != 200:
    print(response.text[:1000])
    exit()

# Save raw XBRL
with open("reliance_financial_result.xml", "wb") as f:
    f.write(response.content)

print("\nXBRL saved successfully.")

# Show beginning of document
text = response.text

print("\n========== XBRL PREVIEW ==========")
print(text[:3000])