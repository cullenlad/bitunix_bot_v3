import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

MAX_DRAWDOWN_USDT = float(os.getenv("MAX_DRAWDOWN_USDT", 50))
ACCOUNT_USDT = float(os.getenv("ACCOUNT_USDT", 1000))
CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", 5))

def get_current_drawdown_usdt() -> float:
    try:
        # placeholder for your actual PnL/drawdown check
        # can read a file, API, or database
        path = "/opt/bitunix-bot/last_center.json"
        if os.path.exists(path):
            with open(path, "r") as f:
                data = f.read()
            if data.strip():
                logging.debug("Checked last_center.json: %s", data[:100])
        # Simulate zero drawdown for now
        return 0.0
    except Exception as e:
        logging.error(f"Error checking drawdown: {e}")
        return 0.0

def trigger_killswitch():
    logging.info(">>> Triggering killswitch due to drawdown breach...")
    try:
        os.system("python3 /opt/bitunix-bot/killswitch.py")
    except Exception as e:
        logging.error(f"Error executing killswitch: {e}")

def main():
    logging.info("Starting BitUnix watchdog...")
    while True:
        dd = get_current_drawdown_usdt()
        if dd > MAX_DRAWDOWN_USDT:
            logging.warning(f"Drawdown {dd:.2f} > {MAX_DRAWDOWN_USDT:.2f} USDT limit!")
            trigger_killswitch()
        time.sleep(CHECK_INTERVAL_SEC)

if __name__ == "__main__":
    main()
