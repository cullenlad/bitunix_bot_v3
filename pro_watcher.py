#!/usr/bin/env python3
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
import os, time, json, requests, subprocess
from decimal import Decimal
from dotenv import load_dotenv
load_dotenv()
BASE_URL="https://fapi.bitunix.com"; SYMBOL=os.getenv("SYMBOL","BTCUSDT")
LIVE=os.getenv("LIVE","0")=="1"; DRIFT_PCT=Decimal(os.getenv("DRIFT_PCT","0.8"))
CENTER_FILE=os.path.join(os.path.dirname(__file__),"last_center.json")
def price():
    j=requests.get(BASE_URL+"/api/v1/futures/market/tickers",params={"symbols":SYMBOL},timeout=10).json()
    for r in j.get("data") or []:
        if r.get("symbol")==SYMBOL: return Decimal(str(r["lastPrice"]))
    return None
def center():
    try:
        j=json.load(open(CENTER_FILE))
        return Decimal(j["center"])
    except Exception:
        return None
def recenter():
    try: subprocess.run(["/home/ianms/bitunix-bot/recenter.sh"],cwd="/home/ianms/bitunix-bot",check=False)
    except: pass
def main():
    while True:
        if os.getenv("LIVE","0")!="1":
            time.sleep(30); continue
        p=price(); c=center()
        if p and c:
            drift = abs((p-c)/c*Decimal(100))
            if drift > DRIFT_PCT:
                recenter()
        time.sleep(60)
if __name__=="__main__": main()
