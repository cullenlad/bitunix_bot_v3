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
    try: return r.status_code, r.json()
    except Exception: return r.status_code, {"raw": r.text}

def detail(sym, cid):
    tried=[]
    # Try with clientOrderId + common futures filters
    common_bodies = [
        {"symbol":sym,"clientOrderId":cid,"category":"linear","marginCoin":"USDT"},
        {"symbol":sym,"clientOrderId":cid},
    ]
    for body in common_bodies:
        for m,p in (("POST","/api/v1/futures/trade/order_detail"),
                    ("GET" ,"/api/v1/futures/trade/order_detail"),
                    ("POST","/api/v1/futures/trade/orders"),
                    ("GET" ,"/api/v1/futures/trade/orders")):
            q = body if m=="GET" else {}
            b = {} if m=="GET" else body
            sc,j = req(m,p,q,b); tried.append((p,sc,j))
            if sc==200 and str(j.get("code"))=="0" and j.get("data"):
                data=j["data"]
                if isinstance(data,list) and data: return {"ok":True,"path":p,"data":data[0]}
                if isinstance(data,dict): return {"ok":True,"path":p,"data":data}
    p,sc,j = tried[-1]
    return {"ok":False,"path":p,"http":sc,"resp":j}

if __name__=="__main__":
    ids=sys.argv[1:]
    if not ids:
        print("usage: python check_by_client_id.py <clientId1> ..."); sys.exit(1)
    out=[]
    for cid in ids:
        out.append({"clientId":cid,"detail":detail(SYM,cid)})
    print(json.dumps(out,indent=2))
