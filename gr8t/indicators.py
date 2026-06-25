"""Pure indicator functions: SMA, ATR, swing pivots, volume profile / POC.

Everything here is side-effect free and operates on pandas objects so the
components can be unit-tested in isolation with synthetic data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


def sma(close: pd.Series, period: int) -> pd.Series:
    """Simple moving average."""
    return close.rolling(period, min_periods=period).mean()


def ema(close: pd.Series, period: int) -> pd.Series:
    """Exponential moving average (span convention, no warm-up bias)."""
    return close.ewm(span=period, adjust=False, min_periods=period).mean()


def moving_average(close: pd.Series, period: int, kind: str = "sma") -> pd.Series:
    return ema(close, period) if kind.lower() == "ema" else sma(close, period)


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Wilder's ATR (RMA of the true range)."""
    tr = true_range(df)
    # Wilder smoothing == EMA with alpha = 1/period.
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


@dataclass(frozen=True)
class Swing:
    index: int          # positional index of the pivot bar
    time: pd.Timestamp  # timestamp of the pivot bar
    price: float
    kind: str           # "high" or "low"
    confirm_index: int  # bar at which the pivot becomes confirmed (index+lookback)


def find_swings(df: pd.DataFrame, lookback: int) -> list[Swing]:
    """Fractal swing highs/lows.

    A swing high at i requires high[i] to be the maximum of the window
    [i-lookback, i+lookback]; symmetric for swing lows. A pivot is only
    *confirmed* `lookback` bars later, which the backtester respects to avoid
    look-ahead.
    """
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    times = df.index
    n = len(df)
    swings: list[Swing] = []
    for i in range(lookback, n - lookback):
        win_hi = highs[i - lookback : i + lookback + 1]
        win_lo = lows[i - lookback : i + lookback + 1]
        if highs[i] == win_hi.max() and (win_hi.argmax() == lookback):
            swings.append(Swing(i, times[i], float(highs[i]), "high", i + lookback))
        elif lows[i] == win_lo.min() and (win_lo.argmin() == lookback):
            swings.append(Swing(i, times[i], float(lows[i]), "low", i + lookback))
    return swings


@dataclass(frozen=True)
class LegRange:
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    low: float
    high: float


def current_leg_range(
    df: pd.DataFrame, lookback: int, as_of_index: Optional[int] = None
) -> Optional[LegRange]:
    """Define the 'current structure leg' for the volume profile.

    The leg spans from the earlier of {most recent confirmed swing high, most
    recent confirmed swing low} up to `as_of_index`. This captures the active
    swing the market is trading within. Returns None if there isn't enough
    structure yet.
    """
    if as_of_index is None:
        as_of_index = len(df) - 1
    if as_of_index < lookback * 2:
        return None

    # Only swings confirmed at/before as_of_index are visible.
    swings = [s for s in find_swings(df, lookback) if s.confirm_index <= as_of_index]
    last_high = next((s for s in reversed(swings) if s.kind == "high"), None)
    last_low = next((s for s in reversed(swings) if s.kind == "low"), None)
    if last_high is None or last_low is None:
        return None

    start_idx = min(last_high.index, last_low.index)
    seg = df.iloc[start_idx : as_of_index + 1]
    if seg.empty:
        return None
    return LegRange(
        start_time=seg.index[0],
        end_time=seg.index[-1],
        low=float(seg["low"].min()),
        high=float(seg["high"].max()),
    )


@dataclass(frozen=True)
class VolumeProfile:
    poc_price: float
    bin_centers: np.ndarray
    bin_volume: np.ndarray
    low: float
    high: float


def volume_profile(df: pd.DataFrame, bins: int) -> Optional[VolumeProfile]:
    """Build a volume profile by spreading each bar's volume uniformly across
    the price bins its high-low range overlaps. Returns None when volume is
    unavailable (e.g. cash indices report 0 volume)."""
    if df.empty:
        return None
    lo = float(df["low"].min())
    hi = float(df["high"].max())
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return None
    vol = df["volume"].fillna(0.0).to_numpy(dtype=float)
    if vol.sum() <= 0:
        return None

    edges = np.linspace(lo, hi, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2.0
    bin_vol = np.zeros(bins, dtype=float)
    bin_w = (hi - lo) / bins

    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    for j in range(len(df)):
        v = vol[j]
        if v <= 0:
            continue
        b_lo = int((lows[j] - lo) / bin_w)
        b_hi = int((highs[j] - lo) / bin_w)
        b_lo = max(0, min(bins - 1, b_lo))
        b_hi = max(0, min(bins - 1, b_hi))
        span = b_hi - b_lo + 1
        bin_vol[b_lo : b_hi + 1] += v / span

    poc_idx = int(bin_vol.argmax())
    return VolumeProfile(
        poc_price=float(centers[poc_idx]),
        bin_centers=centers,
        bin_volume=bin_vol,
        low=lo,
        high=hi,
    )
