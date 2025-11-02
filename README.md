# 🧠 BitUnix Grid Bot — by IanMS

A lightweight, self-hosted crypto grid trading bot for **BitUnix Futures**, built for safety, automation, and transparency.

It includes:
- 🔐 Web control panel (Flask) with password login  
- 🧩 Trend filter and drift-based re-centering  
- 🛡️ Drawdown watchdog (kills on max loss)  
- ⏰ Daily systemd re-center timer  
- ⚙️ Configurable grid logic via `.env`  
- 💾 Full backtesting support  
- 🔁 Auto-restart + logs for resilience  

---

PANEL_USER=yourlogin
PANEL_PASS=yourpassword


---

## ⚙️ How to Install on a Fresh Ubuntu Server

### 1️⃣ Update and install required packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-venv


**Clone the bot from GitHib - SSH**
git clone git@github.com:cullenlad/bitunix-bot.git
cd bitunix-bot

Create .env configuration
--------------------------
cp .env.example .env
nano .env

BITUNIX_API_KEY=your_api_key
BITUNIX_API_SECRET=your_api_secret
ACCOUNT_USDT=1000
SYMBOL=BTCUSDT
GRID_LEVELS=2
GRID_SPACING_PCT=0.25
ORDER_NOTIONAL_PCT=0.07
MIN_QTY=0.001
LEVERAGE=2
MAX_GRID_NOTIONAL_USDT=400
LIVE=0             # set to 1 for live trading
PANEL_USER=yourlogin
PANEL_PASS=yourpassword
PORT=8080

⚠️ .env is private — never upload it to GitHub.

4. Install and set up
-------------------------
chmod +x install.sh
./install.sh

5.  Start the bot
--------------------
sudo systemctl restart bitunix-panel.service

Open in your browser:
http://<your-server-ip>:8080
(Example: http://192.168.1.108:8080)

Login with you username and password that's in your .env file

Backtesting
------------
Before trading live

source .venv/bin/activate
python backtest_grid_v2.py

You’ll see the number of trades, PnL, and grid efficiency.


💾 Backup & Restore
Backup:
cd ~
tar --exclude='bitunix-bot/.venv' --exclude='bitunix-bot/status.csv' \
    --exclude='bitunix-bot/last_center.json' --exclude='bitunix-bot/.env' \
    -czf bitunix-bot_$(date +%Y%m%d).tar.gz bitunix-bot
Restore:
tar -xzf bitunix-bot_YYYYMMDD.tar.gz
cd bitunix-bot
./install.sh
🔁 TL;DR Reinstall Summary
sudo apt update && sudo apt install -y git python3-venv
git clone git@github.com:cullenlad/bitunix-bot.git
cd bitunix-bot
cp .env.example .env && nano .env
./install.sh
sudo systemctl restart bitunix-panel.service
Then open:
http://192.168.1.108:8080

