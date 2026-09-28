"""Heartbeat and watchdog (docs/05 §5). The watchdog is its own process, started by Task Scheduler every minute.

Deliberately light (standard library only, no pandas): on 2026-09-28 the laptop ran out of memory, and a watchdog
that loaded pandas on every start took more than 5 minutes to run. `python -m tradebot watchdog` imports only this.
"""
import json
import os
import sys
import time

from . import execution, notify
from .config import DATA_DIR, DB_PATH, read_env
from .store import Store
from .trading212 import Trading212

HEARTBEAT = DATA_DIR / "heartbeat.json"
STALE_S = 60                       # the watchdog runs every minute, so a dead engine is caught within 2 minutes


def beat(state: str = "running") -> None:
    HEARTBEAT.parent.mkdir(exist_ok=True)
    HEARTBEAT.write_text(json.dumps({"ts": time.time(), "pid": os.getpid(), "state": state}), encoding="utf-8")


def heartbeat() -> dict | None:
    try:
        return json.loads(HEARTBEAT.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def engine_alive() -> bool:
    hb = heartbeat()
    return bool(hb) and hb["state"] == "running" and time.time() - hb["ts"] <= STALE_S


def check(broker, db, alert) -> str:
    """A stale 'running' heartbeat means the engine died or hung: trip the kill switch and cancel entry orders
    through our own broker session. Protective stops stay. A clean stop marks the heartbeat 'stopped'."""
    hb = heartbeat()
    if hb is None or hb["state"] != "running":
        return "engine not running (stopped cleanly or never started)"
    age = time.time() - hb["ts"]
    if age <= STALE_S:
        return f"ok: heartbeat {age:.0f} s old"
    execution.halt(broker, db, f"watchdog: engine heartbeat {age:.0f} s old", alert, by="watchdog")
    return f"stale ({age:.0f} s): kill switch tripped, entry orders cancelled"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    db, env = Store(DB_PATH), read_env()
    broker = Trading212(env["T212_DEMO_API_KEY"], env["T212_DEMO_API_SECRET"])
    print(check(broker, db, lambda t: notify.alert(db, env, t)))
