import logging,sys
logging.basicConfig(level=logging.INFO, format="%(message)s")
import logging,sys
logging.basicConfig(level=logging.INFO, format="%(message)s")
import os, time, json
from datetime import datetime

STATE_FILE = "/opt/bitunix-bot/.guard.json"

def _now(): return int(time.time())
def _getb(k, d="0"): return os.getenv(k, d) == "1"
def _geti(k, d): return int(os.getenv(k, d))
def _getf(k, d): return float(os.getenv(k, d))
def _load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"paused_until": 0, "status": "armed", "last_outside": None}
def _save_state(s):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(s, f)
    except Exception:
        pass

def csv_read_band(path):
    lo, hi = None, None
    try:
        with open(path, "r") as f:
            lines = f.read().strip().splitlines()
        if not lines:
            return None, None
        prices = []
        for line in lines:
            parts = line.split(",")
            if len(parts) >= 6:
                try:
                    prices.append(float(parts[4]))
                except Exception:
                    pass
        if prices:
            lo, hi = min(prices), max(prices)
        st = os.stat(path)
        max_age = _geti("GRID_GUARD_REQUIRE_RECENT_MINUTES", "180") * 60
        if _now() - int(st.st_mtime) > max_age:
            lo, hi = None, None
    except Exception:
        lo, hi = None, None
    return lo, hi

def decision(price, lo, hi):
    if not _getb("GRID_GUARD_ENABLED", "1"):
        return "ok"
    if lo is None or hi is None or hi <= 0:
        return "ok"
    buf = _getf("GRID_GUARD_BUFFER_PCT", "0.004")
    hyst = _getf("GRID_GUARD_HYSTERESIS_PCT", "0.002")
    cooldown = _geti("GRID_GUARD_COOLDOWN_S", "600")
    action = os.getenv("GRID_GUARD_ACTION", "pause")
    s = _load_state()
    now = _now()
    if s.get("paused_until", 0) > now:
        return action
    upper = hi * (1 + buf)
    lower = lo * (1 - buf)
    if price > upper or price < lower:
        s["paused_until"] = now + cooldown
        s["status"] = "paused"
        s["last_outside"] = price
        _save_state(s)
        return action
    if s.get("status") == "paused":
        inner_upper = hi * (1 - hyst)
        inner_lower = lo * (1 + hyst)
        if inner_lower <= price <= inner_upper:
            s["status"] = "armed"
            s["paused_until"] = 0
            _save_state(s)
            return "ok"
        else:
            s["paused_until"] = now + cooldown
            _save_state(s)
            return action
    return "ok"

def guard_pause_if_outside(price, price_list):
    if not price_list:
        return False
    lo = min(price_list)
    hi = max(price_list)
    return decision(price, lo, hi) != "ok"
