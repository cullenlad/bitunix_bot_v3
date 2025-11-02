#!/usr/bin/env python3
import os, json, time, random, string, hashlib
from decimal import Decimal, ROUND_DOWN
import requests
from dotenv import load_dotenv
load_dotenv()

BASE_URL = "https://fapi.bitunix.com"
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
GRID_LEVELS = int(os.getenv("GRID_LEVELS", "12"))
GRID_SPACING_PCT = Decimal(os.getenv("GRID_SPACING_PCT", "0.25"))
ACCOUNT_USDT = Decimal(os.getenv("ACCOUNT_USDT", "1000"))
ORDER_NOTIONAL_PCT = Decimal(os.getenv("ORDER_NOTIONAL_PCT", "0.02"))
MIN_QTY = Decimal(os.getenv("MIN_QTY", "0.001"))
DRY_RUN = os.getenv("LIVE", "0") != "1"

API_KEY = os.getenv("BITUNIX_API_KEY", "")
API_SECRET = os.getenv("BITUNIX_API_SECRET", "")
TIMEOUT = 10

def _now_ms():
    return str(int(time.time() * 1000))

def _nonce():
    return "".join(random.choices(string.ascii_letters + string.digits, k=32))

def _sha256_hex(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _sign(nonce, ts, qp, body):
    digest = _sha256_hex(nonce + ts + API_KEY + qp + body)
    return _sha256_hex(digest + API_SECRET)

def _headers(sign, nonce, ts):
    return {"api-key": API_KEY, "nonce": nonce, "timestamp": ts, "sign": sign, "language": "en-US", "Content-Type": "application/json"}

def get_last_price(symbol):
    r = requests.get(BASE_URL + "/api/v1/futures/market/tickers", params={"symbols": symbol}, timeout=TIMEOUT)
    r.raise_for_status()
    j = r.json()
    rows = j.get("data") or []
    for row in rows:
        if row.get("symbol") == symbol:
            return Decimal(str(row["lastPrice"]))
    raise RuntimeError("ticker not found")

def truncate_qty(qty):
    return (Decimal(qty)).quantize(MIN_QTY, rounding=ROUND_DOWN)

def build_grid(px):
    grid = []
    for i in range(1, GRID_LEVELS + 1):
        pct = GRID_SPACING_PCT * i
        buy_px = (px * (Decimal("1.0") - pct/Decimal("100"))).quantize(Decimal("0.1"))
        sell_px = (px * (Decimal("1.0") + pct/Decimal("100"))).quantize(Decimal("0.1"))
        grid.append(("BUY", buy_px))
        grid.append(("SELL", sell_px))
    return grid

def place_limit(symbol, side, qty, price):
    nonce = _nonce()
    ts = _now_ms()
    body = json.dumps({
        "symbol": symbol,
        "side": side,
        "price": str(price),
        "qty": str(qty),
        "tradeSide": "OPEN",
        "orderType": "LIMIT",
        "effect": "GTC",
        "reduceOnly": False,
        "clientId": f"grid_{int(time.time()*1000)}"
    }, separators=(",",":"))
    sign = _sign(nonce, ts, "", body)
    h = _headers(sign, nonce, ts)
    r = requests.post(BASE_URL + "/api/v1/futures/trade/place_order", data=body, headers=h, timeout=TIMEOUT)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(j)
    return j.get("data", {})

def main():
    px = get_last_price(SYMBOL)
    grid = build_grid(px)
    notional_per_order = ACCOUNT_USDT * ORDER_NOTIONAL_PCT
    placed = []
    for side, p in grid:
        qty = truncate_qty((notional_per_order / p) * Decimal("2"))
        if DRY_RUN:
            placed.append({"side": side, "price": str(p), "qty": str(qty), "dry_run": True})
        else:
            if not API_KEY or not API_SECRET:
                raise SystemExit("missing api credentials; set LIVE=0 or provide keys in .env")
            res = place_limit(SYMBOL, side, str(qty), str(p))
            placed.append({"side": side, "price": str(p), "qty": str(qty), "order": res})
        time.sleep(0.1)
    print(json.dumps({"symbol": SYMBOL, "reference_price": str(px), "dry_run": DRY_RUN, "orders": placed}, indent=2))

if __name__ == "__main__":
    main()
