"""Market data: a dependency-light Yahoo Finance client (plain `requests`, so it
honours the session proxy), timeframe resampling, no-look-ahead multi-timeframe
alignment, and a deterministic synthetic generator for offline tests.

We fetch the base (5m) series and resample up to 15m/1h. Resampling from one
source guarantees the timeframes are mutually consistent and lets us align them
without leaking future information.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import numpy as np
import pandas as pd
import requests

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_cache")

_OHLCV = ["open", "high", "low", "close", "volume"]


# ---------------------------------------------------------------------------
# Yahoo Finance
# ---------------------------------------------------------------------------
def fetch_yahoo(symbol: str, interval: str = "5m", rng: str = "60d",
                timeout: int = 30, retries: int = 3) -> pd.DataFrame:
    """Fetch OHLCV candles from Yahoo's public chart API.

    Returns a tz-aware (US/Eastern) DataFrame indexed by bar open time with
    columns open/high/low/close/volume. Raises on failure.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": interval, "range": rng, "includePrePost": "false"}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; GR8T/1.0)"}
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            r.raise_for_status()
            payload = r.json()
            return _parse_yahoo(payload)
        except Exception as e:  # noqa: BLE001 - surface after retries
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Yahoo fetch failed for {symbol}: {last_err}")


def _parse_yahoo(payload: dict) -> pd.DataFrame:
    chart = payload.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(f"Yahoo error: {chart['error']}")
    result = chart["result"][0]
    ts = result.get("timestamp")
    if not ts:
        raise RuntimeError("Yahoo returned no candles (symbol/interval/range?)")
    q = result["indicators"]["quote"][0]
    df = pd.DataFrame(
        {
            "open": q.get("open"),
            "high": q.get("high"),
            "low": q.get("low"),
            "close": q.get("close"),
            "volume": q.get("volume"),
        },
        index=pd.to_datetime(ts, unit="s", utc=True),
    )
    # normalise resolution to nanoseconds so downstream resample/merge_asof
    # never see mixed datetime units (Yahoo returns second-resolution stamps).
    df.index = df.index.tz_convert("US/Eastern").as_unit("ns")
    df.index.name = "time"
    df = df.dropna(subset=["open", "high", "low", "close"])
    df["volume"] = df["volume"].fillna(0.0)
    return df[_OHLCV]


def load_base(cfg, *, use_cache: bool = True, offline: bool = False) -> pd.DataFrame:
    """Load the base 5m series for cfg.symbol, with simple on-disk caching."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, f"{cfg.symbol}_{cfg.base_tf}_{cfg.period}.parquet")
    if offline:
        if os.path.exists(cache):
            return pd.read_parquet(cache)
        raise RuntimeError(f"offline mode but no cache at {cache}")
    if use_cache and os.path.exists(cache):
        age = time.time() - os.path.getmtime(cache)
        if age < 3600:  # 1h freshness
            return pd.read_parquet(cache)
    interval = _tf_to_yahoo(cfg.base_tf)
    rng = _clamp_range(interval, cfg.period)
    df = fetch_yahoo(cfg.symbol, interval=interval, rng=rng)
    try:
        df.to_parquet(cache)
    except Exception:  # parquet engine optional
        pass
    return df


# ---------------------------------------------------------------------------
# GitHub intraday history (OANDA CFDs via FutureSharks/financial-data)
# 1-minute bars from 2005-2018 -> lets us backtest real regimes (2008/2011/2015/
# 2018 selloffs) that Yahoo's 60-day 5m cap can't reach. SPX500_USD ~ ES proxy.
# ---------------------------------------------------------------------------
GITHUB_OANDA_BASE = ("https://raw.githubusercontent.com/FutureSharks/financial-data/"
                     "master/pyfinancialdata/data/currencies/oanda")

# friendly symbol -> OANDA instrument
GITHUB_SYMBOLS = {"SPX500": "SPX500_USD", "NAS100": "NAS100_USD",
                  "US2000": "US2000_USD", "JP225": "JP225_USD", "UK100": "UK100_GBP"}


def _month_iter(start: str, end: str):
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    y, m = sy, sm
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def fetch_oanda_month(instrument: str, year: int, month: int,
                      timeout: int = 30, retries: int = 3) -> pd.DataFrame:
    from io import StringIO
    url = f"{GITHUB_OANDA_BASE}/{instrument}/{year}/oanda-{instrument}-{year}-{month}.csv"
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            df = pd.read_csv(StringIO(r.text))
            # timestamps are UTC; convert to US/Eastern to match the pipeline
            idx = pd.to_datetime(df["time"], utc=True).dt.tz_convert("US/Eastern")
            df = df.assign(time=idx).set_index("time")[_OHLCV]
            df.index = df.index.as_unit("ns")
            df.index.name = "time"
            return df
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"github fetch failed {instrument} {year}-{month}: {last_err}")


def load_github(symbol: str, start: str, end: str, base_tf: str = "5min",
                use_cache: bool = True, offline: bool = False) -> pd.DataFrame:
    """Load a 1-minute GitHub series for [start, end] (months 'YYYY-MM'),
    resampled to base_tf. symbol is a friendly key (e.g. 'SPX500')."""
    instrument = GITHUB_SYMBOLS.get(symbol, symbol)
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, f"gh_{instrument}_{start}_{end}_{base_tf}.parquet")
    if (offline or use_cache) and os.path.exists(cache):
        return pd.read_parquet(cache)
    if offline:
        raise RuntimeError(f"offline but no cache at {cache}")
    parts = [fetch_oanda_month(instrument, y, m) for y, m in _month_iter(start, end)]
    one_min = pd.concat(parts).sort_index()
    one_min = one_min[~one_min.index.duplicated(keep="first")]
    one_min = one_min.dropna(subset=["open", "high", "low", "close"])
    base = resample(one_min, base_tf)
    try:
        base.to_parquet(cache)
    except Exception:  # noqa: BLE001
        pass
    return base


def _tf_to_yahoo(tf: str) -> str:
    return {"5min": "5m", "15min": "15m", "30min": "30m",
            "60min": "1h", "1h": "1h",
            "1D": "1d", "1d": "1d", "1day": "1d", "1wk": "1wk", "1W": "1wk"}.get(tf, "5m")


# Yahoo's history limit per base interval (the binding constraint on a run).
_MAX_RANGE_DAYS = {"5m": 60, "15m": 60, "30m": 60, "1h": 730, "1d": 100 * 365,
                   "1wk": 100 * 365}


def _clamp_range(interval: str, period: str) -> str:
    """Cap the requested period to what Yahoo will serve for this interval."""
    cap = _MAX_RANGE_DAYS.get(interval)
    if cap is None or not period.endswith("d"):
        return period
    try:
        days = int(period[:-1])
    except ValueError:
        return period
    return f"{min(days, cap)}d"


# ---------------------------------------------------------------------------
# Resampling & alignment
# ---------------------------------------------------------------------------
def resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Resample a base OHLCV frame to a higher timeframe.

    Uses label='left'/closed='left': a bar stamped 09:30 covers [09:30, 09:30+tf).
    Empty buckets (gaps/overnight) are dropped.
    """
    agg = {"open": "first", "high": "max", "low": "min",
           "close": "last", "volume": "sum"}
    out = df.resample(tf, label="left", closed="left", origin="start_day").agg(agg)
    out = out.dropna(subset=["open", "high", "low", "close"])
    out.index = out.index.as_unit("ns")
    return out


