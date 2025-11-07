import os, json, uuid, hashlib, requests, sys
from dotenv import load_dotenv
load_dotenv()
BASE="https://fapi.bitunix.com"
K=os.getenv("BITUNIX_API_KEY",""); S=os.getenv("BITUNIX_API_SECRET",""); SYM=os.getenv("SYMBOL","BTCUSDT")

def h(x): import hashlib; return hashlib.sha256(x.encode()).hexdigest()
def headers(q,b):
    qp="".join(f"{k}{q[k]}" for k in sorted(q)) if q else ""
    body=json.dumps(b,separators=(",",":"))
    n=uuid.uuid4().hex[:32]; ts=str(int(__import__("time").time()*1000))
    d=h(n+ts+K+qp+body); s=h(d+S)
    return {"api-key":K,"nonce":n,"timestamp":ts,"sign":s,"language":"en-US","Content-Type":"application/json"}, body

def req(m,path,q=None,b=None):
    q=q or {}; b=b or {}
    hd,bd=headers(q,b)
    r=requests.request(m,BASE+path,params=q,data=bd,headers=hd,timeout=15)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text}

def detail(sym, oid):
    tried=[]
    # Try multiple known detail routes
    for m,p,q,b in (
        ("POST","/api/v1/futures/trade/order_detail",{},{"symbol":sym,"orderId":oid}),
        ("GET" ,"/api/v1/futures/trade/order_detail",{"symbol":sym,"orderId":oid},{}),
        ("POST","/api/v1/futures/trade/orders",{},{"symbol":sym,"orderId":oid}),
        ("GET" ,"/api/v1/futures/trade/orders",{"symbol":sym,"orderId":oid},{}),
    ):
        sc,j = req(m,p,q,b); tried.append((p,sc,j))
        if sc==200 and str(j.get("code"))=="0":
            data=j.get("data")
            if isinstance(data, list) and data: return {"path":p,"status":"ok","data":data[0]}
            if isinstance(data, dict): return {"path":p,"status":"ok","data":data}
    # No success; return last try
    p,sc,j = tried[-1]
    return {"path":p,"status":"fail","http":sc,"resp":j}

if __name__=="__main__":
    oids = sys.argv[1:]
    if not oids:
        print("usage: python check_orders_by_id.py <orderId1> <orderId2> ...")
        sys.exit(1)
    out=[]
    for oid in oids:
        out.append({"orderId":oid, "detail": detail(SYM, oid)})
    print(json.dumps(out, indent=2))
