from flask import Flask, jsonify, request
import yfinance as yf
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os
import json
import urllib.request
import urllib.parse
import requests

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




SESSION_WINDOWS = {
    "NIFTY": ("09:15:01", "15:40:00"),
    "SENSEX": ("09:15:01", "15:40:00"),
    "CRUDE MINI": ("00:00:00", "23:30:00"),
    "NAT GAS MINI": ("00:00:00", "23:30:00"),
}

def session_status(instrument):
    instrument = instrument.upper().strip()
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    if instrument not in SESSION_WINDOWS:
        return {"instrument": instrument, "open": False, "state": "UNKNOWN INSTRUMENT", "time_ist": now.isoformat()}
    start_text, end_text = SESSION_WINDOWS[instrument]
    current = now.time()
    start_t = datetime.strptime(start_text, "%H:%M:%S").time()
    end_t = datetime.strptime(end_text, "%H:%M:%S").time()
    if instrument in ("CRUDE MINI", "NAT GAS MINI"):
        is_open = current <= end_t
    else:
        is_open = start_t <= current <= end_t
    return {
        "instrument": instrument,
        "open": is_open,
        "state": "PAPER TRADING OPEN" if is_open else "TRADING LOCKED",
        "start_ist": start_text,
        "end_ist": end_text,
        "time_ist": now.isoformat(),
        "timezone": "Asia/Kolkata"
    }

@app.route("/session-status")
def session_status_route():
    instrument = urllib.parse.unquote(request.args.get("instrument", "NIFTY"))
    return jsonify(session_status(instrument))

def get_nse_option_quote(strike, option_type, expiry=None):
    strike = int(float(strike))
    option_type = option_type.upper().strip()
    if option_type not in ("CE", "PE"):
        raise ValueError("option_type must be CE or PE")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/option-chain"
    }
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers, timeout=10)
    response = session.get("https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY", headers=headers, timeout=10)
    response.raise_for_status()
    payload = response.json()
    expiry_dates = payload.get("records", {}).get("expiryDates", [])
    wanted_expiry = expiry or (expiry_dates[0] if expiry_dates else None)
    for item in payload.get("records", {}).get("data", []):
        if item.get("strikePrice") == strike and (not wanted_expiry or item.get("expiryDate") == wanted_expiry) and option_type in item:
            selected = item[option_type]
            return {
                "underlying": "NIFTY",
                "strike": strike,
                "option_type": option_type,
                "expiry": item.get("expiryDate"),
                "ltp": selected.get("lastPrice"),
                "change": selected.get("change"),
                "change_pct": selected.get("pChange"),
                "bid": selected.get("bidprice"),
                "ask": selected.get("askPrice"),
                "volume": selected.get("totalTradedVolume"),
                "open_interest": selected.get("openInterest"),
                "iv": selected.get("impliedVolatility"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "source": "NSE option chain"
            }
    raise RuntimeError("Requested NIFTY option contract was not found")

@app.route("/nifty-option")
def nifty_option():
    try:
        strike = request.args.get("strike")
        option_type = request.args.get("type", "CE")
        expiry = request.args.get("expiry")
        if not strike:
            return jsonify({"error": "strike is required"}), 400
        return jsonify(get_nse_option_quote(strike, option_type, expiry))
    except Exception as e:
        return jsonify({"error": str(e), "source": "NSE option chain"}), 502

ALERT_THRESHOLDS = {"nifty": 0.50, "sensex": 0.50, "crude": 1.00, "natgas": 1.00}


@app.route("/threshold-alert")
def threshold_alert():
    triggered = []

    for key, (ticker_symbol, display_name) in SYMBOLS.items():
        try:
            data = get_quote(ticker_symbol, display_name)
            change_pct = data.get("change_pct")
            threshold = ALERT_THRESHOLDS[key]

            if change_pct is not None and abs(change_pct) >= threshold:
                direction = "UP" if change_pct > 0 else "DOWN"
                sign = "+" if change_pct > 0 else ""
                triggered.append(
                    f"🚨 {display_name} {direction}\n"
                    f"Price: {data['price']:.2f}\n"
                    f"Change: {sign}{change_pct:.2f}%\n"
                    f"Threshold: {threshold:.2f}%"
                )
        except Exception:
            continue

    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))

    if not triggered:
        return jsonify({
            "status": "no_alert",
            "message": "No configured market threshold has been crossed.",
            "checked_at_ist": ist_now.isoformat()
        })

    message = (
        "⚡ DELITE TRADE THRESHOLD ALERT\n\n"
        + "\n\n".join(triggered)
        + f"\n\nTime: {ist_now.strftime('%d-%m-%Y %I:%M:%S %p')} IST"
        + "\nSource: Yahoo Finance via yfinance"
        + "\n\nPaper-trading alert only. Not an execution signal."
    )

    try:
        telegram = send_telegram_message(message)
        return jsonify({
            "status": "sent",
            "triggered": len(triggered),
            "message": message,
            "telegram": telegram
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


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
