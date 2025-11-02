#!/usr/bin/env python3
import os, time, hmac, hashlib, json, requests
from decimal import Decimal

BASE_DIR = os.path.dirname(__file__)
ENV_PATH = os.path.join(BASE_DIR, ".env")

def get_env(k, default=None, t=str):
    for line in open(ENV_PATH):
        if line.strip().startswith(f"{k}="):
            return t(line.strip().split("=", 1)[1])
    return default

API_KEY = get_env("BITUNIX_API_KEY", "")
API_SECRET = get_env("BITUNIX_API_SECRET", "")
ACCOUNT_USDT = Decimal(get_env("ACCOUNT_USDT", "1000"))
SYMBOL = get_env("SYMBOL", "BTCUSDT")
GRID_LEVELS = int(get_env("GRID_LEVELS", "1"))
GRID_SPACING_PCT = Decimal(get_env("GRID_SPACING_PCT", "0.25"))
ORDER_NOTIONAL_PCT = Decimal(get_env("ORDER_NOTIONAL_PCT", "0.05"))
MIN_QTY = Decimal(get_env("MIN_QTY", "0.001"))
LEVERAGE = Decimal(get_env("LEVERAGE", "2"))
MAX_GRID_NOTIONAL_USDT = Decimal(get_env("MAX_GRID_NOTIONAL_USDT", "400"))
LIVE = bool(int(get_env("LIVE", "0")))
TREND_WINDOW_MIN = int(get_env("TREND_WINDOW_MIN", "30"))
TREND_THRESHOLD_PCT = Decimal(get_env("TREND_THRESHOLD_PCT", "0.3"))

BASE_URL = "https://fapi.bitunix.com"

def sign(params):
    query = "&".join(f"{k}={params[k]}" for k in sorted(params))
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    return {**params, "sign": sig}

def api(method, path, params=None, auth=False):
    url = f"{BASE_URL}{path}"
    headers = {"X-BX-APIKEY": API_KEY} if auth else {}
    r = requests.request(method, url, headers=headers, params=params, timeout=10)
    return r.json()

def get_last_price(symbol):
    j = api("GET", f"/api/v1/market/ticker", {"symbol": symbol})
    return Decimal(j["data"]["lastPrice"])

def truncate_qty(qty):
    return Decimal(str(qty)).quantize(Decimal("0.000"))

def change_leverage(symbol, lev):
    if not LIVE:
        return {"ok": True}
    p = sign({"symbol": symbol, "leverage": lev})
    return api("POST", "/api/v1/futures/adjustLeverage", p, True)

def place_limit(symbol, side, qty, price):
    if not LIVE:
        return {"ok": True, "dry_run": True}
    p = sign({
        "symbol": symbol,
        "side": side,
        "price": price,
        "qty": qty,
        "type": "LIMIT",
        "timeInForce": "GTC",
    })
    j = api("POST", "/api/v1/futures/order/place", p, True)
    if j.get("code") != 0:
        raise RuntimeError(j)
    return {"orderId": j["data"]["orderId"], "clientId": j["data"]["clientId"]}

def build_grid(ref):
    levels = []
    for i in range(1, GRID_LEVELS + 1):
        d = GRID_SPACING_PCT * Decimal(i) / Decimal(100)
        levels.append(("BUY", ref * (1 - d)))
        levels.append(("SELL", ref * (1 + d)))
    return levels

def trend_guard(px_now):
    try:
        candles = api("GET", "/api/v1/market/kline", {
            "symbol": SYMBOL,
            "interval": "1m",
            "limit": TREND_WINDOW_MIN
        })["data"]
        prices = [Decimal(c["close"]) for c in candles]
    except Exception:
        prices = []
    if len(prices) < TREND_WINDOW_MIN:
        return {"ok": True, "reason": "not_enough_history"}
    avg = sum(prices) / Decimal(len(prices))
    change_pct = (px_now - avg) / avg * Decimal("100")
    if abs(change_pct) > TREND_THRESHOLD_PCT:
        return {"ok": False, "avg": str(avg), "change_pct": str(change_pct)}
    return {"ok": True, "avg": str(avg), "change_pct": str(change_pct)}

def main():
    px = get_last_price(SYMBOL)
    tg = trend_guard(px)
    if not tg["ok"]:
        out = {"symbol": SYMBOL, "reference_price": str(px), "dry_run": not LIVE,
               "trend_blocked": True, "trend_avg": tg.get("avg"),
               "trend_change_pct": tg.get("change_pct"),
               "threshold_pct": str(TREND_THRESHOLD_PCT)}
        open(os.path.join(BASE_DIR,"last_center.json"),"w").write(json.dumps({"symbol":SYMBOL,"center":str(px),"ts":int(time.time())}))
        print(json.dumps(out, indent=2))
        return

    grid = build_grid(px)
    per_order_notional = ACCOUNT_USDT * ORDER_NOTIONAL_PCT
    orders = []
    total_notional = Decimal("0")

    for side, p in grid:
        qty = truncate_qty((per_order_notional / p) * LEVERAGE)
        if qty <= 0:
            continue
        notional = qty * p
        total_notional += notional
        orders.append({"side": side, "price": str(p), "qty": str(qty), "est_notional": str(notional)})

    out = {"symbol": SYMBOL, "reference_price": str(px), "dry_run": not LIVE,
           "grid_levels": GRID_LEVELS,
           "per_order_notional": str(per_order_notional),
           "total_grid_notional": str(total_notional),
           "max_grid_notional": str(MAX_GRID_NOTIONAL_USDT),
           "orders": orders}

    if total_notional > MAX_GRID_NOTIONAL_USDT:
        out["blocked"] = "total_notional_exceeds_cap"
        open(os.path.join(BASE_DIR,"last_center.json"),"w").write(json.dumps({"symbol":SYMBOL,"center":str(px),"ts":int(time.time())}))
        print(json.dumps(out, indent=2))
        return

    if not LIVE:
        open(os.path.join(BASE_DIR,"last_center.json"),"w").write(json.dumps({"symbol":SYMBOL,"center":str(px),"ts":int(time.time())}))
        print(json.dumps(out, indent=2))
        return

    if not API_KEY or not API_SECRET:
        raise SystemExit("missing api credentials")

    change_leverage(SYMBOL, int(LEVERAGE))
    placed = []
    for o in orders:
        res = place_limit(SYMBOL, o["side"], o["qty"], o["price"])
        placed.append({**o, "order": res})
        time.sleep(0.2)
    out["placed"] = placed

    open(os.path.join(BASE_DIR,"last_center.json"),"w").write(json.dumps({"symbol":SYMBOL,"center":str(px),"ts":int(time.time())}))
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
