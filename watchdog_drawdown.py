#!/usr/bin/env python3
import os, json, time, random, string, subprocess, sys, hashlib
from decimal import Decimal
import requests
from dotenv import load_dotenv
load_dotenv()

BASE_URL = "https://fapi.bitunix.com"
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
API_KEY = os.getenv("BITUNIX_API_KEY", "")
API_SECRET = os.getenv("BITUNIX_API_SECRET", "")
LIVE = os.getenv("LIVE", "0") == "1"
MAX_DRAWDOWN = Decimal(os.getenv("MAX_DRAWDOWN_USDT", "50"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SEC", "30"))
TIMEOUT = 10

def _now_ms(): return str(int(time.time()*1000))
def _nonce(): return "".join(random.choices(string.ascii_letters+string.digits, k=32))
def _sha256_hex(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()
def _sign(nonce, ts, qp, body):
    digest = _sha256_hex(nonce + ts + API_KEY + qp + body)
    return _sha256_hex(digest + API_SECRET)
def _headers(sign, nonce, ts):
    return {"api-key": API_KEY, "nonce": nonce, "timestamp": ts, "sign": sign, "language": "en-US", "Content-Type": "application/json"}

def _get(path, params):
    qp = "".join([f"{k}{params[k]}" for k in sorted(params.keys())])
    nonce, ts = _nonce(), _now_ms()
    sign = _sign(nonce, ts, qp, "")
    r = requests.get(BASE_URL + path, params=params, headers=_headers(sign, nonce, ts), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def fetch_pnl():
    # attempt 1: positions with symbol + marginCoin
    params = {"symbol": SYMBOL, "marginCoin": "USDT"}
    try:
        j = _get("/api/v1/futures/account/positions", params)
        if j.get("code") == 0 and j.get("data") is not None:
            total = Decimal("0")
            for pos in j.get("data") or []:
                total += Decimal(str(pos.get("unrealisedPnl", "0")))
            return total
    except Exception:
        pass
    # attempt 2: positions with only marginCoin
    params2 = {"marginCoin": "USDT"}
    try:
        j = _get("/api/v1/futures/account/positions", params2)
        if j.get("code") == 0 and j.get("data") is not None:
            total = Decimal("0")
            for pos in j.get("data") or []:
                if SYMBOL and pos.get("symbol") and pos["symbol"] != SYMBOL:
                    continue
                total += Decimal(str(pos.get("unrealisedPnl", "0")))
            return total
    except Exception:
        pass
    # attempt 3: quiet failure (treat as 0 to avoid spam)
    return Decimal("0")

def kill():
    print(">>> Triggering killswitch due to drawdown breach...")
    subprocess.run(["python", "killswitch.py"], check=False)

def main():
    if not LIVE:
        print("LIVE=0 -> watchdog inactive; exiting.")
        sys.exit(0)
    if not API_KEY or not API_SECRET:
        print("Missing API credentials; exiting.")
        sys.exit(1)
    last_err_shown = False
    while True:
        try:
            pnl = fetch_pnl()
            print(f"[{time.strftime('%H:%M:%S')}] unrealisedPnL={pnl}")
            if pnl < -MAX_DRAWDOWN:
                kill()
                break
            last_err_shown = False
        except Exception as e:
            if not last_err_shown:
                print("watchdog warning: transient error; will retry")
                last_err_shown = True
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
