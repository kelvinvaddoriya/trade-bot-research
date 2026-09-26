"""Config loading. Values outside BOUNDS make the engine refuse to start (docs/05 §10)."""
import hashlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"

# (min, max). capital_cap_eur tops out at the owner's €1,000 decision: raising it needs a code change.
BOUNDS = {
    "capital_cap_eur": (100, 1000),
    "max_positions": (1, 20),
    "max_position_eur": (10, 1000),
    "min_order_eur": (1, 100),
    "risk_per_trade_pct": (0.001, 0.02),
    "max_daily_loss_pct": (0.005, 0.05),
    "max_drawdown_pct": (0.02, 0.25),
    "max_orders_per_day": (1, 50),
    "max_orders_per_minute": (1, 10),
    "price_collar_pct": (0.005, 0.10),
}


class ConfigError(Exception):
    pass


def _load(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return tomllib.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()[:12]


def load_risk(path: Path = CONFIG_DIR / "risk.toml") -> dict:
    cfg, digest = _load(path)
    for key, (lo, hi) in BOUNDS.items():
        v = cfg.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ConfigError(f"{path.name}: {key} missing or not a number")
        if not lo <= v <= hi:
            raise ConfigError(f"{path.name}: {key}={v} outside [{lo}, {hi}]")
    if cfg.get("allow_short") is not False:
        raise ConfigError(f"{path.name}: allow_short must be false")
    wl = cfg.get("whitelist")
    if not wl or not all(isinstance(s, str) for s in wl):
        raise ConfigError(f"{path.name}: whitelist must be a non-empty list of symbols")
    if cfg["max_position_eur"] > cfg["capital_cap_eur"] or cfg["min_order_eur"] >= cfg["max_position_eur"]:
        raise ConfigError(f"{path.name}: need min_order_eur < max_position_eur <= capital_cap_eur")
    cfg["hash"] = digest
    return cfg


def load_instruments(path: Path = CONFIG_DIR / "instruments.toml") -> dict:
    cfg, _ = _load(path)
    for sym, inst in cfg.items():
        for key in ("name", "isin", "market", "currency", "strategy", "yahoo"):
            if key not in inst:
                raise ConfigError(f"{path.name}: [{sym}] missing {key}")
        if inst["currency"] not in ("EUR", "USD"):
            raise ConfigError(f"{path.name}: [{sym}] currency must be EUR or USD")
    return cfg


def load_settings(path: Path = CONFIG_DIR / "settings.toml") -> dict:
    cfg, digest = _load(path)
    cfg["hash"] = digest
    return cfg
