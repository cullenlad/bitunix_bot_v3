#!/usr/bin/env python3
import os, json, time, random, string, hashlib, sys
import requests
from dotenv import load_dotenv
load_dotenv()

BASE_URL = "https://fapi.bitunix.com"
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
API_KEY = os.getenv("BITUNIX_API_KEY", "")
API_SECRET = os.getenv("BITUNIX_API_SECRET", "")
LIVE = os.getenv("LIVE", "0") == "1"
TIMEOUT = 10

def _now_ms(): return str(int(time.time()*1000))
def _nonce(): return "".join(random.choices(string.ascii_letters+string.digits, k=32))
def _sha256_hex(s): import hashlib; return hashlib.sha256(s.encode("utf-8")).hexdigest()
def _sign(nonce, ts, qp, body):
    digest = _sha256_hex(nonce + ts + API_KEY + qp + body)
    return _sha256_hex(digest + API_SECRET)
def _headers(sign, nonce, ts):
    return {"api-key": API_KEY, "nonce": nonce, "timestamp": ts, "sign": sign, "language": "en-US", "Content-Type": "application/json"}
def _post(path, body_obj):
    nonce, ts = _nonce(), _now_ms()
    body = json.dumps(body_obj or {}, separators=(",",":"))
    sign = _sign(nonce, ts, "", body)
    r = requests.post(BASE_URL + path, data=body, headers=_headers(sign, nonce, ts), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def main():
    if not LIVE:
        print({"error": "LIVE is 0; set LIVE=1 in .env to arm killswitch"})
        sys.exit(1)
    if not API_KEY or not API_SECRET:
        print({"error": "missing api credentials"})
        sys.exit(1)

    out = {"cancel_all_orders": None, "flash_close": None}
    try:
        # Some futures APIs support this endpoint; if BitUnix rejects it, we just continue.
        out["cancel_all_orders"] = _post("/api/v1/futures/trade/cancel_all_orders", {"symbol": SYMBOL})
    except Exception as e:
        out["cancel_all_orders"] = {"error": str(e)}

    time.sleep(0.2)
    try:
        out["flash_close"] = _post("/api/v1/futures/trade/flash_close_position", {"symbol": SYMBOL})
    except Exception as e:
        out["flash_close"] = {"error": str(e)}

    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
