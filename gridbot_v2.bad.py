import os, time, hmac, hashlib, json, requests, logging, math, random, string
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("/opt/bitunix-bot/.env")

API_KEY = os.getenv("BITUNIX_API_KEY")
API_SECRET = os.getenv("BITUNIX_API_SECRET")
BASE_URL = "https://fapi.bitunix.com"
SYMBOL = "BTCUSDT"
MARGIN = "USDT"

LOG_DIR = "/opt/bitunix-bot/logs"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(filename=f"{LOG_DIR}/gridbot.log",
                    level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

def sign_request(endpoint, payload):
    ts = str(int(time.time() * 1000))
    nonce = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    clean = endpoint[1:] if endpoint.startswith("/") else endpoint
    body = json.dumps(payload, separators=(',', ':'))
    pre_sign = f"{ts}{nonce}POST{clean}{body}"
    sig = hmac.new(API_SECRET.encode(), pre_sign.encode(), hashlib.sha256).hexdigest()
    headers = {
        "api-key": API_KEY,
        "sign": sig,
        "signType": "HmacSHA256",
        "nonce": nonce,
        "timestamp": ts,
        "language": "en-US",
        "Content-Type": "application/json",
    }
    return headers, body

def get_price():
    try:
        r = requests.get(f"{BASE_URL}/api/v1/futures/market/ticker?symbol={SYMBOL}", timeout=10)
        data = r.json().get("data", {})
        return float(data.get("last", 0))
    except Exception as e:
        logging.error(f"get_price() failed: {e}")
        return 0

def place_order(side, price, size, live=True):
    endpoint = "/api/v1/futures/trade/place_order"
    qty = f"{size:.6f}"
    payload = {
        "symbol": SYMBOL,
        "side": side.upper(),
        "orderType": "LIMIT",
        "price": f"{price:.2f}",
        "qty": qty,
        "effect": "GTC",
        "reduceOnly": False,
        "clientId": f"grid-{int(time.time()*1000)}",
    }
    if not live:
        logging.info(f"[DRY RUN] {side.lower()} {qty} {SYMBOL} @ {price:.2f}")
        return {"code": 0, "msg": "Dry run"}
    try:
        headers, body = sign_request(endpoint, payload)
        r = requests.post(f"{BASE_URL}{endpoint}", headers=headers, data=body, timeout=10)
        result = r.json()
        logging.info(f"POST {endpoint} => {result}")
        return result
    except Exception as e:
        logging.error(f"Order placement failed: {e}")
        return {"code": -1, "msg": str(e)}

def grid_cycle(mode="LIVE"):
    live = mode.upper() == "LIVE"
    mid = get_price()
    if not mid:
        logging.error("Price fetch failed, aborting.")
        return
    logging.info(f"{mode.upper()} GRIDBOT for {SYMBOL} started")
    logging.info(f"Placing 4 orders around mid={mid:.2f}")

    spacing = 0.25 / 100
    size = 0.0093
    orders = []
    for i in range(2):
        buy_price = mid * (1 - spacing * (i + 1))
        sell_price = mid * (1 + spacing * (i + 1))
        orders.append(("buy", buy_price, size))
        orders.append(("sell", sell_price, size))

    for side, p, s in orders:
        result = place_order(side, p, s, live)
        with open(f"{LOG_DIR}/orders.csv", "a") as f:
            f.write(f"{datetime.utcnow().isoformat()},{mode},{SYMBOL},{side},{p},{s},{json.dumps(result)}\n")
        time.sleep(0.3)

    logging.info("Grid placement complete.")

if __name__ == "__main__":
    import sys
    mode = sys.argv[1].upper() if len(sys.argv) > 1 else "DRYRUN"
    grid_cycle(mode)
