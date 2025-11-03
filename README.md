# Bitunix Bot v3

Grid bot + killswitch for Bitunix futures.
- `gridbot_v3.py` places grid orders via `/api/v1/futures/trade/place_order`
- `killswitch.py` cancels orders / closes positions
- Web panel served by `app.py` via gunicorn (systemd service `bitunix-panel`)

Do **not** commit `.env`, `venv/`, `logs/`, or `backups/`.
