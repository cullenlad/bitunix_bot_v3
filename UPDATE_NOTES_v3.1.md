# v3.1 (stable)

- Guard pauses grid placement when current price is outside the last placed grid band (derived from `orders.csv`). Env:
  - `GRID_GUARD_ENABLED=1`
  - `GRID_GUARD_BUFFER_PCT=0.004`
  - `GRID_GUARD_ACTION=pause` (or `flatten`)
  - Optional: `GRID_GUARD_REQUIRE_RECENT_MINUTES=180` to ignore stale CSV bands
- Panel APIs (Basic Auth via `PANEL_USER`/`PANEL_PASS`):
  - `POST /api/killswitch` — cancels all orders (retries ×3, logs status/body)
  - `POST /api/newgrid` — archives `orders.csv` to `/backups/orders_YYYYMMDDTHHMMSSZ.csv` and recreates empty file
- Killswitch now accepts optional symbol; defaults to `SYMBOL` in `.env`.
- Minimal `requirements.txt` and tighter `.gitignore`.

How to run:
- Panel: `source venv/bin/activate && python -m flask --app app run --host 0.0.0.0 --port 8000`
- Bot (dry run): `source venv/bin/activate && python -X dev gridbot_v3.py --dry-run --symbols BTCUSDT --interval 60`
