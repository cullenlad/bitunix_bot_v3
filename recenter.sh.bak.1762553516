#!/usr/bin/env bash
set -euo pipefail

# single-run lock to avoid overlap
LOCK="/var/lock/bitunix-recenter.lock"
if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK"
  flock -n 9 || { echo "[recenter] another run is active"; exit 0; }
fi

STATE_DIR="/opt/bitunix-bot"
OUTSIDE_FILE="${STATE_DIR}/.outside_since"

if [[ -d venv ]]; then source venv/bin/activate; elif [[ -d .venv ]]; then source .venv/bin/activate; fi
export $(grep -v '^#' .env | xargs)

OUTSIDE_MAX_MINUTES="${OUTSIDE_MAX_MINUTES:-0}"

# FORCE NOW?
if [[ "${1:-}" == "--force-now" ]]; then
  echo "[recenter] FORCE: skipping guard/timeout"
  if [[ "${LIVE:-0}" = "1" ]]; then
    echo "[recenter] killswitch"; python killswitch.py || true
    echo "[recenter] flatten position"; python flatten_position.py || true
  else
    echo "LIVE=0 -> dry-run force recenter"
  fi
  
python gridbot_latest.py
# auto-sync guard center from last successful placement
python - <<'PY2'
import re,json,os,pathlib
log="/opt/bitunix-bot/logs/gridbot.log"
mid=None; seen=False
for line in reversed(pathlib.Path(log).read_text().splitlines()):
    if "Grid placement complete." in line and not seen: seen=True
    elif seen and "Placing" in line and " mid=" in line:
        m=re.search(r'mid=([0-9.]+)', line)
        if m: mid=float(m.group(1)); break
out=os.getenv("LAST_CENTER_PATH","/opt/bitunix-bot/last_center_BTCUSDT.json")
if mid: open(out,"w").write(json.dumps({"center":mid},indent=2)); print("[center] ->", mid)
else:  print("[center] no recent placement found")
PY2

  exit 0
fi

GUARD_OUT="$(python -u guard_check.py 2>&1 || true)"
echo "$GUARD_OUT"

is_outside() { echo "$1" | grep -qi '^outside$'; }

if is_outside "$GUARD_OUT"; then
  echo "[recenter] grid guard: OUTSIDE"
  now=$(date +%s)

  if [[ "${OUTSIDE_MAX_MINUTES:-0}" =~ ^[0-9]+$ ]] && (( OUTSIDE_MAX_MINUTES > 0 )); then
    if [[ -f "$OUTSIDE_FILE" ]]; then
      since=$(cat "$OUTSIDE_FILE" 2>/dev/null || echo "$now")
    else
      echo "$now" > "$OUTSIDE_FILE"
      echo "[recenter] started outside timer"
      exit 0
    fi
    elapsed=$(( now - since ))
    threshold=$(( OUTSIDE_MAX_MINUTES * 60 ))
    echo "[recenter] outside for ${elapsed}s (threshold ${threshold}s)"
    if (( elapsed < threshold )); then
      exit 0
    fi
    echo "[recenter] outside timeout reached → RECENTER"
  else
    exit 0
  fi

  if [[ "${LIVE:-0}" = "1" ]]; then
    echo "[recenter] killswitch"; python killswitch.py || true
    echo "[recenter] flatten position"; python flatten_position.py || true
  else
    echo "LIVE=0 -> dry-run recenter (after outside timeout)"
  fi

  python gridbot_latest.py
  rm -f "$OUTSIDE_FILE"
  exit 0
fi

rm -f "$OUTSIDE_FILE" 2>/dev/null || true

if [[ "${LIVE:-0}" = "1" ]]; then
  echo "LIVE=1 -> killswitch then recenter"; python killswitch.py || true
else
  echo "LIVE=0 -> dry-run recenter"
fi

python gridbot_latest.py
  rm -f "$OUTSIDE_FILE"
  exit 0
else
  rm -f "$OUTSIDE_FILE" 2>/dev/null || true
fi

if [[ "${LIVE:-0}" = "1" ]]; then
  echo "LIVE=1 -> killswitch then recenter"; python killswitch.py || true
else
  echo "LIVE=0 -> dry-run recenter"
fi

python gridbot_latest.py
