#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_file, render_template_string, Response
import os, subprocess, threading, time, json, requests, random, string, hashlib
from decimal import Decimal
from dotenv import load_dotenv
load_dotenv()

BASE_DIR=os.path.abspath(os.path.dirname(__file__))
ENV_PATH=os.path.join(BASE_DIR,'.env')
BASE_URL="https://fapi.bitunix.com"
app=Flask(__name__)

def read_env():
    d={}
    if os.path.exists(ENV_PATH):
        for line in open(ENV_PATH):
            if '=' in line and not line.strip().startswith('#'):
                k,v=line.strip().split('=',1)
                d[k]=v
    return d

def set_env(k,v):
    d=read_env()
    d[k]=str(v)
    order = ["BITUNIX_API_KEY","BITUNIX_API_SECRET","ACCOUNT_USDT","SYMBOL","GRID_LEVELS","GRID_SPACING_PCT","ORDER_NOTIONAL_PCT","MIN_QTY","LEVERAGE","MAX_GRID_NOTIONAL_USDT","LIVE","STATUS_POLL_SEC","BT_TIMEFRAME","BT_LIMIT","MAKER_FEE_PCT","TAKER_FEE_PCT","CHECK_INTERVAL_SEC","MAX_DRAWDOWN_USDT","PORT","PANEL_USER","PANEL_PASS"]
    seen=set(); lines=[]
    for k0 in order:
        if k0 in d:
            lines.append(f"{k0}={d[k0]}\n"); seen.add(k0)
    for k0,v0 in d.items():
        if k0 not in seen:
            lines.append(f"{k0}={v0}\n")
    open(ENV_PATH,'w').writelines(lines)
    load_dotenv(override=True)

def run_cmd(cmd):
    p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=BASE_DIR)
    out=p.communicate()[0].decode('utf-8','ignore')
    return out

def _now_ms(): return str(int(time.time()*1000))
def _nonce(): return ''.join(random.choices(string.ascii_letters+string.digits,k=32))
def _sha(s): return hashlib.sha256(s.encode('utf-8')).hexdigest()
def _sign(nonce,ts,qp,body,key,secret):
    d=_sha(nonce+ts+key+qp+body); return _sha(d+secret)

def bu_get(path,params):
    env=read_env(); key=env.get('BITUNIX_API_KEY',''); secret=env.get('BITUNIX_API_SECRET','')
    qp=''.join([f"{k}{params[k]}" for k in sorted(params.keys())])
    nonce,ts=_nonce(),_now_ms(); sign=_sign(nonce,ts,qp,'',key,secret)
    h={"api-key":key,"nonce":nonce,"timestamp":ts,"sign":sign,"language":"en-US","Content-Type":"application/json"}
    r=requests.get(f"{BASE_URL}{path}",params=params,headers=h,timeout=10); r.raise_for_status(); return r.json()

def fetch_price():
    sym=read_env().get('SYMBOL','BTCUSDT')
    j=requests.get(f"{BASE_URL}/api/v1/futures/market/tickers",params={"symbols":sym},timeout=10).json()
    for row in j.get('data') or []:
        if row.get('symbol')==sym: return Decimal(str(row['lastPrice']))
    return Decimal('0')

def fetch_unrealised():
    env=read_env(); sym=env.get('SYMBOL','BTCUSDT')
    try:
        j=bu_get('/api/v1/futures/account/positions',{"symbol":sym,"marginCoin":"USDT"})
        total=Decimal('0')
        for pos in j.get('data') or []:
            total+=Decimal(str(pos.get('unrealisedPnl','0')))
        return total
    except Exception:
        return Decimal('0')

# ---------- BASIC AUTH ----------
def need_auth():
    env=read_env(); return bool(env.get('PANEL_USER')) and bool(env.get('PANEL_PASS'))
def check_auth(auth):
    if not auth: return False
    env=read_env()
    return auth.username==env.get('PANEL_USER') and auth.password==env.get('PANEL_PASS')
def auth_required():
    return Response('Authentication required', 401, {'WWW-Authenticate':'Basic realm="GridPanel"'})
@app.before_request
def guard():
    if not need_auth():
        return
    if request.authorization and check_auth(request.authorization):
        return
    return auth_required()
# --------------------------------

LOG_PATH=os.path.join(BASE_DIR,'status.csv')
def logger_loop():
    while True:
        try:
            p=float(fetch_price()); u=float(fetch_unrealised()); ts=time.strftime('%Y-%m-%d %H:%M:%S')
            with open(LOG_PATH,'a') as f: f.write(f"{ts},{p},{u}\n")
        except Exception: pass
        time.sleep(int(read_env().get('STATUS_POLL_SEC','60')))
threading.Thread(target=logger_loop,daemon=True).start()

