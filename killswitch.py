import os, time, json, uuid, hashlib, requests, sys
BASE = "https://fapi.bitunix.com"
K = os.getenv("BITUNIX_API_KEY",""); S = os.getenv("BITUNIX_API_SECRET",""); SYM = os.getenv("SYMBOL","BTCUSDT")
h=lambda x: __import__("hashlib").sha256(x.encode()).hexdigest()
def headers(q,b):
    qp="".join(f"{k}{q[k]}" for k in sorted(q)) if q else ""
    body=json.dumps(b,separators=(",",":"))
    n=uuid.uuid4().hex[:32]; ts=str(int(__import__("time").time()*1000))
    d=h(n+ts+K+qp+body); s=h(d+S)
    return {"api-key":K,"nonce":n,"timestamp":ts,"sign":s,"language":"en-US","Content-Type":"application/json"}, body
def req(method, path, query=None, body=None):
    query=query or {}; body=body or {}
    hd, bd = headers(query, body)
    r = requests.request(method, BASE+path, params=query, data=bd, headers=hd, timeout=15)
    try: j=r.json()
    except: return r.status_code, {"raw": r.text}, False
    return r.status_code, j, str(j.get("code")) in ("0",0)
def cancel_all(symbol):
    bodies=[{"symbol":symbol}, {}]
    paths=["/api/v1/futures/trade/cancel_all","/api/v1/futures/trade/cancelAll"]
    for p in paths:
        for b in bodies:
            for _ in (1,2):
                sc,j,ok = req("POST",p,{},b)
                if ok: return True, {"path":p,"body":b,"resp":j}
                time.sleep(0.3)
    return False, j
def list_open(symbol):
    seen={}
    def add(items):
        for x in items or []:
            oid=str(x.get("orderId") or x.get("id") or x.get("order_id") or "")
            if oid: seen[oid]=x
    for m,p,q,b in (
        ("POST","/api/v1/futures/trade/open_orders",{},{"symbol":symbol}),
        ("GET" ,"/api/v1/futures/trade/open_orders",{"symbol":symbol},{}),
        ("POST","/api/v1/futures/trade/orders",{},{"symbol":symbol,"status":"NEW"}),
        ("POST","/api/v1/futures/trade/orders",{},{"symbol":symbol,"status":"PARTIALLY_FILLED"}),
        ("POST","/api/v1/futures/trade/trigger/open_orders",{},{"symbol":symbol}),
        ("GET" ,"/api/v1/futures/trade/trigger/open_orders",{"symbol":symbol},{})
    ):
        sc,j,ok = req(m,p,q,b)
        if ok and isinstance(j.get("data"), list): add(j["data"])
    return list(seen.values())
def cancel_one(symbol, oid):
    bodies=[{"symbol":symbol,"orderId":oid},{"symbol":symbol,"clientOrderId":oid}]
    for p in ("/api/v1/futures/trade/cancel_order","/api/v1/futures/trade/cancel-order"):
        for b in bodies:
            sc,j,ok = req("POST",p,{},b)
            if ok: return True, {"path":p,"body":b,"resp":j}
    return False, {}
if __name__ == "__main__":
    ok, resp = cancel_all(SYM)
    print(json.dumps({"cancel_all": ("ok" if ok else "failed"), "resp": resp}, indent=2))
    time.sleep(0.4)
    before = list_open(SYM)
    print(json.dumps({"open_before": len(before)}))
    for o in before:
        oid=str(o.get("orderId") or o.get("id") or o.get("order_id") or "")
        if not oid: continue
        ok, info = cancel_one(SYM, oid)
        print(json.dumps({"cancelled": oid, "ok": ok, "info": info}))
        time.sleep(0.2)
    time.sleep(0.4)
    after = list_open(SYM)
    print(json.dumps({"open_after": len(after)}))
    sys.exit(0 if not after else 2)

def cancel_all_orders(symbol: str = None):
    """
    Backwards-compatible wrapper expected by gridbot_latest.py.
    Returns a simple (ok: bool, info: dict) tuple.
    """
    sym = symbol or os.getenv("SYMBOL","BTCUSDT")
    try:
        ok, info = cancel_all(sym)   # uses the robust cancel_all in this file
    except Exception as e:
        ok, info = False, {"error": str(e)}
    return ok, info
