import os, time, json, uuid, hashlib, requests, sys
from dotenv import load_dotenv
load_dotenv()

BASE = "https://fapi.bitunix.com"
API_KEY = os.getenv("BITUNIX_API_KEY","")
SECRET  = os.getenv("BITUNIX_API_SECRET","")
SYMBOL  = os.getenv("SYMBOL","BTCUSDT")

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def sign_headers(query_params: dict, body_obj: dict):
    # Build query string in ASCII key order with no separators
    if query_params:
        qp = "".join(f"{k}{query_params[k]}" for k in sorted(query_params.keys()))
    else:
        qp = ""
    body = json.dumps(body_obj, separators=(",",":"))
    nonce = uuid.uuid4().hex[:32]
    ts = str(int(time.time()*1000))
    digest = sha256_hex(nonce + ts + API_KEY + qp + body)
    sign = sha256_hex(digest + SECRET)
    return {
        "api-key": API_KEY,
        "nonce": nonce,
        "timestamp": ts,
        "sign": sign,
        "language": "en-US",
        "Content-Type": "application/json",
    }, body

def post(path: str, body_obj: dict, query: dict=None):
    h, body = sign_headers(query or {}, body_obj)
    url = BASE + path
    r = requests.post(url, headers=h, params=(query or {}), data=body, timeout=15)
    txt = r.text
    # print raw on error for fast diagnosis
    try:
        j = r.json()
    except Exception:
        print(f"[HTTP] {r.status_code} {url}\n{txt}", file=sys.stderr)
        raise
    if r.status_code != 200 or j.get("code") not in (0, "0"):
        print(f"[HTTP] {r.status_code} {url}\n{json.dumps(j, indent=2)}", file=sys.stderr)
        raise RuntimeError(f"HTTP {r.status_code} code={j.get('code')} msg={j.get('msg')}")
    return j

def close_all(symbol: str):
    # POST /api/v1/futures/trade/close_all_position  (symbol optional)
    return post("/api/v1/futures/trade/close_all_position", {"symbol": symbol})

if __name__ == "__main__":
    try:
        resp = close_all(SYMBOL)
        print(json.dumps({"flatten":"sent","resp":resp}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
