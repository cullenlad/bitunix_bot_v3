#!/usr/bin/env python3
import os, json, time, hashlib, random, string, logging
from decimal import Decimal, ROUND_DOWN
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

BASE_URL = "https://fapi.bitunix.com"
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
GRID_LEVELS = int(os.getenv("GRID_LEVELS", "4"))
GRID_SPACING_PCT = Decimal(os.getenv("GRID_SPACING_PCT", "0.2"))
ACCOUNT_USDT = Decimal(os.getenv("ACCOUNT_USDT", "1000"))
ORDER_NOTIONAL_PCT = Decimal(os.getenv("ORDER_NOTIONAL_PCT", "0.02"))
MIN_QTY = Decimal(os.getenv("MIN_QTY", "0.001"))
DRY_RUN = os.getenv("LIVE", "0") != "1"

API_KEY = os.getenv("BITUNIX_API_KEY")
API_SECRET = os.getenv("BITUNIX_API_SECRET")

logging.basicConfig(filename="/opt/bitunix-bot/logs/gridbot.log",
                    level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

def _nonce():
    return "".join(random.choices(string.ascii_letters + string.digits, k=32))

def _timestamp():
    return str(int(time.time() * 1000))

def _sign(nonce, ts, body):
    digest = hashlib.sha256((nonce + ts + API_KEY + body).encode()).hexdigest()
    return hashlib.sha256((digest + API_SECRET).encode()).hexdigest()

def _headers(sign, nonce, ts):
    return {
        "api-key": API_KEY,
        "sign": sign,
        "nonce": nonce,
        "timestamp": ts,
        "language": "en-US",
        "Content-Type": "application/json"
    }

def get_price():
    try:
        r = requests.get(f"{BASE_URL}/api/v1/futures/market/tickers",
                         params={"symbols": SYMBOL}, timeout=10)
        data = r.json()
        return Decimal(data["data"][0]["lastPrice"])
    except Exception as e:
        logging.error(f"get_price() failed: {e}")
        return None

def place_order(side, qty, price=None, trade_side="OPEN", order_type="LIMIT"):
    url = f"{BASE_URL}/api/v1/futures/trade/place_order"
    body_dict = {"symbol": SYMBOL, "side": side, "qty": str(qty),
                 "tradeSide": trade_side, "orderType": order_type}
    if order_type == "LIMIT" and price is not None:
        body_dict["price"] = str(price)
        body_dict["effect"] = "GTC"
    body = json.dumps(body_dict, separators=(",", ":"))
    nonce, ts = _nonce(), _timestamp()
    sign = _sign(nonce, ts, body)
    headers = _headers(sign, nonce, ts)
    try:
        r = requests.post(url, headers=headers, data=body, timeout=10)
        logging.info(f"POST /api/v1/futures/trade/place_order => {r.text}")
        return r.json()
    except Exception as e:
        logging.error(f"place_order() failed: {e}")
        return None

def run_grid(mode="LIVE"):
    price = get_price()
    if price is None:
        logging.error("Price fetch failed, aborting.")
        return
    logging.info(f"{mode} GRIDBOT for {SYMBOL} started")
    spacing = GRID_SPACING_PCT / Decimal("100")
    notional = ACCOUNT_USDT * ORDER_NOTIONAL_PCT
    qty = (notional / price).quantize(MIN_QTY, rounding=ROUND_DOWN)

    prices = []
    for i in range(1, GRID_LEVELS + 1):
        prices.append((price * (1 - spacing * i)).quantize(Decimal("0.01")))
        prices.append((price * (1 + spacing * i)).quantize(Decimal("0.01")))

    logging.info(f"Placing {len(prices)} orders around mid={price}")
    for p in prices:
        side = "BUY" if p < price else "SELL"
        if DRY_RUN:
            logging.info(f"[DRY RUN] {side.lower()} {qty} {SYMBOL} @ {p}")
        else:
            result = place_order(side, qty, p)
            logging.info(f"Order API response: {result}")
            try:
                with open("/opt/bitunix-bot/orders.csv", "a") as f:
                    f.write(f"{datetime.utcnow().isoformat()},{mode},{SYMBOL},{side},{p},{qty},{json.dumps(result)}\n")
            except Exception:
                pass
    logging.info("Grid placement complete.")

if __name__ == "__main__":
    run_grid("LIVE" if not DRY_RUN else "DRY-RUN")
