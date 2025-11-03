#!/usr/bin/env python3
import os, json, time, random, string, hashlib, requests
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
load_dotenv()

# === CONFIG ===
BASE_URL = "https://fapi.bitunix.com"
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
GRID_LEVELS = int(os.getenv("GRID_LEVELS", "20"))
GRID_STEP_PCT = Decimal(os.getenv("GRID_STEP_PCT", "0.25"))
ACCOUNT_USDT = Decimal(os.getenv("ACCOUNT_USDT", "1000"))
ORDER_NOTIONAL_PCT = Decimal(os.getenv("ORDER_NOTIONAL_PCT", "0.02"))
MIN_QTY = Decimal(os.getenv("MIN_QTY", "0.001"))
LEVERAGE = int(os.getenv("LEVERAGE", "10"))
LIVE = os.getenv("LIVE", "0") == "1"

API_KEY = os.getenv("BITUNIX_API_KEY", "")
API_SECRET = os.getenv("BITUNIX_API_SECRET", "")
TIMEOUT = 10

# === SIGNING HELPERS ===
def _now_ms(): return str(int(time.time() * 1000))
def _nonce(): return "".join(random.choices(string.ascii_letters + string.digits, k=32))
def _sha256_hex(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()
def _sign(nonce, ts, qp, body):
    digest = _sha256_hex(nonce + ts + API_KEY + qp + body)
    return _sha256_hex(digest + API_SECRET)
def _headers(sign, nonce, ts):
    return {
        "api-key": API_KEY,
        "nonce": nonce,
        "timestamp": ts,
        "sign": sign,
        "language": "en-US",
        "Content-Type": "application/json",
    }

# === HTTP HELPERS ===
def _get(path, params=None):
    r = requests.get(BASE_URL + path, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def _post(path, body_obj):
    nonce, ts = _nonce(), _now_ms()
    body = json.dumps(body_obj or {}, separators=(",", ":"))
    sign = _sign(nonce, ts, "", body)
    r = requests.post(BASE_URL + path, data=body, headers=_headers(sign, nonce, ts), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

# === TRADING HELPERS ===
def get_last_price(symbol):
    j = _get("/api/v1/futures/market/tickers", {"symbols": symbol})
    rows = j.get("data") or []
    for row in rows:
        if row.get("symbol") == symbol:
            return Decimal(str(row["lastPrice"]))
    raise RuntimeError(f"Ticker not found for {symbol}: {j}")

def change_leverage(symbol, leverage):
    body = {
        "symbol": symbol,
        "leverage": int(leverage),
        "marginCoin": "USDT"
    }
    try:
        j = _post("/api/v1/futures/account/change_leverage", body)
        print("Leverage API response:", j)
        if j.get("code") == 0:
            print(f"✓ Leverage set to {leverage}x for {symbol}")
            return j
        else:
            raise RuntimeError(j)
    except Exception as e:
        raise RuntimeError({"error": str(e), "body": body})

def truncate_qty(qty):
    q = (Decimal(qty)).quantize(MIN_QTY, rounding=ROUND_DOWN)
    return q if q >= MIN_QTY else MIN_QTY

def place_limit(symbol, side, qty, price):
    body = {
        "symbol": symbol,
        "side": side,               # "BUY" | "SELL"
        "price": str(price),
        "qty": str(qty),
        "tradeSide": "OPEN",
        "orderType": "LIMIT",
        "effect": "GTC",
        "reduceOnly": False,
        "clientId": f"grid_{int(time.time()*1000)}",
    }
    if not LIVE:
        return {"dry_run": True, "body": body}
    j = _post("/api/v1/futures/trade/place_order", body)
    if j.get("code") != 0:
        raise RuntimeError({"resp": j, "sent": body})
    return j.get("data", {})

def build_grid(px):
    grid = []
    for i in range(1, GRID_LEVELS + 1):
        pct = GRID_STEP_PCT * i
        buy_px = (px * (Decimal("1.0") - pct/Decimal("100"))).quantize(Decimal("0.1"))
        sell_px = (px * (Decimal("1.0") + pct/Decimal("100"))).quantize(Decimal("0.1"))
        grid.append(("BUY", buy_px))
        grid.append(("SELL", sell_px))
    return grid

def main():
    if not API_KEY or not API_SECRET:
        raise SystemExit("Missing BITUNIX_API_KEY / BITUNIX_API_SECRET in .env")
    px = get_last_price(SYMBOL)
    print(f"Current {SYMBOL} price: {px}")
    try:
        change_leverage(SYMBOL, LEVERAGE)
    except Exception as e:
        print(f"Leverage change failed (continuing): {e}")
    grid = build_grid(px)
    notional_per_order = ACCOUNT_USDT * ORDER_NOTIONAL_PCT
    placed = []
    for side, p in grid:
        qty = truncate_qty(notional_per_order / p)
        try:
            res = place_limit(SYMBOL, side, str(qty), str(p))
            placed.append({"side": side, "price": str(p), "qty": str(qty), "result": res})
            print(f"{side} {qty} @ {p} → {res}")
        except Exception as e:
            print(f"Order error: {e}")
        time.sleep(0.08)
    print(json.dumps({"symbol": SYMBOL, "ref_price": str(px), "orders": placed, "live": LIVE}, indent=2))

if __name__ == "__main__":
    main()
