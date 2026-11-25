import pytest

from tradebot.config import CONFIG_DIR, ConfigError, load_instruments, load_risk, load_settings


def test_shipped_config_loads():
    risk = load_risk()
    assert risk["capital_cap_eur"] == 1000 and len(risk["hash"]) == 12
    inst = load_instruments()
    assert set(risk["whitelist"]) == set(inst)          # one whitelist, one universe
    assert load_settings()["budgets_eur"]["s1_trend"] + load_settings()["budgets_eur"]["s2_pullback"] <= 1000


RISK = """capital_cap_eur = 1000
max_positions = 9
max_position_eur = 250
min_order_eur = 20
risk_per_trade_pct = 0.005
max_daily_loss_pct = 0.02
max_drawdown_pct = 0.10
max_orders_per_day = 10
max_orders_per_minute = 2
price_collar_pct = 0.02
allow_short = false
whitelist = ["SAP"]
"""


@pytest.mark.parametrize("old,new", [
    ("capital_cap_eur = 1000", "capital_cap_eur = 5000"),         # above the owner's cap
    ("max_drawdown_pct = 0.10", "max_drawdown_pct = 10"),         # percent typed as a whole number
    ("allow_short = false", "allow_short = true"),
    ('whitelist = ["SAP"]', "whitelist = []"),
    ("min_order_eur = 20", "min_order_eur = 300"),                # min order above max position
    ("max_positions = 9\n", ""),                                  # missing key
])
def test_bad_config_refuses_to_start(tmp_path, old, new):
    path = tmp_path / "risk.toml"
    path.write_text(RISK.replace(old, new), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_risk(path)


def test_hash_changes_with_content(tmp_path):
    path = tmp_path / "risk.toml"
    path.write_text(RISK, encoding="utf-8")
    h1 = load_risk(path)["hash"]
    path.write_text(RISK.replace("max_positions = 9", "max_positions = 8"), encoding="utf-8")
    assert load_risk(path)["hash"] != h1


def test_hash_ignores_line_endings(tmp_path):
    """git on Windows may check risk.toml out with CRLF; the limits hash must not change with it."""
    src = (CONFIG_DIR / "risk.toml").read_bytes().replace(b"\r\n", b"\n")
    lf, crlf = tmp_path / "lf.toml", tmp_path / "crlf.toml"
    lf.write_bytes(src)
    crlf.write_bytes(src.replace(b"\n", b"\r\n"))
    assert load_risk(lf)["hash"] == load_risk(crlf)["hash"]
