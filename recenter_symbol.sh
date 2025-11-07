#!/usr/bin/env bash
set -euo pipefail
if [[ -d venv ]]; then source venv/bin/activate; elif [[ -d .venv ]]; then source .venv/bin/activate; fi
export $(grep -v '^#' .env | xargs)
export SYMBOL="${1:-$SYMBOL}"
export LAST_CENTER_PATH="/opt/bitunix-bot/last_center_${SYMBOL}.json"
GUARD_OUT="$(python -u guard_check.py 2>&1 || true)"
echo "$GUARD_OUT"
if echo "$GUARD_OUT" | grep -qi '^outside$'; then
  echo "[recenter:$SYMBOL] grid guard tripped"
  if [[ "${LIVE:-0}" = "1" ]]; then
    echo "[recenter:$SYMBOL] killswitch"
    python killswitch.py || true
    echo "[recenter:$SYMBOL] flatten position"
    python flatten_position.py || true
  fi
  exit 0
fi
if [[ "${LIVE:-0}" = "1" ]]; then
  echo "[recenter:$SYMBOL] LIVE"
  python killswitch.py || true
else
  echo "[recenter:$SYMBOL] DRY"
fi
python gridbot_latest.py
