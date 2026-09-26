"""Read-only check that the keys in .env work. Prints pass/fail only, never the keys."""
import base64
import json
import pathlib
import urllib.error
import urllib.request

ENV = pathlib.Path(__file__).with_name(".env")


def load_env():
    env = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None
    except OSError as e:
        return None, str(e)


def check_t212(env):
    key, secret = env.get("T212_DEMO_API_KEY"), env.get("T212_DEMO_API_SECRET")
    if not key or not secret:
        return "FAIL  missing T212_DEMO_API_KEY or T212_DEMO_API_SECRET"
    auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    status = None
    for path in ("/equity/account/summary", "/equity/account/cash"):  # summary is newer; cash is the older endpoint
        status, body = get("https://demo.trading212.com/api/v0" + path, headers)
        if status == 200:
            return "OK    demo account reachable (a live key would be rejected here, so this is a practice key)"
        if status != 404:
            break
    hint = {401: "key/secret wrong, or it's a live key", 403: "key lacks 'account' permission",
            429: "rate limited, wait a minute and retry"}.get(status, body if status is None else "")
    return f"FAIL  HTTP {status} {hint}"


def check_alpaca(env):
    key, secret = env.get("APCA_API_KEY_ID"), env.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        return ["FAIL  missing APCA_API_KEY_ID or APCA_API_SECRET_KEY"]
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    out = []
    status, body = get("https://data.alpaca.markets/v2/stocks/bars/latest?symbols=AAPL&feed=iex", headers)
    if status == 200 and body and body.get("bars", {}).get("AAPL"):
        bar = body["bars"]["AAPL"]
        out.append(f"OK    market data: AAPL latest bar {bar['t']} close {bar['c']}")
    else:
        out.append(f"FAIL  market data HTTP {status}" + (" (key/secret wrong)" if status in (401, 403) else ""))
    status, body = get("https://data.alpaca.markets/v1beta1/news?symbols=AAPL&limit=1", headers)
    if status == 200 and body is not None:
        out.append(f"OK    news: {len(body.get('news', []))} AAPL headline(s) returned")
    else:
        out.append(f"FAIL  news HTTP {status}")
    return out


if __name__ == "__main__":
    env = load_env()
    print("Trading 212 (demo):", check_t212(env))
    for line in check_alpaca(env):
        print("Alpaca:            ", line)
