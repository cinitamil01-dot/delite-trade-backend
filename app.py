from flask import Flask, jsonify
import requests

app = Flask(__name__)

@app.route("/")
def home():
    return "Delite Trade Backend is running!"

@app.route("/nifty")
def nifty():
    try:
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/"
        }

        session = requests.Session()
        session.headers.update(headers)

        session.get("https://www.nseindia.com/", timeout=10)
        response = session.get(url, timeout=10)

        data = response.json()

        spot = data["records"]["underlyingValue"]

        return jsonify({
            "symbol": "NIFTY 50",
            "price": spot
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500
