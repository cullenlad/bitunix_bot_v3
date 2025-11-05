#!/usr/bin/env python3
import os, json, time, hashlib, random, string, logging
from grid_guard import decision as grid_guard_decision
from grid_guard import csv_read_band as _read_csv_band
from killswitch import cancel_all_orders
from grid_guard import guard_pause_if_outside as _guard_pause_if_outside
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv


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

LOG_FILE = "/opt/bitunix-bot/logs/gridbot.log"
ORDERS_FILE = "/opt/bitunix-bot/orders.csv"

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
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

def _bot_cancel_all_orders():
    url = f"{BASE_URL}/api/v1/futures/trade/cancel_all"
    body_dict = {"symbol": SYMBOL}
    body = json.dumps(body_dict, separators=(",", ":"))
    nonce, ts = _nonce(), _timestamp()
    sign = _sign(nonce, ts, body)
    headers = _headers(sign, nonce, ts)
    try:
        r = requests.post(url, headers=headers, data=body, timeout=10)
        logging.info(f"Cancel all => {r.text}")
        return r.json()
    except Exception as e:
        logging.error(f"cancel_all_orders() failed: {e}")
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

    if not DRY_RUN:
        cancel_all_orders()

    logging.info(f"{mode} GRIDBOT for {SYMBOL} started")
    spacing = GRID_SPACING_PCT / Decimal("100")
    notional = ACCOUNT_USDT * ORDER_NOTIONAL_PCT
    qty = (notional / price).quantize(MIN_QTY, rounding=ROUND_DOWN)

    prices = []
    for i in range(1, GRID_LEVELS + 1):
        prices.append((price * (1 - spacing * i)).quantize(Decimal("0.01")))
        prices.append((price * (1 + spacing * i)).quantize(Decimal("0.01")))

    logging.info(f"Placing {len(prices)} orders around mid={price}")
    lo, hi = _read_csv_band(ORDERS_FILE)
    try:
        mt = os.path.getmtime(ORDERS_FILE)
        max_age = int(os.getenv("GRID_GUARD_REQUIRE_RECENT_MINUTES","180"))*60
        if time.time() - mt > max_age:
            lo = hi = None
    except Exception:
        pass
    if lo is not None and hi is not None:
        print(f"DEBUG csv_band=({lo},{hi})")
        if grid_guard_decision(float(price), float(lo), float(hi)) == "pause":
            print(f"DEBUG GUARD-PAUSED by csv band mid={price} band=({lo},{hi})")
            return
    print(f"DEBUG mid={price} band=({min(prices)},{max(prices)})")
    if _guard_pause_if_outside(float(price), [float(x) for x in prices]):
        logging.info(f"[GUARD] paused outside band: mark={price}, band=({min(prices)},{max(prices)})")
        print(f"DEBUG GUARD-PAUSED mid={price} band=({min(prices)},{max(prices)})")
        return

    for p in prices:
        side = "BUY" if p < price else "SELL"
        if DRY_RUN:
            logging.info(f"[DRY RUN] {side.lower()} {qty} {SYMBOL} @ {p}")
        else:
            result = place_order(side, qty, p)
            logging.info(f"Order API response: {result}")
            try:
                with open(ORDERS_FILE, "a") as f:
                    f.write(f"{datetime.now(timezone.utc).isoformat()},{mode},{SYMBOL},{side},{p},{qty},{json.dumps(result)}\n")
            except Exception:
                pass
    logging.info("Grid placement complete.")

if __name__ == "__main__":
    run_grid("LIVE" if not DRY_RUN else "DRY-RUN")

# def _guard_pause_if_outside(mark_price: float, grid_prices: list[float]) -> bool:
#     if not grid_prices:
#         return False

def _read_csv_band(path: str):
    try:
        lo = None
        hi = None
        with open(path, "r") as f:
            first = True
            for line in f:
                if first:
                    first = False
                    continue
                parts = line.strip().split(",")
                if len(parts) < 5:
                    continue
                try:
                    p = float(parts[4])
                except Exception:
                    continue
                if lo is None or p < lo:
                    lo = p
                if hi is None or p > hi:
                    hi = p
        return lo, hi
    except Exception:
        return None, None
