import os, json, uuid, hashlib, requests
from dotenv import load_dotenv
load_dotenv()
BASE="https://fapi.bitunix.com"; K=os.getenv("BITUNIX_API_KEY",""); S=os.getenv("BITUNIX_API_SECRET",""); SYM=os.getenv("SYMBOL","BTCUSDT")
h=lambda x: __import__("hashlib").sha256(x.encode()).hexdigest()
def headers(q,b):
    qp="".join(f"{k}{q[k]}" for k in sorted(q)) if q else ""
    body=json.dumps(b,separators=(",",":"))
    n=uuid.uuid4().hex[:32]; ts=str(int(__import__("time").time()*1000))
    d=h(n+ts+K+qp+body); s=h(d+S)
    return {"api-key":K,"nonce":n,"timestamp":ts,"sign":s,"language":"en-US","Content-Type":"application/json"}, body
def req(m,p,q=None,b=None):
    q=q or {}; b=b or {}
    hd,bd=headers(q,b); r=requests.request(m,BASE+p,params=q,data=bd,headers=hd,timeout=15); r.raise_for_status()
    return r.json().get("data") or []
def collect():
    out={}
    out["open_orders_post"]=req("POST","/api/v1/futures/trade/open_orders",{},{"symbol":SYM})
    out["open_orders_get"]=req("GET","/api/v1/futures/trade/open_orders",{"symbol":SYM},{})
    out["orders_NEW"]=req("POST","/api/v1/futures/trade/orders",{},{"symbol":SYM,"status":"NEW"})
    out["orders_PF"]=req("POST","/api/v1/futures/trade/orders",{},{"symbol":SYM,"status":"PARTIALLY_FILLED"})
    out["trigger_open_post"]=req("POST","/api/v1/futures/trade/trigger/open_orders",{},{"symbol":SYM})
    out["trigger_open_get"]=req("GET","/api/v1/futures/trade/trigger/open_orders",{"symbol":SYM},{})
    print(json.dumps({k:len(v) for k,v in out.items()},indent=2))
    for k,v in out.items():
        if v: print(f"\n== {k} =="); print(json.dumps(v,indent=2))
collect()
