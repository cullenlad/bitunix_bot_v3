import os
from decimal import Decimal

EN = os.getenv("GRID_GUARD_ENABLED","0") == "1"
BUF = Decimal(os.getenv("GRID_GUARD_BUFFER_PCT","0.004"))
ACT = os.getenv("GRID_GUARD_ACTION","pause")  # pause | flatten

def decision(mark_price: float, grid_low: float, grid_high: float):
    if not EN:
        return "allow"
    mp = Decimal(str(mark_price))
    lo = Decimal(str(grid_low))
    hi = Decimal(str(grid_high))
    lo_b = lo * (1 - BUF)
    hi_b = hi * (1 + BUF)
    if mp < lo_b or mp > hi_b:
        return ACT
    return "allow"

def guard_pause_if_outside(mark_price: float, grid_prices: list[float]) -> bool:
    if not grid_prices:
        return False
    lo = min(grid_prices)
    hi = max(grid_prices)
    return decision(mark_price, lo, hi) == "pause"

def csv_read_band(path: str):
    try:
        lo = None
        hi = None
        with open(path, "r") as f:
            first = True
            for line in f:
                if first:
                    first = False
                    continue
                parts = line.strip().split(",")
                if len(parts) < 5:
                    continue
                try:
                    p = float(parts[4])
                except Exception:
                    continue
                if lo is None or p < lo:
                    lo = p
                if hi is None or p > hi:
                    hi = p
        return lo, hi
    except Exception:
        return None, None

def csv_read_band(path: str):
    try:
        lo = None
        hi = None
        with open(path, "r") as f:
            first = True
            for line in f:
                if first:
                    first = False
                    continue
                parts = line.strip().split(",")
                if len(parts) < 5:
                    continue
                try:
                    p = float(parts[4])
                except Exception:
                    continue
                if lo is None or p < lo:
                    lo = p
                if hi is None or p > hi:
                    hi = p
        return lo, hi
    except Exception:
        return None, None