INDEX_HTML='''<!doctype html><html><head><meta charset="utf-8"><title>BitUnix Grid Control</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
body{font-family:sans-serif;max-width:820px;margin:20px auto;padding:10px}
fieldset{border:1px solid #ddd;padding:12px;border-radius:10px;margin-bottom:12px}
label{display:block;margin:6px 0 2px}
input,select{padding:8px;border:1px solid #ccc;border-radius:8px;width:100%}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
button{padding:10px 14px;margin:6px;border-radius:10px;border:1px solid #ccc;cursor:pointer}
pre{background:#f6f6f6;padding:10px;border-radius:10px;overflow:auto}
.small{font-size:12px;color:#666}
</style>
</head><body>
<h2>BitUnix Grid Control</h2>

<fieldset>
<legend>Settings</legend>
<div class="row">
  <div><label>GRID_LEVELS</label><select id="GRID_LEVELS"><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></div>
  <div><label>ORDER_NOTIONAL_PCT</label><input id="ORDER_NOTIONAL_PCT" type="number" step="0.01" min="0"></div>
</div>
<div class="row">
  <div><label>GRID_SPACING_PCT</label><input id="GRID_SPACING_PCT" type="number" step="0.01" min="0"></div>
  <div><label>MAX_GRID_NOTIONAL_USDT</label><input id="MAX_GRID_NOTIONAL_USDT" type="number" step="1" min="0"></div>
</div>
<div class="row">
  <div><label>LEVERAGE</label><input id="LEVERAGE" type="number" step="1" min="1" max="5"></div>
  <div><label>LIVE</label><select id="LIVE"><option value="0">0 (Dry-run)</option><option value="1">1 (Live)</option></select></div>
</div>
<div class="row">
  <div><label>STATUS_POLL_SEC</label><input id="STATUS_POLL_SEC" type="number" step="1" min="10"></div>
  <div><label>SYMBOL</label><input id="SYMBOL" type="text"></div>
</div>
<button onclick="save()">Save Settings</button>
<span class="small">Saving updates the .env file immediately.</span>
</fieldset>

<div>
<button onclick="act('status')">Status</button>
<button onclick="act('dryrun')">Place Grid (Dry-Run)</button>
<button onclick="act('golive')">Go Live + Place Grid</button>
<button onclick="act('recenter')">Re-center</button>
<button onclick="act('killswitch')" style="background:#fee">Kill-Switch</button>
<a href="/download" style="margin-left:8px">Download status.csv</a>
</div>

<pre id="out">Ready.</pre>

<script>
async function loadConfig(){
  const r=await fetch('/config'); const cfg=await r.json();
  const set=(id,def)=>{ const el=document.getElementById(id); if(!el) return; const v=cfg[id]??def; if(el.tagName==='SELECT'){ [...el.options].forEach(o=>o.selected=(o.value==v||o.text==v)); } else { el.value=v??''; } }
  set('GRID_LEVELS','1'); set('ORDER_NOTIONAL_PCT','0.07'); set('GRID_SPACING_PCT','0.25'); set('MAX_GRID_NOTIONAL_USDT','400');
  set('LEVERAGE','2'); set('LIVE','0'); set('STATUS_POLL_SEC','60'); set('SYMBOL','BTCUSDT');
}
async function save(){
  const ids=['GRID_LEVELS','ORDER_NOTIONAL_PCT','GRID_SPACING_PCT','MAX_GRID_NOTIONAL_USDT','LEVERAGE','LIVE','STATUS_POLL_SEC','SYMBOL'];
  const payload={}; ids.forEach(id=>payload[id]=document.getElementById(id).value);
  const r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  document.getElementById('out').textContent=await r.text();
}
async function act(path){ const r=await fetch('/'+path,{method:'POST'}); const t=await r.text(); document.getElementById('out').textContent=t; }
loadConfig();
</script>
</body></html>
'''

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/config')
def config():
    return jsonify(read_env())

@app.route('/save',methods=['POST'])
def save():
    data=request.get_json(force=True,silent=True) or {}
    whitelist={"GRID_LEVELS":int,"ORDER_NOTIONAL_PCT":float,"GRID_SPACING_PCT":float,"MAX_GRID_NOTIONAL_USDT":float,"LEVERAGE":int,"LIVE":int,"STATUS_POLL_SEC":int,"SYMBOL":str}
    for k,cast in whitelist.items():
        if k in data:
            try:
                v = cast(data[k]) if cast!=str else str(data[k])
                if k=="LIVE": v = 1 if int(v)==1 else 0
                set_env(k,v)
            except Exception:
                return jsonify({"error": f"bad value for {k}: {data[k]}"}), 400
    return jsonify({"saved": True, "env": read_env()})

@app.route('/status',methods=['POST'])
def status():
    env=read_env(); live=env.get('LIVE','0'); sym=env.get('SYMBOL','BTCUSDT')
    try: price=str(fetch_price()); pnl=str(fetch_unrealised())
    except Exception as e: price,pnl='0',f"err:{e}"
    return jsonify({"LIVE":live,"SYMBOL":sym,"price":price,"unrealised":pnl})

@app.route('/dryrun',methods=['POST'])
def dryrun():
    set_env('LIVE','0'); return run_cmd(['python','gridbot_v2.py'])

@app.route('/golive',methods=['POST'])
def golive():
    set_env('LIVE','1'); return run_cmd(['python','gridbot_v2.py'])

@app.route('/recenter',methods=['POST'])
def recenter():
    return run_cmd(['./recenter.sh'])

@app.route('/killswitch',methods=['POST'])
def killswitch():
    return run_cmd(['python','killswitch.py'])

@app.route('/download')
def download():
    if not os.path.exists(LOG_PATH): open(LOG_PATH,'a').close()
    return send_file(LOG_PATH,as_attachment=True,download_name='status.csv')

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.getenv('PORT','8080')))
