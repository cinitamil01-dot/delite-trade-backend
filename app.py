from flask import Flask, jsonify
import yfinance as yf
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os
import json
import urllib.request
import urllib.parse

app = Flask(__name__)

SYMBOLS = {
    "nifty": ("^NSEI", "NIFTY 50"),
    "sensex": ("^BSESN", "SENSEX"),
    "crude": ("CL=F", "WTI CRUDE"),
    "natgas": ("NG=F", "NATURAL GAS"),
}


def get_quote(ticker_symbol, display_name):
    ticker = yf.Ticker(ticker_symbol)

    df = ticker.history(
        period="1d",
        interval="1m",
        auto_adjust=False
    )

    if df.empty:
        raise RuntimeError("No market data returned")

    row = df.dropna(subset=["Close"]).iloc[-1]

    price = float(row["Close"])
    previous = None

    try:
        daily = ticker.history(
            period="5d",
            interval="1d",
            auto_adjust=False
        )

        if len(daily) >= 2:
            previous = float(daily["Close"].iloc[-2])
    except Exception:
        pass

    change = None
    change_pct = None

    if previous:
        change = price - previous
        change_pct = (change / previous) * 100

    return {
        "symbol": display_name,
        "ticker": ticker_symbol,
        "price": price,
        "open": float(row["Open"]),
        "high": float(row["High"]),
        "low": float(row["Low"]),
        "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
        "prev_close": previous,
        "change": change,
        "change_pct": change_pct,
        "source": "Yahoo Finance via yfinance",
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }


def send_telegram_message(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").replace("\r", "").replace("\n", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").replace("\r", "").replace("\n", "").strip()

    if not token or not chat_id:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not configured"
        )

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message
    }).encode()

    request = urllib.request.Request(url, data=data)

    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode())


@app.route("/")
def home():
    return jsonify({
        "service": "Delite Trade Backend",
        "status": "running",
        "mode": "paper trading",
        "market_data": "free/public source adapter",
        "telegram_alerts": "enabled"
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/nifty")
def nifty():
    try:
        return jsonify(get_quote(*SYMBOLS["nifty"]))
    except Exception as e:
        return jsonify({"error": str(e), "symbol": "NIFTY 50"}), 502


@app.route("/sensex")
def sensex():
    try:
        return jsonify(get_quote(*SYMBOLS["sensex"]))
    except Exception as e:
        return jsonify({"error": str(e), "symbol": "SENSEX"}), 502


@app.route("/crude")
def crude():
    try:
        return jsonify(get_quote(*SYMBOLS["crude"]))
    except Exception as e:
        return jsonify({"error": str(e), "symbol": "WTI CRUDE"}), 502


@app.route("/natgas")
def natgas():
    try:
        return jsonify(get_quote(*SYMBOLS["natgas"]))
    except Exception as e:
        return jsonify({"error": str(e), "symbol": "NATURAL GAS"}), 502


@app.route("/market")
def market():
    result = {}

    for key, (ticker_symbol, display_name) in SYMBOLS.items():
        try:
            result[key] = get_quote(ticker_symbol, display_name)
        except Exception as e:
            result[key] = {
                "error": str(e),
                "symbol": display_name
            }

    return jsonify(result)


@app.route("/signals")
def signals():
    result = {}

    for key, (ticker_symbol, display_name) in SYMBOLS.items():
        try:
            data = get_quote(ticker_symbol, display_name)

            change_pct = data.get("change_pct")

            if change_pct is None:
                signal = "NO DATA"
            elif change_pct > 0:
                signal = "UP"
            elif change_pct < 0:
                signal = "DOWN"
            else:
                signal = "FLAT"

            result[key] = {
                "symbol": display_name,
                "price": data["price"],
                "change_pct": change_pct,
                "signal": signal,
                "timestamp_utc": data["timestamp_utc"]
            }

        except Exception as e:
            result[key] = {
                "symbol": display_name,
                "signal": "ERROR",
                "error": str(e)
            }

    return jsonify(result)


@app.route("/market-alert")
def market_alert():
    lines = [
        "📊 DELITE TRADE MARKET ALERT",
        ""
    ]

    for key, (ticker_symbol, display_name) in SYMBOLS.items():
        try:
            data = get_quote(ticker_symbol, display_name)
            change_pct = data.get("change_pct")

            if change_pct is None:
                signal = "NO DATA"
                change_text = "N/A"
            elif change_pct > 0:
                signal = "UP"
                change_text = f"+{change_pct:.2f}%"
            elif change_pct < 0:
                signal = "DOWN"
                change_text = f"{change_pct:.2f}%"
            else:
                signal = "FLAT"
                change_text = "0.00%"

            lines.append(
                f"{display_name}: {data['price']:.2f} | {change_text} | {signal}"
            )
        except Exception as e:
            lines.append(f"{display_name}: DATA ERROR")

    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    lines.extend([
        "",
        f"Time: {ist_now.strftime('%d-%m-%Y %I:%M:%S %p')} IST",
        "Source: Yahoo Finance via yfinance",
        "",
        "Paper-trading alert only. Not an execution signal."
    ])

    message = "\n".join(lines)

    try:
        telegram = send_telegram_message(message)
        return jsonify({
            "status": "sent",
            "message": message,
            "telegram": telegram
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route("/test-alert")
def test_alert():
    message = (
        "🚨 DELITE TRADE TEST ALERT\n\n"
        "Telegram connection is working.\n"
        "Market alert system is ready for testing."
    )

    try:
        result = send_telegram_message(message)

        return jsonify({
            "status": "sent",
            "telegram": result
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500
