"""News / event tagging for the studies.

There is no paid economic-calendar feed available here, so 'news' is approximated
two transparent, defensible ways and you can plug in a real calendar later:

  1. Volatility shocks (data-driven, no calendar): bars whose true range is far
     above its recent normal. This is *when impactful news actually hits the
     tape*, regardless of what the calendar said — robust and self-calibrating.

  2. The US release clock (schedule proxy): the windows around the standard
     Eastern-time release slots that dominate index futures —
       08:30 (CPI, PPI, NFP, Retail Sales, GDP, jobless claims, PCE),
       10:00 (ISM, JOLTS, consumer sentiment),
       14:00 (FOMC rate decision).

  3. Optional explicit calendar: pass a list/CSV of event timestamps to mark
     exactly (e.g. real FOMC/CPI datetimes) — these override the proxies.

All timestamps are interpreted in US/Eastern (the index tz used throughout).
"""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd

from .indicators import true_range

# (hour, minute) Eastern release slots that move ES/NQ the most
RELEASE_SLOTS = [(8, 30), (10, 0), (14, 0)]


def volatility_shock_mask(base: pd.DataFrame, k: float = 3.0,
                          window: int = 288) -> pd.Series:
    """True where true range exceeds k x its rolling median (a news/shock spike).
    window defaults to ~1 day of 5m bars."""
    tr = true_range(base)
    med = tr.rolling(window, min_periods=max(20, window // 4)).median()
    return (tr > k * med).fillna(False)


def release_window_mask(index: pd.DatetimeIndex, pad_min: int = 15,
                        slots: Iterable[tuple[int, int]] = RELEASE_SLOTS) -> pd.Series:
    """True for weekday bars within +/-pad_min of a standard ET release slot."""
    idx = pd.DatetimeIndex(index)
    minutes = idx.hour * 60 + idx.minute
    weekday = idx.weekday < 5
    hit = np.zeros(len(idx), dtype=bool)
    for h, m in slots:
        target = h * 60 + m
        hit |= np.abs(minutes - target) <= pad_min
    return pd.Series(hit & weekday, index=index)


def explicit_calendar_mask(index: pd.DatetimeIndex, events: Iterable,
                           pad_min: int = 15) -> pd.Series:
    """True for bars within +/-pad_min of any supplied event timestamp."""
    idx = pd.DatetimeIndex(index)
    out = np.zeros(len(idx), dtype=bool)
    pad = pd.Timedelta(minutes=pad_min)
    for ev in events:
        ts = pd.Timestamp(ev)
        if ts.tzinfo is None:
            ts = ts.tz_localize("US/Eastern")
        else:
            ts = ts.tz_convert("US/Eastern")
        out |= (idx >= ts - pad) & (idx <= ts + pad)
    return pd.Series(out, index=index)


def news_mask(base: pd.DataFrame, *, shock_k: float = 3.0, shock_window: int = 288,
              pad_min: int = 15, use_release_clock: bool = True,
              events: Optional[Iterable] = None) -> pd.Series:
    """Combined news mask: volatility shocks OR scheduled-release windows OR an
    explicit calendar (if supplied)."""
    mask = volatility_shock_mask(base, shock_k, shock_window)
    if use_release_clock:
        mask = mask | release_window_mask(base.index, pad_min)
    if events:
        mask = mask | explicit_calendar_mask(base.index, events, pad_min)
    return mask.reindex(base.index).fillna(False)
