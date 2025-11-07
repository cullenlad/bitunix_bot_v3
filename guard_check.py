import json
def _pick_mark(obj):
    d = obj.get('data') if isinstance(obj, dict) else None
    if isinstance(d, list) and d:
        d = d[0]
    if isinstance(d, dict):
        for k in ('markPrice','price','last','indexPrice','lastPrice'):
            v = d.get(k)
            if v not in (None, ''):
                try: return float(v)
                except: pass
    return None

import os, json, sys, requests
from dotenv import load_dotenv

load_dotenv()

symbol = os.getenv("SYMBOL", "BTCUSDT")
grid_spacing = float(os.getenv("GRID_SPACING_PCT", "0.005"))
buf = float(os.getenv("GRID_GUARD_BUFFER_PCT", "0.002"))
last_center_path = os.getenv("LAST_CENTER_PATH", "/opt/bitunix-bot/last_center.json")
panel_user = os.getenv("PANEL_USER")
panel_pass = os.getenv("PANEL_PASS")
panel_port = os.getenv("PORT", "8080")

def get_mark_via_panel():
    if not (panel_user and panel_pass and panel_port):
        raise RuntimeError("panel auth/port missing")
    url = f"http://127.0.0.1:{panel_port}/status"
    r = requests.post(url, auth=(panel_user, panel_pass), timeout=10)
    r.raise_for_status()
    j = r.json()
    # expecting something like {"symbol":"BTCUSDT","mark":100123.45,...}
    if "mark" in j:
        return float(j["mark"])
    # fallback: try common keys
    for k in ("markPrice","indexPrice","lastPrice","price"):
        if k in j:
            return float(j[k])
    raise RuntimeError("panel /status returned no mark price")

def get_mark_via_bitunix():
    url = "https://fapi.bitunix.com/api/v1/futures/market/tickers"
    r = requests.get(url, params={"symbol": symbol}, timeout=10)
    r.raise_for_status()
    j = r.json()
    # try to find a row for our symbol
    data = j.get("data") or []
    row = None
    if isinstance(data, list):
        for d in data:
            if str(d.get("symbol")).upper() == symbol.upper():
                row = d
                break
    elif isinstance(data, dict) and str(data.get("symbol")).upper() == symbol.upper():
        row = data
    if not row:
        raise RuntimeError("ticker not found for symbol")
    for k in ("markPrice","indexPrice","lastPrice","price"):
        if k in row and row[k] is not None:
            return float(row[k])
    raise RuntimeError("no price fields in ticker")

def get_mark():
    try:
        return get_mark_via_panel()
    except Exception:
        return get_mark_via_bitunix()

def get_last_center(path: str) -> float:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r") as f:
        j = json.load(f)
    if isinstance(j, dict) and "center" in j:
        return float(j["center"])
    return float(j)

try:
    mark = get_mark()
    mid  = get_last_center(last_center_path)
except Exception as e:
    print(f"guard: skip ({e})")
    sys.exit(0)

low = mid * (1 - grid_spacing)
high = mid * (1 + grid_spacing)
low_buf = low * (1 - buf)
high_buf = high * (1 + buf)

print(f"guard: symbol={symbol} mark={mark:.2f} mid={mid:.2f} band=({low:.2f},{high:.2f}) buf=({low_buf:.2f},{high_buf:.2f})")

if mark < low_buf or mark > high_buf:
    print("outside")
    sys.exit(42)

print("inside")
sys.exit(0)
