#!/usr/bin/env python3
# Author: IanMS trader
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
import os, math
from decimal import Decimal, ROUND_DOWN
import pandas as pd
import ccxt
from dotenv import load_dotenv
load_dotenv()

SYMBOL = os.getenv("SYMBOL","BTCUSDT")
PAIR = "BTC/USDT"
GRID_LEVELS = int(os.getenv("GRID_LEVELS","1"))
GRID_SPACING_PCT = Decimal(os.getenv("GRID_SPACING_PCT","0.15"))
ACCOUNT_USDT = Decimal(os.getenv("ACCOUNT_USDT","1000"))
ORDER_NOTIONAL_PCT = Decimal(os.getenv("ORDER_NOTIONAL_PCT","0.07"))
LEVERAGE = Decimal(os.getenv("LEVERAGE","2"))
MIN_QTY = Decimal(os.getenv("MIN_QTY","0.001"))
TIMEFRAME = os.getenv("BT_TIMEFRAME","5m")
LIMIT = int(os.getenv("BT_LIMIT","1000"))
MAKER_FEE_PCT = Decimal(os.getenv("MAKER_FEE_PCT","0.04"))/Decimal(100)  # example 0.04%
TAKER_FEE_PCT = Decimal(os.getenv("TAKER_FEE_PCT","0.05"))/Decimal(100)

ex = ccxt.binance()
df = pd.DataFrame(ex.fetch_ohlcv(PAIR, timeframe=TIMEFRAME, limit=min(LIMIT,1000)),
                  columns=["ts","open","high","low","close","vol"])
df["ts"] = pd.to_datetime(df["ts"], unit="ms")
mid = Decimal(str(df.iloc[0]["close"]))

def q_for_price(p):
    notional = ACCOUNT_USDT * ORDER_NOTIONAL_PCT
    q = (notional / Decimal(str(p))) * LEVERAGE
    q = Decimal(q).quantize(MIN_QTY, rounding=ROUND_DOWN)
    return q if q >= MIN_QTY else Decimal("0")

levels = []
for i in range(1, GRID_LEVELS+1):
    pct = GRID_SPACING_PCT * i
    buy_p = (mid * (Decimal("1") - pct/Decimal("100")))
    sell_p = (mid * (Decimal("1") + pct/Decimal("100")))
    levels.append(("BUY", buy_p))
    levels.append(("SELL", sell_p))
levels.sort(key=lambda x: float(x[1]))

open_legs = {}
realized = Decimal("0")
fees = Decimal("0")
trades = 0
max_open = 0

for _,row in df.iterrows():
    hi = Decimal(str(row["high"]))
    lo = Decimal(str(row["low"]))
    for side,price in levels:
        p = Decimal(str(price))
        if side=="BUY" and lo <= p <= hi and ("LONG", p) not in open_legs:
            qty = q_for_price(p)
            if qty > 0:
                open_legs[("LONG", p)] = {"qty": qty, "tp": p*(Decimal("1")+GRID_SPACING_PCT/Decimal("100"))}
                fees += p * qty * MAKER_FEE_PCT
                trades += 1
        if side=="SELL" and lo <= p <= hi and ("SHORT", p) not in open_legs:
            qty = q_for_price(p)
            if qty > 0:
                open_legs[("SHORT", p)] = {"qty": qty, "tp": p*(Decimal("1")-GRID_SPACING_PCT/Decimal("100"))}
                fees += p * qty * MAKER_FEE_PCT
                trades += 1
    closes = []
    for key,data in open_legs.items():
        kind, entry = key
        tp = data["tp"]
        if kind=="LONG" and lo <= tp <= hi:
            realized += (tp - entry) * data["qty"]
            fees += tp * data["qty"] * MAKER_FEE_PCT
            closes.append(key)
        if kind=="SHORT" and lo <= tp <= hi:
            realized += (entry - tp) * data["qty"]
            fees += tp * data["qty"] * MAKER_FEE_PCT
            closes.append(key)
    for key in closes:
        del open_legs[key]
    if len(open_legs) > max_open:
        max_open = len(open_legs)

net = realized - fees
logging.info({
    "used_timeframe": TIMEFRAME,
    "used_limit": len(df),
    "grid_levels": GRID_LEVELS,
    "spacing_pct": str(GRID_SPACING_PCT),
    "per_order_pct": str(ORDER_NOTIONAL_PCT),
    "min_qty": str(MIN_QTY),
    "leverage": str(LEVERAGE),
    "trades_opened": trades,
    "open_legs_left": len(open_legs),
    "max_open_legs": max_open,
    "realized_pnl_usdt": float(realized),
    "fees_usdt": float(fees),
    "net_pnl_usdt": float(net)
})
