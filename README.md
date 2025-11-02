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

## 🚀 Quick Start (existing setup)

Your bot runs on Ubuntu Server VM at:

**http://192.168.1.108:8080**

Login with:
PANEL_USER=yourlogin
PANEL_PASS=yourpassword

---

## ⚙️ How to Install on a Fresh Ubuntu Server

### 1️⃣ Update and install required packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-venv
2️⃣ Clone the bot from GitHub
Option A – SSH (recommended):
git clone git@github.com:cullenlad/bitunix-bot.git
Option B – HTTPS (if SSH not set up):
git clone https://github.com/cullenlad/bitunix-bot.git
Then:
cd bitunix-bot
3️⃣ Create your .env configuration
cp .env.example .env
nano .env
Example contents:
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
4️⃣ Install and set up
chmod +x install.sh
./install.sh
This:
Creates a Python virtual environment
Installs dependencies (Flask, ccxt, pandas, etc.)
Sets up systemd services:
bitunix-panel.service – Web dashboard
bitunix-watchdog.service – Loss protection
bitunix-recenter.timer – Daily grid re-center
5️⃣ Start the bot
sudo systemctl restart bitunix-panel.service
Open in your browser:
http://<your-server-ip>:8080
(Example: http://192.168.1.108:8080)
Login with your credentials from .env.

🧮 Backtesting
Before trading live:
source .venv/bin/activate
python backtest_grid_v2.py
You’ll see the number of trades, PnL, and grid efficiency.
🧾 Daily Operation
Action	Command
Check status	systemctl status bitunix-panel.service
Restart bot	sudo systemctl restart bitunix-panel.service
View logs	journalctl -u bitunix-panel.service -n 50 --no-pager
Trigger re-center manually	sudo systemctl start bitunix-recenter.service
See timers	`systemctl list-timers
⚠️ Safety Features
Layer	Description
Drawdown Watchdog	Cancels orders if unrealised loss exceeds MAX_DRAWDOWN_USDT.
Trend Filter	Suspends grids when volatility exceeds TREND_THRESHOLD_PCT.
Drift Watcher	Re-centers automatically if price drifts from midline.
Notional Cap	Prevents total grid exposure > MAX_GRID_NOTIONAL_USDT.
🔒 Security
API keys stay local in .env only.
The web interface uses password login.
Restrict dashboard access to your LAN if needed:
sudo ufw allow from 192.168.1.0/24 to any port 8080
🧰 Maintenance
Task	Command
Update code	git pull origin main
Rebuild venv	rm -rf .venv && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
Stop services	sudo systemctl stop bitunix-*
Start services	sudo systemctl start bitunix-panel.service bitunix-watchdog.service bitunix-recenter.timer
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
🧠 Author
IanMS Trader
GitHub: @cullenlad
Version: v1.0
🏁 License
Private project — for personal and educational use only.
Redistribution or public sharing of this strategy or its code is not allowed.

---

✅ Once you’ve pasted that, hit **Commit changes**, and your README is complete — no formatting or code block confusion.
You said:
what is the name of my .env file so I know it is the same if I need to reinstall
ChatGPT said:
Excellent question 👍 — you’ve already been using it correctly!
The name of your environment file is simply:

.env
That’s the exact filename (with a dot at the start).
✅ Location
It lives in your project folder:
/home/ianms/bitunix-bot/.env
You can confirm it anytime with:
ls -a ~/bitunix-bot | grep env
You’ll see:
.env
✅ Why it matters
This file contains your API key, secret, bot settings, and panel login.
It’s never uploaded to GitHub (because .gitignore excludes it).
When reinstalling or restoring from a backup, you just need to copy this file back into your bot folder.
✅ Reuse during reinstall
If you reinstall on a new server:
git clone git@github.com:cullenlad/bitunix-bot.git
cd bitunix-bot
# copy your backed-up .env back in
scp ianms@oldserver:/home/ianms/bitunix-bot/.env .
./install.sh
sudo systemctl restart bitunix-panel.service
That’s it — your bot will be configured exactly as before, using your .env.
Would you like me to show you how to make a secure backup copy of just that file (so you can restore it anytime)?

You said:
yeah give me a secure backup copy so I can just copy this file back if needs nbe
ChatGPT said:
Perfect ✅ — you’re thinking exactly like a professional trader should.
The .env file is the brain of your bot, so having a secure backup means you can reinstall in minutes without retyping API keys or settings.
Here’s how to do it safely and easily 👇

🧱 Step 1 — Make a secure backup copy
Run this command on your Ubuntu VM:
cp ~/bitunix-bot/.env ~/bitunix-bot/env_backup_$(date +%Y%m%d).txt
That creates a timestamped copy like:
env_backup_20251102.txt
🗜️ Step 2 — Compress and protect it
Now compress it with encryption so nobody else can read your keys:
zip -e ~/env_backup_$(date +%Y%m%d).zip ~/bitunix-bot/env_backup_$(date +%Y%m%d).txt
🔒 It will ask you to set a password — this encrypts the backup so even if it’s stolen, your keys are safe.
You’ll get something like:

adding: env_backup_20251102.txt (deflated 25%)
Enter password:
Verify password:
🧳 Step 3 — Copy to your Mac (or USB, or cloud)
You can then safely copy it off the server:
scp ianms@192.168.1.108:~/env_backup_*.zip ~/Desktop/
Or just drag it from your SSH file browser if you use one.
🪄 Step 4 — To restore later
When reinstalling, copy it back to your bot folder and extract it:
scp ~/Desktop/env_backup_20251102.zip ianms@192.168.1.108:~/
unzip env_backup_20251102.zip -d ~/bitunix-bot/
mv ~/bitunix-bot/env_backup_20251102.txt ~/bitunix-bot/.env
That restores your full configuration instantly.
✅ Result
Now your backup:
Is encrypted
Is timestamped
Can be restored on any new VM
Keeps your bot’s settings exactly as before
