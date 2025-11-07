import os, json, uuid, hashlib, requests, time
from dotenv import load_dotenv
load_dotenv()
BASE="https://fapi.bitunix.com"; K=os.getenv("BITUNIX_API_KEY",""); S=os.getenv("BITUNIX_API_SECRET",""); SYM=os.getenv("SYMBOL","BTCUSDT")
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
    r.raise_for_status()
    return r.json()
def fills(sym, limit=50):
    for m,p,q,b in (
        ("POST","/api/v1/futures/trade/fills",{},{"symbol":sym,"limit":limit}),
        ("GET" ,"/api/v1/futures/trade/fills",{"symbol":sym,"limit":limit},{})
    ):
        try:
            j=req(m,p,q,b)
            if str(j.get("code"))=="0": return j.get("data") or []
        except Exception:
            pass
    return []
if __name__=="__main__":
    data=fills(os.getenv("SYMBOL","BTCUSDT"), limit=50)
    print(json.dumps(data, indent=2))
