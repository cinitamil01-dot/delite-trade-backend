from flask import Flask, jsonify
import dalal

app = Flask(__name__)

@app.route("/")
def home():
    return "Delite Trade Backend is running!"

@app.route("/nifty")
def nifty():
    try:
        data = dalal.quote("NIFTY 50")

        return jsonify({
            "symbol": "NIFTY 50",
            "price": data["ltp"],
            "open": data["open"],
            "high": data["high"],
            "low": data["low"],
            "prev_close": data["prev_close"]
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500
