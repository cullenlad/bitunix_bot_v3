import os, time, json, uuid, hashlib, requests, sys
from dotenv import load_dotenv
load_dotenv()
BASE="https://fapi.bitunix.com"
K=os.getenv("BITUNIX_API_KEY",""); S=os.getenv("BITUNIX_API_SECRET",""); SYM=os.getenv("SYMBOL","BTCUSDT")
h=lambda x: __import__("hashlib").sha256(x.encode()).hexdigest()
def headers(q,b):
    qp="".join(f"{k}{q[k]}" for k in sorted(q)) if q else ""
    body=json.dumps(b,separators=(",",":"))
    n=uuid.uuid4().hex[:32]; ts=str(int(time.time()*1000))
    d=h(n+ts+K+qp+body); s=h(d+S)
    return {"api-key":K,"nonce":n,"timestamp":ts,"sign":s,"language":"en-US","Content-Type":"application/json"}, body
def req(m,p,q=None,b=None):
    q=q or {}; b=b or {}
    hd,bd=headers(q,b); r=requests.request(m,BASE+p,params=q,data=bd,headers=hd,timeout=15)
    r.raise_for_status(); return r.json()
def list_triggers(sym):
    for m,p,q,b in (("POST","/api/v1/futures/trade/trigger/open_orders",{},{"symbol":sym}),
                    ("GET","/api/v1/futures/trade/trigger/open_orders",{"symbol":sym},{})):
        try: return (req(m,p,q,b).get("data") or [])
        except: pass
    return []
def cancel_trigger(sym,oid):
    for p in ("/api/v1/futures/trade/trigger/cancel_order","/api/v1/futures/trade/trigger/cancel-order"):
        try:
            j=req("POST",p,{},{"symbol":sym,"orderId":oid})
            if str(j.get("code"))=="0": return True
        except: pass
    return False
if __name__=="__main__":
    items=list_triggers(SYM)
    for o in items:
        oid=str(o.get("orderId") or o.get("id") or "")
        if oid:
            ok=cancel_trigger(SYM,oid)
            print(json.dumps({"cancel_trigger":oid,"ok":ok}))
    print(json.dumps({"remaining_triggers": len(list_triggers(SYM))}))
