"""Position sizing and order intents (docs/03 §3–5, docs/04 §3). EUR amounts, fractional quantities."""
from .models import OrderIntent, Signal, intent_id

ENTRY_LIMIT = 0.01      # entries are DAY limit orders at last close + 1 %: a big gap up means no fill


def size_entry(sig: Signal, budget_eur: float, cash_eur: float, capital_eur: float,
               strategy_cap_eur: float, risk: dict) -> tuple[float, float, str | None]:
    """Returns (qty, notional_eur, reason_if_zero). Notional is at the worst-case fill (the limit price),
    so no fill can exceed a cap.

    S1: budget x inverse-volatility weight.  S2: risk `risk_per_trade_pct` of capital between entry and stop.
    Then capped by the strategy's per-position cap, the global max position, and available cash.
    """
    worst = sig.close * (1 + ENTRY_LIMIT)
    if "weight" in sig.features:
        target = budget_eur * sig.features["weight"]
    else:
        if sig.stop_distance <= 0:
            return 0.0, 0.0, "no stop distance"
        target = risk["risk_per_trade_pct"] * capital_eur / sig.stop_distance * worst
    target = min(target, strategy_cap_eur, risk["max_position_eur"], cash_eur)
    if target < risk["min_order_eur"]:
        return 0.0, 0.0, "below minimum order"
    return target / worst, target, None


def make_intent(sig: Signal, qty: float) -> OrderIntent:
    iid = intent_id(sig.strategy, sig.symbol, sig.side, sig.bar_date)
    if sig.kind == "entry":
        limit = sig.close * (1 + ENTRY_LIMIT)
        return OrderIntent(iid, sig, qty, "limit", limit, qty * limit)
    return OrderIntent(iid, sig, qty, "market", None, qty * sig.close)
