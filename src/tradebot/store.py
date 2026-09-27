"""SQLite journal and ledger (docs/04 §7). One file per environment (data/demo.db), WAL mode.

events: append-only journal.  orders: the ledger's view of every order, from PENDING (decided at a close,
sent at the next open) to the broker's final status.  lots: one position lot per entry fill.
"""
import datetime as dt
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts TEXT, type TEXT, entity TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS orders (
    key TEXT PRIMARY KEY, intent_id TEXT, role TEXT, strategy TEXT, symbol TEXT, ticker TEXT, lot TEXT,
    session TEXT, qty REAL, type TEXT, price REAL, stop_distance REAL, reason TEXT,
    status TEXT, done INTEGER DEFAULT 0, attempts INTEGER DEFAULT 0, broker_id INTEGER,
    filled_qty REAL DEFAULT 0, fill_price REAL, missing_since TEXT, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS lots (
    id TEXT PRIMARY KEY, strategy TEXT, symbol TEXT, ticker TEXT, qty REAL, entry_price REAL, entry_date TEXT,
    stop_price REAL, status TEXT, exit_price REAL, exit_date TEXT, exit_reason TEXT, pnl REAL);
"""


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path, timeout=30, isolation_level=None)      # autocommit: every write is durable
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.executescript(SCHEMA)

    def event(self, type_: str, entity: str = "", **payload) -> None:
        self.con.execute("INSERT INTO events (ts, type, entity, payload) VALUES (?,?,?,?)",
                         (now(), type_, entity, json.dumps(payload, default=str)))

    def events(self, where: str = "1", *args) -> list[dict]:
        rows = self.con.execute(f"SELECT * FROM events WHERE {where} ORDER BY id", args).fetchall()
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]

    def insert(self, table: str, **row) -> None:
        self.con.execute(f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join('?' * len(row))})", tuple(row.values()))

    def update(self, table: str, key: str, **fields) -> None:
        col = "key" if table == "orders" else "id"
        if table == "orders":
            fields.setdefault("updated", now())
        self.con.execute(f"UPDATE {table} SET {','.join(f'{k}=?' for k in fields)} WHERE {col}=?", (*fields.values(), key))

    def select(self, table: str, where: str = "1", *args) -> list[dict]:
        return [dict(r) for r in self.con.execute(f"SELECT * FROM {table} WHERE {where}", args).fetchall()]

    def order(self, key: str) -> dict | None:
        rows = self.select("orders", "key=?", key)
        return rows[0] if rows else None

    def lot(self, lot_id: str) -> dict | None:
        rows = self.select("lots", "id=?", lot_id)
        return rows[0] if rows else None
