"""Alerts and the dead-man's switch (docs/04 §12, docs/09 §5).

alert(): console + journal, plus Telegram when TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are in .env. The same text
goes to Telegram at most once an hour, so a persistent fault doesn't flood the phone.
ping(): healthchecks.io (HC_PING_URL). A missed ping alerts even when the whole laptop is down.
"""
import datetime as dt
import urllib.parse
import urllib.request


def _post(url: str, form: dict | None = None) -> bool:
    try:
        data = urllib.parse.urlencode(form).encode() if form else b""
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10).read()
        return True
    except Exception:                        # alerting must never take the engine down
        return False


def telegram(env: dict, text: str) -> bool:
    token, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    return bool(token and chat) and _post(f"https://api.telegram.org/bot{token}/sendMessage",
                                          {"chat_id": chat, "text": text[:4000]})


def alert(db, env: dict, text: str) -> None:
    print(f"ALERT {text}", flush=True)
    hour_ago = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)).isoformat(timespec="seconds")
    repeat = db.events("type='ALERT' AND ts>=? AND json_extract(payload, '$.text')=?", hour_ago, text)
    db.event("ALERT", text=text)
    if not repeat:
        telegram(env, f"TradeBot (demo): {text}")


def ping(env: dict, fail: bool = False) -> None:
    if env.get("HC_PING_URL"):
        _post(env["HC_PING_URL"] + ("/fail" if fail else ""))
