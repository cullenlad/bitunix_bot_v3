import os, json, uuid, hashlib, requests, time
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
    hd,bd=headers(q,b)
    r=requests.request(m,BASE+p,params=q,data=bd,headers=hd,timeout=15)
    try: j=r.json()
    except: return r.status_code, {"raw": r.text}
    return r.status_code, j

def list_open(sym):
    seen={}
    for m,p,q,b in (
        ("POST","/api/v1/futures/trade/open_orders",{},{"symbol":sym}),
        ("GET" ,"/api/v1/futures/trade/open_orders",{"symbol":sym},{}),
        ("POST","/api/v1/futures/trade/orders",{},{"symbol":sym,"status":"NEW"}),
        ("POST","/api/v1/futures/trade/orders",{},{"symbol":sym,"status":"PARTIALLY_FILLED"}),
        ("POST","/api/v1/futures/trade/trigger/open_orders",{},{"symbol":sym}),
        ("GET" ,"/api/v1/futures/trade/trigger/open_orders",{"symbol":sym},{})
    ):
        sc,j = req(m,p,q,b)
        data = j.get("data") if isinstance(j,dict) else None
        if isinstance(data,list):
            for x in data:
                oid=str(x.get("orderId") or x.get("id") or x.get("order_id") or "")
                if oid: seen[oid]=x
    return list(seen.values())

def position_qty(sym):
    sc,j = req("POST","/api/v1/futures/account/positions",{},{"symbol":sym})
    qty=0.0
    if isinstance(j,dict):
        for x in (j.get("data") or []):
            if str(x.get("symbol","")).upper()==sym.upper():
                for k in ("positionAmt","size","positionQty","qty"):
                    if k in x and x[k] is not None:
                        try: qty=float(x[k])
                        except: pass
                        break
    return qty

if __name__=="__main__":
    opens = list_open(os.getenv("SYMBOL","BTCUSDT"))
    qty = position_qty(os.getenv("SYMBOL","BTCUSDT"))
    print(json.dumps({"open_orders": len(opens),
                      "sample_open": opens[:2],
                      "position_qty": qty}, indent=2))
