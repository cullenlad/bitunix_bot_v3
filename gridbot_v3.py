#!/usr/bin/env python3
import os, sys, json, time, hashlib, random, string, logging, requests
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone
from dotenv import load_dotenv
from grid_guard import decision as grid_guard_decision
from grid_guard import csv_read_band as _read_csv_band
from grid_guard import guard_pause_if_outside as _guard_pause_if_outside
from killswitch import cancel_all_orders
load_dotenv()

BASE_URL = "https://fapi.bitunix.com"
SYMBOL = os.getenv("SYMBOL","BTCUSDT")
GRID_LEVELS = int(os.getenv("GRID_LEVELS","2"))
GRID_SPACING_PCT = Decimal(os.getenv("GRID_SPACING_PCT","0.2"))
ACCOUNT_USDT = Decimal(os.getenv("ACCOUNT_USDT","1000"))
ORDER_NOTIONAL_PCT = Decimal(os.getenv("ORDER_NOTIONAL_PCT","0.01"))
MIN_QTY = Decimal(os.getenv("MIN_QTY","0.001"))
API_KEY = os.getenv("BITUNIX_API_KEY","")
API_SECRET = os.getenv("BITUNIX_API_SECRET","")
CLI_DRY = any(a in ("--dry-run","-n","--paper") for a in sys.argv)
DRY_RUN = os.getenv("LIVE","0")!="1" or CLI_DRY

LOG_FILE = "/opt/bitunix-bot/logs/gridbot.log"
ORDERS_FILE = "/opt/bitunix-bot/orders.csv"

TREND_FILTER_ENABLED = os.getenv("TREND_FILTER_ENABLED","1")=="1"
TREND_EMA_PERIOD = int(os.getenv("TREND_EMA_PERIOD","30"))
TREND_SLOPE_BP = float(os.getenv("TREND_SLOPE_BP","8"))
TREND_MODE = os.getenv("TREND_MODE","block")
TREND_STATE = "/opt/bitunix-bot/.trend.json"

ATR_FILTER_ENABLED = os.getenv("ATR_FILTER_ENABLED","1")=="1"
ATR_PERIOD = int(os.getenv("ATR_PERIOD","14"))
ATR_MAX_TO_GRIDSTEP = float(os.getenv("ATR_MAX_TO_GRIDSTEP","1.2"))
ATR_DEBUG = os.getenv("ATR_DEBUG","0")=="1"
ATR_SOURCE = os.getenv("ATR_SOURCE","auto")

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def _nonce(): return "".join(random.choices(string.ascii_letters+string.digits,k=32))
def _timestamp(): return str(int(time.time()*1000))
def _sign(nonce, ts, body):
    digest = hashlib.sha256((nonce+ts+API_KEY+body).encode()).hexdigest()
    return hashlib.sha256((digest+API_SECRET).encode()).hexdigest()
def _headers(sign, nonce, ts):
    return {"api-key":API_KEY,"sign":sign,"nonce":nonce,"timestamp":ts,"language":"en-US","Content-Type":"application/json"}

def get_price():
    try:
        r = requests.get(f"{BASE_URL}/api/v1/futures/market/tickers", params={"symbols":SYMBOL}, timeout=10)
        data = r.json()
        return Decimal(str(data["data"][0]["lastPrice"]))
    except Exception as e:
        logging.error(f"get_price() failed: {e}")
        return None

class EmaTrend:
    def __init__(self, period):
        self.alpha = 2/(period+1)
        self.ema = None
        self.prev_ema = None
    def load(self, path):
        try:
            with open(path,"r") as f:
                x=json.load(f)
            self.ema = float(x.get("ema",0)) or None
            self.prev_ema = float(x.get("prev_ema",0)) or None
        except Exception:
            pass
    def save(self, path):
        try:
            with open(path,"w") as f:
                json.dump({"ema":self.ema,"prev_ema":self.prev_ema,"ts":int(time.time())}, f)
        except Exception:
            pass
    def update(self, price):
        p = float(price)
        if self.ema is None:
            self.ema = p
            self.prev_ema = p
            return 0.0
        self.prev_ema = self.ema
        self.ema = self.alpha*p + (1-self.alpha)*self.ema
        if self.prev_ema == 0:
            return 0.0
        return (self.ema - self.prev_ema) / self.prev_ema * 10000.0

