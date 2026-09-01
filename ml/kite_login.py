import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, request
from kiteconnect import KiteConnect


# ==========================================
# 1. LOAD .ENV
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / "backend" / ".env"

load_dotenv(ENV_FILE, override=True)


# ==========================================
# 2. KITE CONFIG
# ==========================================

API_KEY = os.getenv("KITE_API_KEY")
API_SECRET = os.getenv("KITE_API_SECRET")

print("========== KITE CONFIG ==========")
print("ENV exists:", ENV_FILE.exists())
print("API Key loaded:", bool(API_KEY))
print("API Secret loaded:", bool(API_SECRET))


if not API_KEY:
    raise ValueError("KITE_API_KEY missing")

if not API_SECRET:
    raise ValueError("KITE_API_SECRET missing")


# ==========================================
# 3. KITE
# ==========================================

kite = KiteConnect(api_key=API_KEY)


# ==========================================
# 4. FLASK CALLBACK
# ==========================================

app = Flask(__name__)


@app.route("/")
def callback():

    request_token = request.args.get("request_token")
    status = request.args.get("status")

    print("\n========== KITE CALLBACK ==========")
    print("Status:", status)
    print("Request token received:", bool(request_token))

    if request_token:

        print("Request token captured successfully.")

        return """
        <h2>Kite login successful</h2>
        <p>Request token received.</p>
        <p>You can close this tab and return to the terminal.</p>
        """

    return """
    <h2>Kite Callback</h2>
    <p>No request token received.</p>
    """


# ==========================================
# 5. START
# ==========================================

if __name__ == "__main__":

    print("\n========== KITE LOGIN ==========")

    print("\nOpen this URL in your browser:\n")

    print(kite.login_url())

    print("\nWaiting for Kite callback...")
    print("Callback URL: http://127.0.0.1:8000/")

    app.run(
        host="127.0.0.1",
        port=8000,
        debug=False
    )