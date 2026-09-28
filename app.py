from flask import Flask, jsonify
from nsepythonserver import nse_quote_ltp

app = Flask(__name__)

@app.route("/")
def home():
    return "Delite Trade Backend is running!"

@app.route("/nifty")
def nifty():
    try:
        price = nse_quote_ltp("NIFTY")
        return jsonify({
            "symbol": "NIFTY 50",
            "price": price
        })
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500
