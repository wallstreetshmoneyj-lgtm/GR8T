"""Imbalance (Fair Value Gap) detection and entry candle patterns.

Imbalance rules (per the strategy):
  * 3 consecutive candles, all the SAME color (when require_same_color).
  * A real gap between candle 1 and candle 3:
      - bullish: candle3.low  > candle1.high  (gap = [c1.high, c3.low])
      - bearish: candle3.high < candle1.low   (gap = [c3.high, c1.low])
  * The imbalance is only *confirmed* once candle 3 closes.

Candle patterns used for entries: bullish/bearish engulfing, hammer,
shooting star.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class Imbalance:
    tf: str
    direction: str        # "bull" or "bear"
    lower: float          # bottom of the gap zone
    upper: float          # top of the gap zone
    index: int            # positional index of candle 3 (creation bar)
    created_time: pd.Timestamp     # candle 3 open time
    confirm_time: pd.Timestamp     # when candle 3 closes (no look-ahead before this)
    same_color: bool = False       # were all three candles the same colour?
    mid: float = field(init=False)

    def __post_init__(self) -> None:
        self.mid = (self.lower + self.upper) / 2.0

    @property
    def size(self) -> float:
        return self.upper - self.lower

    def overlaps(self, other: "Imbalance") -> bool:
        return self.lower < other.upper and other.lower < self.upper


def _bar_color(o: float, c: float) -> str:
    if c > o:
        return "green"
    if c < o:
        return "red"
    return "doji"


def detect_imbalances(
    df: pd.DataFrame,
    tf: str,
    require_same_color: bool = True,
    min_gap: float = 0.0,
    direction: Optional[str] = None,
) -> list[Imbalance]:
    """Scan a single timeframe for imbalances.

    `confirm_time` is the close time of candle 3 = its open time + one bar.
    `min_gap` is an absolute price distance filter (0 disables).
    """
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    times = df.index
    # bar duration (for the confirm timestamp of the last bar of the window)
    if len(times) >= 2:
        bar_dt = times[1] - times[0]
    else:
        bar_dt = pd.Timedelta(0)

    out: list[Imbalance] = []
    for i in range(2, len(df)):
        a, b, d = i - 2, i - 1, i  # three candle indices
        colors = {_bar_color(o[a], c[a]), _bar_color(o[b], c[b]), _bar_color(o[d], c[d])}

        # bullish gap
        if (direction in (None, "bull")) and l[d] > h[a]:
            if (not require_same_color) or colors == {"green"}:
                gap = l[d] - h[a]
                if gap >= min_gap:
                    out.append(
                        Imbalance(
                            tf=tf, direction="bull", lower=float(h[a]), upper=float(l[d]),
                            index=d, created_time=times[d], confirm_time=times[d] + bar_dt,
                            same_color=(colors == {"green"}),
                        )
                    )
        # bearish gap
        if (direction in (None, "bear")) and h[d] < l[a]:
            if (not require_same_color) or colors == {"red"}:
                gap = l[a] - h[d]
                if gap >= min_gap:
                    out.append(
                        Imbalance(
                            tf=tf, direction="bear", lower=float(h[d]), upper=float(l[a]),
                            index=d, created_time=times[d], confirm_time=times[d] + bar_dt,
                            same_color=(colors == {"red"}),
                        )
                    )
    return out


# ---------------------------------------------------------------------------
# Candle patterns. Each returns a boolean (does bar `i` complete the pattern?).
# ---------------------------------------------------------------------------
def _body(o: float, c: float) -> float:
    return abs(c - o)


def is_bullish_engulfing(o, h, l, c, i: int) -> bool:
    if i < 1:
        return False
    prev_red = c[i - 1] < o[i - 1]
    cur_green = c[i] > o[i]
    engulf = (c[i] >= o[i - 1]) and (o[i] <= c[i - 1])
    bigger = _body(o[i], c[i]) > _body(o[i - 1], c[i - 1])
    return bool(prev_red and cur_green and engulf and bigger)


def is_bearish_engulfing(o, h, l, c, i: int) -> bool:
    if i < 1:
        return False
    prev_green = c[i - 1] > o[i - 1]
    cur_red = c[i] < o[i]
    engulf = (o[i] >= c[i - 1]) and (c[i] <= o[i - 1])
    bigger = _body(o[i], c[i]) > _body(o[i - 1], c[i - 1])
    return bool(prev_green and cur_red and engulf and bigger)


def is_hammer(o, h, l, c, i: int, wick_ratio=2.0, body_max=0.34, opp_max=0.25) -> bool:
    rng = h[i] - l[i]
    if rng <= 0:
        return False
    body = _body(o[i], c[i])
    upper_wick = h[i] - max(o[i], c[i])
    lower_wick = min(o[i], c[i]) - l[i]
    return bool(
        body <= body_max * rng
        and lower_wick >= wick_ratio * body
        and upper_wick <= opp_max * rng
    )


def is_shooting_star(o, h, l, c, i: int, wick_ratio=2.0, body_max=0.34, opp_max=0.25) -> bool:
    rng = h[i] - l[i]
    if rng <= 0:
        return False
    body = _body(o[i], c[i])
    upper_wick = h[i] - max(o[i], c[i])
    lower_wick = min(o[i], c[i]) - l[i]
    return bool(
        body <= body_max * rng
        and upper_wick >= wick_ratio * body
        and lower_wick <= opp_max * rng
    )


def entry_pattern(df: pd.DataFrame, i: int, direction: str, cfg) -> Optional[str]:
    """Return the name of the trend-aligned pattern completed at bar i, else None."""
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    wr, bm, om = cfg.wick_body_ratio, cfg.body_max_frac, cfg.opp_wick_max_frac
    if direction == "bull":
        if is_bullish_engulfing(o, h, l, c, i):
            return "bullish_engulfing"
        if is_hammer(o, h, l, c, i, wr, bm, om):
            return "hammer"
    elif direction == "bear":
        if is_bearish_engulfing(o, h, l, c, i):
            return "bearish_engulfing"
        if is_shooting_star(o, h, l, c, i, wr, bm, om):
            return "shooting_star"
    return None
