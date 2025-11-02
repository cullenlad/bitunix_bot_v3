#!/usr/bin/env python3
import os, json, time, random, string, hashlib, csv
from decimal import Decimal, ROUND_DOWN
import requests
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_PATH = os.path.join(BASE_DIR, "status.csv")

BASE_URL = "https://fapi.bitunix.com"
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
GRID_LEVELS = int(os.getenv("GRID_LEVELS", "1"))
GRID_SPACING_PCT = Decimal(os.getenv("GRID_SPACING_PCT", "0.25"))
ACCOUNT_USDT = Decimal(os.getenv("ACCOUNT_USDT", "1000"))
ORDER_NOTIONAL_PCT = Decimal(os.getenv("ORDER_NOTIONAL_PCT", "0.07"))
MIN_QTY = Decimal(os.getenv("MIN_QTY", "0.001"))
LEVERAGE = Decimal(os.getenv("LEVERAGE", "2"))
MAX_GRID_NOTIONAL_USDT = Decimal(os.getenv("MAX_GRID_NOTIONAL_USDT", "400"))
DRY_RUN = os.getenv("LIVE", "0") != "1"

STATUS_POLL_SEC = int(os.getenv("STATUS_POLL_SEC", "60"))
TREND_WINDOW_MIN = int(os.getenv("TREND_WINDOW_MIN", "10"))
TREND_THRESHOLD_PCT = Decimal(os.getenv("TREND_THRESHOLD_PCT", "0.7"))

API_KEY = os.getenv("BITUNIX_API_KEY", "")
API_SECRET = os.getenv("BITUNIX_API_SECRET", "")
TIMEOUT = 10

def _now_ms(): return str(int(time.time() * 1000))
def _nonce(): return "".join(random.choices(string.ascii_letters + string.digits, k=32))
def _sha256_hex(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()
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

def change_leverage(symbol, leverage):
    nonce, ts = _nonce(), _now_ms()
    body = json.dumps({"symbol": symbol, "leverage": int(leverage), "marginCoin": "USDT"}, separators=(",", ":"))
    sign = _sign(nonce, ts, "", body)
    h = _headers(sign, nonce, ts)
    r = requests.post(BASE_URL + "/api/v1/futures/account/change_leverage", data=body, headers=h, timeout=TIMEOUT)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(j)
    return j

def truncate_qty(qty):
    return (Decimal(qty)).quantize(MIN_QTY, rounding=ROUND_DOWN)

def build_grid(px):
    grid = []
    for i in range(1, GRID_LEVELS + 1):
        pct = GRID_SPACING_PCT * i
        buy_px = (px * (Decimal("1") - pct / Decimal("100"))).quantize(Decimal("0.1"))
        sell_px = (px * (Decimal("1") + pct / Decimal("100"))).quantize(Decimal("0.1"))
        grid.append(("BUY", buy_px))
        grid.append(("SELL", sell_px))
    return grid

def place_limit(symbol, side, qty, price):
    nonce, ts = _nonce(), _now_ms()
    body = json.dumps({"symbol": symbol, "side": side, "price": str(price), "qty": str(qty), "tradeSide": "OPEN",
                       "orderType": "LIMIT", "effect": "GTC", "reduceOnly": False,
                       "clientId": f"grid_{int(time.time()*1000)}"}, separators=(",", ":"))
    sign = _sign(nonce, ts, "", body)
    h = _headers(sign, nonce, ts)
    r = requests.post(BASE_URL + "/api/v1/futures/trade/place_order", data=body, headers=h, timeout=TIMEOUT)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(j)
    return j.get("data", {})

def trend_guard(px_now):
    needed = max(1, int((TREND_WINDOW_MIN * 60) / max(1, STATUS_POLL_SEC)))
    prices = []
    try:
        with open(LOG_PATH) as f:
            for row in reversed(list(csv.reader(f))):
                if len(row) >= 2:
                    prices.append(Decimal(row[1]))
                    if len(prices) >= needed:
                        break
    except Exception:
        prices = []
    if len(prices) < needed:
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
        out = {"symbol": SYMBOL, "reference_price": str(px), "dry_run": DRY_RUN, "trend_blocked": True,
               "trend_avg": tg.get("avg"), "trend_change_pct": tg.get("change_pct"),
               "threshold_pct": str(TREND_THRESHOLD_PCT), "window_min": TREND_WINDOW_MIN}
n    open(os.path.join(BASE_DIR,"last_center.json"),"w").write(json.dumps({"symbol": SYMBOL, "center": str(px), "ts": int(time.time())}))
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
        notional = (qty * p)
        total_notional += notional
        orders.append({"side": side, "price": str(p), "qty": str(qty), "est_notional": str(notional)})

    out = {"symbol": SYMBOL, "reference_price": str(px), "dry_run": DRY_RUN, "grid_levels": GRID_LEVELS,
           "per_order_notional": str(per_order_notional), "total_grid_notional": str(total_notional),
           "max_grid_notional": str(MAX_GRID_NOTIONAL_USDT), "orders": orders}

    if total_notional > MAX_GRID_NOTIONAL_USDT:
        out["blocked"] = "total_notional_exceeds_cap"
n    open(os.path.join(BASE_DIR,"last_center.json"),"w").write(json.dumps({"symbol": SYMBOL, "center": str(px), "ts": int(time.time())}))
        print(json.dumps(out, indent=2))
        return

    if DRY_RUN:
n    open(os.path.join(BASE_DIR,"last_center.json"),"w").write(json.dumps({"symbol": SYMBOL, "center": str(px), "ts": int(time.time())}))
        print(json.dumps(out, indent=2))
        return

    if not API_KEY or not API_SECRET:
        raise SystemExit("missing api credentials")
    change_leverage(SYMBOL, int(LEVERAGE))
    placed = []
    for o in orders:
        res = place_limit(SYMBOL, o["side"], o["qty"], o["price"])
        placed.append({**o, "order": res})
        time.sleep(0.1)
    out["placed"] = placed
n    open(os.path.join(BASE_DIR,"last_center.json"),"w").write(json.dumps({"symbol": SYMBOL, "center": str(px), "ts": int(time.time())}))
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
