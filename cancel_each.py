import os, time, json, uuid, hashlib, requests, sys
from dotenv import load_dotenv
load_dotenv()
BASE="https://fapi.bitunix.com"
K=os.getenv("BITUNIX_API_KEY","")
S=os.getenv("BITUNIX_API_SECRET","")
SYM=os.getenv("SYMBOL","BTCUSDT")
def h(x): return hashlib.sha256(x.encode()).hexdigest()
def headers(q,b):
    qp="".join(f"{k}{q[k]}" for k in sorted(q)) if q else ""
    body=json.dumps(b,separators=(",",":"))
    n=uuid.uuid4().hex[:32]; ts=str(int(time.time()*1000))
    d=h(n+ts+K+qp+body); s=h(d+S)
    return {"api-key":K,"nonce":n,"timestamp":ts,"sign":s,"language":"en-US","Content-Type":"application/json"}, body
def req(method,path,query=None,body=None):
    query=query or {}; body=body or {}
    hd, bd = headers(query, body)
    r = requests.request(method,BASE+path,params=query,data=bd,headers=hd,timeout=15)
    t=r.text
    try: j=r.json()
    except: print(t); raise
    if r.status_code!=200: print(json.dumps(j,indent=2)); raise SystemExit(1)
    return j
def open_orders(sym):
    try: j=req("POST","/api/v1/futures/trade/open_orders",{},{"symbol":sym})
    except: j=req("GET","/api/v1/futures/trade/open_orders",{"symbol":sym},{})
    return j.get("data") or []
def cancel_order(sym,oid):
    try: return req("POST","/api/v1/futures/trade/cancel_order",{},{"symbol":sym,"orderId":oid})
    except: return req("POST","/api/v1/futures/trade/cancel-order",{},{"symbol":sym,"orderId":oid})
if __name__=="__main__":
    orders=open_orders(SYM)
    for o in orders:
        oid=str(o.get("orderId") or o.get("id") or o.get("order_id"))
        if oid:
            print(json.dumps(cancel_order(SYM,oid)))
