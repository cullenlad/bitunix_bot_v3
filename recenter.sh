#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate

if [ "${LIVE:-0}" != "1" ]; then
  echo "LIVE=0 -> dry-run recenter"
else
  python killswitch.py || true
fi

python gridbot_v2.py
