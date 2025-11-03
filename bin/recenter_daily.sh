#!/usr/bin/env bash
set -euo pipefail
ENV="/opt/bitunix-bot/.env"
USER="$(grep -E '^PANEL_USER=' "$ENV" | sed 's/^PANEL_USER=//')"
PASS="$(grep -E '^PANEL_PASS=' "$ENV" | sed 's/^PANEL_PASS=//')"
LOG="/opt/bitunix-bot/logs/recenter_cron.log"
mkdir -p /opt/bitunix-bot/logs
date -Is >> "$LOG"
curl -s -u "${USER}:${PASS}" -X POST http://127.0.0.1:8080/recenter >> "$LOG" 2>&1
echo >> "$LOG"
