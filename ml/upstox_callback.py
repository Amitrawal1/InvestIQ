from flask import Flask, request

app = Flask(__name__)


@app.route("/")
def callback():

    code = request.args.get("code")
    error = request.args.get("error")

    print("\n========== UPSTOX CALLBACK ==========")
    print("Full URL:", request.url)
    print("Authorization code received:", bool(code))
    print("Error:", error)

    if code:
        print("\nAuthorization successful.")
        print("Code received successfully.")

    return """
    <h2>Upstox Login Successful</h2>
    <p>Authorization code received.</p>
    <p>You can close this tab and return to the terminal.</p>
    """


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8000,
        debug=False
    )