import os, json, time, shutil, subprocess
from flask import Flask, request, jsonify, Response, send_file, render_template_string
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

PANEL_USER = os.getenv("PANEL_USER","admin")
PANEL_PASS = os.getenv("PANEL_PASS","changeme")

BASE_DIR = "/opt/bitunix-bot"
ENV_PATH = os.path.join(BASE_DIR, ".env")
ORDERS_PATH = os.path.join(BASE_DIR, "orders.csv")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(BACKUPS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

def _auth_ok(a): return a and a.username == PANEL_USER and a.password == PANEL_PASS
def _need_auth(): return Response("Auth required", 401, {"WWW-Authenticate": 'Basic realm="panel"'})
def _require_auth():
    a = request.authorization
    if not _auth_ok(a): return _need_auth()
    return None

# fields shown and saved
ORDER_FIELDS = [
    "GRID_LEVELS","ORDER_NOTIONAL_PCT","GRID_SPACING_PCT","MAX_GRID_NOTIONAL_USDT",
    "LEVERAGE","LIVE","STATUS_POLL_SEC","SYMBOL",
    "TREND_FILTER_ENABLED","TREND_EMA_PERIOD","TREND_SLOPE_BP","TREND_MODE"
]

def _load_env():
    d = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.rstrip("\n").split("=", 1)
                    d[k] = v
    return d

def _save_env(upd):
    cur = _load_env()
    cur.update({k: str(v) for k, v in upd.items()})
    with open(ENV_PATH, "w") as f:
        for k, v in cur.items():
            f.write(f"{k}={v}\n")
    for k, v in upd.items():
        os.environ[k] = str(v)

@app.route("/")
def home():
    r = _require_auth()
    if r: return r
    template = """
<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BitUnix Grid Control</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;max-width:900px}
h1{font-weight:700}
.card{border:1px solid #e5e5e5;border-radius:14px;padding:16px;background:#fff}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
label{font-size:12px;color:#333}
input,select{width:100%;padding:10px;border:1px solid #ccc;border-radius:10px}
button{padding:10px 14px;border:0;border-radius:10px;background:#eee;cursor:pointer}
button.primary{background:#111;color:#fff}
button.danger{background:#fee;border:1px solid #fbb}
.mono{font-family:ui-monospace, SFMono-Regular, Menlo, monospace}
.row{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
.small{font-size:12px;color:#666}
</style></head><body>
<h1>BitUnix Grid Control</h1>
<div class="card">
  <div class="grid" id="form"></div>
  <div class="small">Saving updates the .env file immediately.</div>
  <div class="row" style="margin-top:12px">
    <button id="save" class="primary">Save Settings</button>
  </div>
</div>

<div class="row" style="margin-top:14px">
  <button onclick="act('status')">Status</button>
  <button onclick="act('dryrun')">Place Grid (Dry-Run)</button>
  <button onclick="act('golive')" class="primary">Go Live + Place Grid</button>
  <button onclick="act('recenter')">Re-center</button>
  <button onclick="act('killswitch')" class="danger">Kill-Switch</button>
  <a href="/dashboard" class="small">📊 Dashboard</a>
  <a href="/download" class="small">Download</a>
</div>

<div style="margin-top:10px"><a class="mono" href="/status.csv">status.csv</a></div>
<pre id="out" class="card mono" style="margin-top:10px;white-space:pre-wrap;max-height:400px;overflow:auto">Ready.</pre>

<script>
const auth = 'Basic '+btoa('{{ user }}:{{ pwd }}');
const ids = {{ ids|tojson }};
function inputRow(k,v){ let t='text'; if(['GRID_LEVELS','LEVERAGE','STATUS_POLL_SEC','TREND_EMA_PERIOD','LIVE'].includes(k)) t='number'; return '<div><label>'+k+'</label><input id="'+k+'" type="'+t+'" value="'+(v??'')+'"></div>'; }
function loadCfg(){
  fetch('/config',{headers:{'Authorization':auth}}).then(r=>r.json()).then(cfg=>{
    document.getElementById('form').innerHTML = ids.map(k=>inputRow(k,cfg[k])).join('');
  });
}
function save(){
  const body={}; ids.forEach(k=>{ const el=document.getElementById(k); if(el) body[k]=el.value; });
  fetch('/save',{method:'POST',headers:{'Content-Type':'application/json','Authorization':auth},body:JSON.stringify(body)})
    .then(r=>r.json()).then(x=>{ document.getElementById('out').textContent = JSON.stringify(x,null,2); });
}
function act(a){
  fetch('/act/'+a,{method:'POST',headers:{'Authorization':auth}})
    .then(r=>r.json()).then(x=>{ document.getElementById('out').textContent = JSON.stringify(x,null,2); });
}
document.getElementById('save').onclick = save;
loadCfg();
</script>
</body></html>
"""
    return render_template_string(template, user=PANEL_USER, pwd=PANEL_PASS, ids=ORDER_FIELDS)

@app.route("/config")
def cfg():
    r = _require_auth()
    if r: return r
    cur = _load_env()
    out = {k: cur.get(k, "") for k in ORDER_FIELDS}
    return jsonify(out)

@app.route("/save", methods=["POST"])
def save():
    r = _require_auth()
    if r: return r
    data = request.get_json(force=True) or {}
    whitelist = {
        "GRID_LEVELS": int, "ORDER_NOTIONAL_PCT": float, "GRID_SPACING_PCT": float,
        "MAX_GRID_NOTIONAL_USDT": float, "LEVERAGE": int, "LIVE": int, "STATUS_POLL_SEC": int,
        "SYMBOL": str,
        "TREND_FILTER_ENABLED": int, "TREND_EMA_PERIOD": int, "TREND_SLOPE_BP": float, "TREND_MODE": str
    }
    clean, errs = {}, {}
    for k, caster in whitelist.items():
        if k in data:
            raw = str(data[k]).strip()
            try:
                if caster is int: int(float(raw))
                elif caster is float: float(raw)
                else: caster(raw)
                clean[k] = raw
            except Exception:
                errs[k] = f"invalid value: {raw}"
    if errs: return jsonify({"ok": False, "errors": errs}), 400
    _save_env(clean)
    return jsonify({"ok": True, "saved": clean})

@app.route("/act/<op>", methods=["POST"])
def act(op):
    r = _require_auth()
    if r: return r
    if op == "killswitch":
        try:
            from killswitch import cancel_all_orders
            res = cancel_all_orders()
            return jsonify({"ok": True, "killswitch": res})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    if op == "recenter":
        if os.path.exists(ORDERS_PATH):
            ts = int(time.time())
            dst = os.path.join(BACKUPS_DIR, f"orders_{ts}.csv")
            shutil.copyfile(ORDERS_PATH, dst)
            open(ORDERS_PATH, "w").close()
            return jsonify({"ok": True, "archived": dst, "cleared": "orders.csv"})
        return jsonify({"ok": True, "msg": "no orders.csv to archive"})
    if op in ("dryrun", "golive", "status"):
        env = _load_env()
        if op == "golive":
            env["LIVE"] = "1"
            _save_env({"LIVE":"1"})
        if op == "dryrun":
            env["LIVE"] = "0"
            _save_env({"LIVE":"0"})
        cmd = ["python","-X","dev", os.path.join(BASE_DIR,"gridbot_v3.py")]
        if op != "golive": cmd.append("--dry-run")
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=BASE_DIR, text=True)
            out, _ = p.communicate(timeout=30)
            return jsonify({"ok": True, "cmd":" ".join(cmd), "rc": p.returncode, "out": out[-4000:]})
        except subprocess.TimeoutExpired:
            p.kill()
            return jsonify({"ok": False, "error": "bot run timed out after 30s"})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})
    return jsonify({"ok": False, "error": "unknown op"})

@app.route("/status.csv")
def status_csv():
    r = _require_auth()
    if r: return r
    if os.path.exists(ORDERS_PATH):
        return send_file(ORDERS_PATH, as_attachment=False, download_name="status.csv")
    return Response("timestamp,mode,symbol,side,price,qty\n", mimetype="text/csv")

@app.route("/download")
def download():
    r = _require_auth()
    if r: return r
    if os.path.exists(ORDERS_PATH):
        return send_file(ORDERS_PATH, as_attachment=True, download_name="orders.csv")
    return Response("No orders.csv", status=404)

@app.route("/dashboard")
def dash():
    r = _require_auth()
    if r: return r
    return Response('<meta http-equiv="refresh" content="0; url=/">', mimetype="text/html")