def bar_duration(tf: str) -> pd.Timedelta:
    return pd.Timedelta(tf.replace("min", "min").replace("h", "h"))


def align_trend(base: pd.DataFrame, htf: pd.DataFrame, tf: str,
                sma_period: int) -> pd.Series:
    """Project a higher-timeframe SMA-trend onto the base index without
    look-ahead.

    For each base bar we attach the trend of the most recently *completed* HTF
    bar. A HTF bar stamped L closes at L + tf; a base bar stamped t closes at
    t + base_tf. We merge on close-time with direction='backward'.
    """
    from .indicators import sma  # local import to avoid cycle at import time

    htf = htf.copy()
    htf_close_time = (htf.index + bar_duration(tf)).as_unit("ns")
    s = sma(htf["close"], sma_period)
    trend = np.where(htf["close"] > s, "bull",
                     np.where(htf["close"] < s, "bear", "none"))
    base_dt = (base.index[1] - base.index[0]) if len(base) > 1 else pd.Timedelta(0)
    left = pd.DataFrame({"close_time": (base.index + base_dt).as_unit("ns")})
    left = left.sort_values("close_time")
    right = pd.DataFrame({"close_time": htf_close_time, "trend": trend}).sort_values("close_time")
    merged = pd.merge_asof(left, right, on="close_time", direction="backward",
                           allow_exact_matches=True)
    out = pd.Series(merged["trend"].to_numpy(), index=base.index, name=f"trend_{tf}")
    return out.fillna("none")


# ---------------------------------------------------------------------------
# Synthetic data (deterministic) for tests / offline demos
# ---------------------------------------------------------------------------
def synthetic_series(n: int = 1200, seed: int = 7, start: str = "2024-01-02 09:30",
                     tf: str = "5min", drift: float = 0.02,
                     start_price: float = 100.0) -> pd.DataFrame:
    """Generate a reproducible trending 5m OHLCV series with realistic-ish bars."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start=start, periods=n, freq=tf, tz="US/Eastern")
    # gentle trend + noise random walk on the close
    steps = rng.normal(drift, 0.25, size=n)
    close = start_price + np.cumsum(steps)
    open_ = np.empty(n)
    open_[0] = start_price
    open_[1:] = close[:-1]
    spread = np.abs(rng.normal(0.15, 0.1, size=n)) + 0.05
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    vol = rng.integers(800, 5000, size=n).astype(float)
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )
    df.index.name = "time"
    return df
