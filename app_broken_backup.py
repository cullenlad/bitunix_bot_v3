import os, json, time, shutil
from flask import Flask, request, jsonify, Response
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

PANEL_USER = os.getenv("PANEL_USER","ianms")
PANEL_PASS = os.getenv("PANEL_PASS","1BitUnix123!$")

def _auth_ok(a): return a and a.username==PANEL_USER and a.password==PANEL_PASS
def _need_auth(): return Response("Auth required",401,{"WWW-Authenticate":'Basic realm=\"panel\"'})
def _require_auth():
    a = request.authorization
    if not _auth_ok(a):
        return _need_auth()
    return None

SAFE_KEYS = sorted({
 "LIVE",
 "SYMBOL","GRID_LEVELS","GRID_SPACING_PCT",
 "ORDER_NOTIONAL_PCT","ACCOUNT_USDT","MIN_QTY",
 "LEVERAGE","MAX_GRID_NOTIONAL_USDT","STATUS_POLL_SEC",
 "TREND_FILTER_ENABLED","TREND_EMA_PERIOD","TREND_SLOPE_BP","TREND_MODE",
 "ATR_FILTER_ENABLED","ATR_PERIOD","ATR_MAX_TO_GRIDSTEP","ATR_SOURCE","ATR_DEBUG",
 "GRID_GUARD_ENABLED","GRID_GUARD_BUFFER_PCT","GRID_GUARD_HYSTERESIS_PCT","GRID_GUARD_COOLDOWN_S","GRID_GUARD_ACTION","GRID_GUARD_REQUIRE_RECENT_MINUTES",
 "PANEL_USER","PANEL_PASS"
})

def _load_env_as_dict():
    return {k: os.getenv(k) for k in SAFE_KEYS}

def _persist_env(upd):
    path = ".env"
    cur = {}
    if os.path.exists(path):
        with open(path,"r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k,v = line.rstrip("\n").split("=",1)
                    cur[k]=v
    cur.update({k:str(v) for k,v in upd.items()})
    lines = [f"{k}={cur[k]}\n" for k in cur]
    with open(path,"w") as f:
        f.writelines(lines)

@app.route("/")
def index():
    return Response('OK. Visit <a href=\"/panel/settings\">/panel/settings</a>', mimetype="text/html")

@app.route("/api/killswitch", methods=["POST"])
def api_killswitch():
    r = _require_auth()
    if r: return r
    try:
        from killswitch import cancel_all_orders
        out = cancel_all_orders()
        return jsonify(out)
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500

@app.route("/api/newgrid", methods=["POST"])
def api_newgrid():
    r = _require_auth()
    if r: return r
    try:
        src = "/opt/bitunix-bot/orders.csv"
        if os.path.exists(src):
            ts = int(time.time())
            dst_dir = "/opt/bitunix-bot/backups"
            os.makedirs(dst_dir, exist_ok=True)
            dst = f"{dst_dir}/orders_{ts}.csv"
            shutil.copyfile(src, dst)
            open(src,"w").close()
            return jsonify({"ok":True,"archived":dst,"cleared":"orders.csv"})
        return jsonify({"ok":True,"msg":"no orders.csv to archive"})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500

@app.route("/api/config", methods=["GET","POST"])
def api_config():
    r = _require_auth()
    if r: return r
    if request.method=="GET":
        return jsonify(_load_env_as_dict())
    data = request.get_json(force=True) or {}
    upd = {k:str(v) for k,v in data.items() if k in SAFE_KEYS}
    if not upd:
        return jsonify({"ok":False,"msg":"no valid keys"}), 400
    _persist_env(upd)
    for k,v in upd.items():
        os.environ[k]=v
    return jsonify({"ok":True,"updated":upd,"current":_load_env_as_dict()})

@app.route("/panel/settings")
def panel_settings():
    r = _require_auth()
    if r: return r
    keys = SAFE_KEYS
    html = """
<html><head><meta name=viewport content=\"width=device-width, initial-scale=1\">
<style>body{font-family:system-ui;margin:20px;max-width:760px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
label{font-size:12px;color:#333}
input{width:100%;padding:8px;border:1px solid #ccc;border-radius:8px}
button{padding:10px 16px;border:0;border-radius:10px;cursor:pointer}
pre{background:#f6f6f6;padding:10px;border-radius:8px;overflow:auto}
.card{background:#fff;border:1px solid #eee;border-radius:12px;padding:16px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
</style></head><body>
<h2>Bitunix Grid Control Settings</h2>
<div class=card>
<div class=grid id=form></div>
<div style=\"margin-top:12px\"><button id=save>Save</button></div>
</div>
<pre id=msg></pre>
<script>
const auth='Basic '+btoa('%s:%s');
const keys=%s;
function row(k,v){return `<div><label>${k}</label><input id=\"${k}\" value=\"${v??''}\"></div>`}
fetch('/api/config',{headers:{'Authorization':auth}})
.then(r=>r.json())
.then(cfg=>{
 document.getElementById('form').innerHTML=keys.map(k=>row(k,cfg[k])).join('');
 document.getElementById('save').onclick=()=>{
  const body={}; keys.forEach(k=>{const el=document.getElementById(k);if(el)body[k]=el.value});
  fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json','Authorization':auth},body:JSON.stringify(body)})
   .then(r=>r.json()).then(x=>{document.getElementById('msg').textContent=JSON.stringify(x,null,2)});
 };
});
</script></body></html>
""" % (PANEL_USER, PANEL_PASS, json.dumps(keys))
    return Response(html, mimetype="text/html")
