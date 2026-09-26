"""Technical indicators. All are causal: the value at bar t uses bars <= t only (tested)."""
import numpy as np
import pandas as pd


def _wilder(x: np.ndarray, n: int) -> np.ndarray:
    """Wilder smoothing: seed with the mean of the first n values, then avg = (avg*(n-1) + x) / n."""
    out = np.full(len(x), np.nan)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) < n:
        return out
    s = valid[0]
    out[s + n - 1] = x[s:s + n].mean()
    for i in range(s + n, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff().to_numpy()
    gain = _wilder(np.where(np.isnan(d), np.nan, np.clip(d, 0, None)), n)
    loss = _wilder(np.where(np.isnan(d), np.nan, np.clip(-d, 0, None)), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = 100 - 100 / (1 + gain / loss)
    r = np.where(loss == 0, np.where(gain == 0, 50.0, 100.0), r)   # no losses: 100; flat: 50
    return pd.Series(np.where(np.isnan(gain), np.nan, r), index=close.index)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int) -> pd.Series:
    prev = close.shift()
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return pd.Series(_wilder(tr.to_numpy(dtype=float), n), index=close.index)


def bollinger_lower(close: pd.Series, n: int, k: float) -> pd.Series:
    return sma(close, n) - k * close.rolling(n, min_periods=n).std(ddof=0)


def volatility(close: pd.Series, n: int) -> pd.Series:
    """Standard deviation of daily returns over n bars."""
    return close.pct_change().rolling(n, min_periods=n).std()
