"""Kite login callback: captures request_token and saves access_token to backend/.env."""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, request
from kiteconnect import KiteConnect

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / "backend" / ".env"

load_dotenv(ENV_FILE, override=True)

API_KEY = os.getenv("KITE_API_KEY")
API_SECRET = os.getenv("KITE_API_SECRET")

app = Flask(__name__)


def save_access_token(access_token: str) -> None:
    text = ENV_FILE.read_text()
    if re.search(r"^KITE_ACCESS_TOKEN=.*$", text, flags=re.MULTILINE):
        text = re.sub(
            r"^KITE_ACCESS_TOKEN=.*$",
            f"KITE_ACCESS_TOKEN={access_token}",
            text,
            flags=re.MULTILINE,
        )
    else:
        text = text.rstrip() + f"\nKITE_ACCESS_TOKEN={access_token}\n"
    ENV_FILE.write_text(text)


@app.route("/")
def callback():
    print("\n========== KITE CALLBACK ==========")
    print("Full URL:", request.url)
    print("Query parameters:", dict(request.args))

    request_token = request.args.get("request_token")
    status = request.args.get("status")

    print("Request token:", request_token)
    print("Status:", status)

    if not request_token:
        return """
        <h2>Waiting for Kite login</h2>
        <p>This page has no <code>request_token</code>.</p>
        <p>Keep this server running, then open the login URL from <code>kite_test.py</code>
        and complete login. Zerodha will redirect back here with the token.</p>
        """

    if not API_KEY or not API_SECRET:
        return """
        <h2>Missing credentials</h2>
        <p>KITE_API_KEY or KITE_API_SECRET is not set in backend/.env</p>
        """, 500

    kite = KiteConnect(api_key=API_KEY)
    try:
        session = kite.generate_session(request_token, api_secret=API_SECRET)
    except Exception as exc:
        print("generate_session failed:", exc)
        return f"""
        <h2>Failed to generate access token</h2>
        <p>Request token is one-time and expires quickly. Login again from kite_test.py.</p>
        <pre>{exc}</pre>
        """, 400

    access_token = session["access_token"]
    save_access_token(access_token)
    kite.set_access_token(access_token)

    print("Access token saved to backend/.env")
    print("User:", session.get("user_id"), session.get("user_name"))

    return f"""
    <h2>Kite login successful</h2>
    <p>Access token saved to <code>backend/.env</code> as <code>KITE_ACCESS_TOKEN</code>.</p>
    <p>User: {session.get("user_id")} — {session.get("user_name")}</p>
    <p>You can close this tab. Restart any app that reads the .env file.</p>
    """


if __name__ == "__main__":
    if not API_KEY or not API_SECRET:
        raise ValueError("KITE_API_KEY / KITE_API_SECRET missing in backend/.env")

    print("Callback listening at", os.getenv("KITE_REDIRECT_URL", "http://127.0.0.1:8000/"))
    print("This URL must match Redirect URL in the Zerodha developer console.")
    app.run(host="127.0.0.1", port=8000)
