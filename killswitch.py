#!/usr/bin/env python3
import os, requests, json, logging, time, random, string, hashlib
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://fapi.bitunix.com"
API_KEY = os.getenv("BITUNIX_API_KEY")
API_SECRET = os.getenv("BITUNIX_API_SECRET")
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
LIVE = os.getenv("LIVE", "0") == "1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/opt/bitunix-bot/logs/killswitch.log"),
        logging.StreamHandler()
    ]
)

def _sha256_hex(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _nonce():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

def cancel_all_orders(symbol=None):
    if not symbol:
        symbol = os.getenv("SYMBOL","BTCUSDT")
    import time, json, requests, logging
    for attempt in range(1, 4):
        nonce = _nonce()
        ts = str(int(time.time() * 1000))
        body = {"symbol": symbol}
        digest = _sha256_hex(nonce + ts + API_KEY + json.dumps(body))
        sign = _sha256_hex(digest + API_SECRET)
        headers = {
            "api-key": API_KEY,
            "sign": sign,
            "nonce": nonce,
            "timestamp": ts,
            "language": "en-US",
            "Content-Type": "application/json"
        }
        try:
            r = requests.post(f"{BASE_URL}/api/v1/futures/trade/cancel_all", headers=headers, json=body, timeout=3)
            logging.info({"killswitch_http": r.status_code, "attempt": attempt})
            txt = r.text
            logging.info({"killswitch_body": txt})
            try:
                data = r.json()
            except Exception:
                data = {"raw": txt}
            if r.status_code == 200 and isinstance(data, dict) and str(data.get("code")) == "0":
                return json.dumps(data)
            if attempt < 3:
                time.sleep(0.7 * attempt)
                continue
            return json.dumps(data)
        except Exception as e:
            logging.error({"killswitch_error": str(e), "attempt": attempt})
            if attempt < 3:
                time.sleep(0.7 * attempt)
                continue
            return json.dumps({"code": -1, "msg": str(e)})
