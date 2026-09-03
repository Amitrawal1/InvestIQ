import requests

ISIN = "INE002A01018"

ACCESS_TOKEN_FILE = "upstox_access_token.txt"

with open(ACCESS_TOKEN_FILE, "r") as f:
    access_token = f.read().strip()

url = f"https://api.upstox.com/v2/fundamentals/{ISIN}/key-ratios"

headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {access_token}"
}

response = requests.get(
    url,
    headers=headers
)

print("\n========================================")
print("Endpoint : key-ratios")
print("Status   :", response.status_code)
print("========================================")

try:
    data = response.json()
    print(data)

except Exception:
    print(response.text)
    