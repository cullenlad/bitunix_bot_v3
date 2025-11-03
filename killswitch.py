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

def cancel_all_orders(symbol):
    nonce = _nonce()
    ts = str(int(time.time() * 1000))
    body = json.dumps({"symbol": symbol})
    digest = _sha256_hex(nonce + ts + API_KEY + body)
    sign = _sha256_hex(digest + API_SECRET)
    headers = {
        "api-key": API_KEY,
        "sign": sign,
        "nonce": nonce,
        "timestamp": ts,
        "language": "en-US",
        "Content-Type": "application/json"
    }
    r = requests.post(f"{BASE_URL}/api/v1/futures/trade/cancel_all", headers=headers, data=body)
    return r.text

if not LIVE:
    logging.info({"error": "LIVE is 0; set LIVE=1 in .env to arm killswitch"})
else:
    logging.info(f"Executing killswitch for {SYMBOL}")
    result = cancel_all_orders(SYMBOL)
    logging.info({"response": result})