def _fetch_bitunix_candles(symbol, interval="1m", limit=100):
    paths = [
        ("/api/v1/futures/market/klines", {"symbol":symbol,"interval":interval,"limit":limit}),
        ("/api/v1/futures/market/candles", {"symbol":symbol,"interval":interval,"limit":limit}),
        ("/api/v1/futures/market/klines", {"symbols":symbol,"interval":interval,"limit":limit}),
    ]
    for path, params in paths:
        try:
            r = requests.get(f"{BASE_URL}{path}", params=params, timeout=10)
            txt = r.text
            try: j = r.json()
            except: j = None
            if ATR_DEBUG:
                logging.info(f"[atr.debug] GET {path} {params} -> HTTP {r.status_code} body[:200]={txt[:200]}")
            if isinstance(j, dict) and "data" in j and isinstance(j["data"], list) and j["data"]:
                return j["data"]
            if isinstance(j, list) and j:
                return j
        except Exception as e:
            if ATR_DEBUG: logging.info(f"[atr.debug] bitunix error {e}")
            continue
    return []

def _fetch_binance_klines(symbol, interval="1m", limit=100):
    try:
        r = requests.get("https://api.binance.com/api/v3/klines", params={"symbol":symbol,"interval":interval,"limit":limit}, timeout=10)
        if ATR_DEBUG:
            logging.info(f"[atr.debug] binance GET /api/v3/klines {symbol} {interval} -> HTTP {r.status_code}")
        j = r.json()
        if isinstance(j, list) and j:
            return j
    except Exception as e:
        if ATR_DEBUG: logging.info(f"[atr.debug] binance error {e}")
    return []

def _as_float(x):
    try: return float(x)
    except: return None

def _parse_candle(c):
    if isinstance(c, list) and len(c) >= 5:
        h=_as_float(c[2]); l=_as_float(c[3]); cl=_as_float(c[4])
        if h is None or l is None or cl is None: return None
        return {"h":h,"l":l,"c":cl}
    if isinstance(c, dict):
        h=_as_float(c.get("h")); l=_as_float(c.get("l")); cl=_as_float(c.get("c"))
        if h is None or l is None or cl is None: return None
        return {"h":h,"l":l,"c":cl}
    return None

def _compute_atr_sma(candles, period):
    xs = [_parse_candle(c) for c in candles]
    xs = [x for x in xs if x]
    if len(xs) < period+1:
        return None
    trs = []
    prev_close = xs[0]["c"]
    for i in range(1,len(xs)):
        h=xs[i]["h"]; l=xs[i]["l"]; c=xs[i]["c"]
        tr = max(h-l, abs(h-prev_close), abs(l-prev_close))
        trs.append(tr)
        prev_close = c
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / float(period)

def _fetch_candles(symbol, interval, limit):
    data = []
    if ATR_SOURCE in ("auto","bitunix"):
        data = _fetch_bitunix_candles(symbol, interval, limit)
    if not data and ATR_SOURCE in ("auto","binance"):
        data = _fetch_binance_klines(symbol, interval, limit)
    return data

def atr_too_hot(price, grid_spacing_pct, period, threshold):
    candles = _fetch_candles(SYMBOL, "1m", max(100, period+2))
    atr = _compute_atr_sma(candles, period)
    if atr is None:
        logging.info("[atr] insufficient candles or API not available")
        return False
    grid_step = float(price) * float(grid_spacing_pct) / 100.0
    if grid_step <= 0:
        return False
    ratio = atr / grid_step
    logging.info(f"[atr] atr={atr:.8f} grid_step={grid_step:.8f} ratio={ratio:.3f} thr={threshold}")
    if ratio > threshold:
        print(f"[atr] hold {SYMBOL} ratio={ratio:.2f} > {threshold}")
        return True
    return False

def place_order(side, qty, price=None, trade_side="OPEN", order_type="LIMIT"):
    url = f"{BASE_URL}/api/v1/futures/trade/place_order"
    body = {"symbol":SYMBOL,"side":side,"qty":str(qty),"tradeSide":trade_side,"orderType":order_type}
    if order_type=="LIMIT" and price is not None:
        body["price"]=str(price)
        body["effect"]="GTC"
    body_s = json.dumps(body, separators=(",",":"))
    nonce, ts = _nonce(), _timestamp()
    sign = _sign(nonce, ts, body_s)
    headers = _headers(sign, nonce, ts)
    try:
        r = requests.post(url, headers=headers, data=body_s, timeout=10)
        logging.info(f"POST /api/v1/futures/trade/place_order => {r.text}")
        return r.json()
    except Exception as e:
        logging.error(f"place_order() failed: {e}")
        return None

def run_grid(mode="LIVE"):
    price = get_price()
    if price is None:
        logging.error("Price fetch failed, aborting.")
        return
    if TREND_FILTER_ENABLED:
        trend = EmaTrend(TREND_EMA_PERIOD)
        trend.load(TREND_STATE)
        slope_bp = trend.update(price)
        trend.save(TREND_STATE)
        strong = abs(slope_bp) > TREND_SLOPE_BP
        if strong and TREND_MODE=="block":
            logging.info(f"[trend] block {SYMBOL} slope_bp={slope_bp:.2f} ema={trend.ema:.4f}")
            print(f"[trend] block {SYMBOL} slope_bp={slope_bp:.2f} ema={trend.ema:.4f}")
            return
    if ATR_FILTER_ENABLED:
        if atr_too_hot(price, float(GRID_SPACING_PCT), ATR_PERIOD, ATR_MAX_TO_GRIDSTEP):
            logging.info("[atr] paused by volatility gate")
            return
    if not DRY_RUN:
        try:
            r = cancel_all_orders()
            logging.info(str(r))
        except Exception as e:
            logging.error(f"killswitch failed: {e}")
    spacing = GRID_SPACING_PCT / Decimal("100")
    notional = ACCOUNT_USDT * ORDER_NOTIONAL_PCT
    if price == 0:
        return
    qty = (notional / price).quantize(MIN_QTY, rounding=ROUND_DOWN)
    prices = []
    for i in range(1, GRID_LEVELS+1):
        prices.append((price*(1-spacing*i)).quantize(Decimal("0.01")))
        prices.append((price*(1+spacing*i)).quantize(Decimal("0.01")))
    logging.info(f"Placing {len(prices)} orders around mid={price}")
    lo, hi = _read_csv_band(ORDERS_FILE)
    try:
        mt = os.path.getmtime(ORDERS_FILE)
        max_age = int(os.getenv("GRID_GUARD_REQUIRE_RECENT_MINUTES","180"))*60
        if time.time()-mt > max_age:
            lo = hi = None
    except Exception:
        pass
    if lo is not None and hi is not None:
        if grid_guard_decision(float(price), float(lo), float(hi)) == "pause":
            print(f"DEBUG GUARD-PAUSED by csv band mid={price} band=({lo},{hi})")
            return
    if _guard_pause_if_outside(float(price), [float(x) for x in prices]):
        logging.info(f"[GUARD] paused outside band: mark={price}, band=({min(prices)},{max(prices)})")
        print(f"DEBUG GUARD-PAUSED mid={price} band=({min(prices)},{max(prices)})")
        return
    for p in prices:
        side = "BUY" if p < price else "SELL"
        if DRY_RUN:
            logging.info(f"[DRY RUN] {side.lower()} {qty} {SYMBOL} @ {p}")
        else:
            result = place_order(side, qty, p)
            logging.info(f"Order API response: {result}")
        try:
            with open(ORDERS_FILE,"a") as f:
                f.write(f"{datetime.now(timezone.utc).isoformat()},{mode},{SYMBOL},{side},{p},{qty}\n")
        except Exception:
            pass
    logging.info("Grid placement complete.")

if __name__ == "__main__":
    run_grid("DRY-RUN" if DRY_RUN else "LIVE")
