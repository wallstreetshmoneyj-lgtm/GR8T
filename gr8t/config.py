"""Configuration for the GR8T strategy and backtester.

A single flat dataclass holds every tunable parameter so it can be round-tripped
to/from a dict (the web UI sends params as JSON) and stored alongside results.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, fields
from typing import Any, Optional


@dataclass
class Config:
    # ----- Instrument / data -------------------------------------------------
    symbol: str = "SPY"
    # How much history to pull for the *base* (5m) timeframe. Yahoo caps 5m at
    # ~60 days. Higher timeframes are resampled from the base so they always
    # align perfectly with no look-ahead.
    period: str = "60d"

    # ----- Timeframes (pandas offset aliases) --------------------------------
    base_tf: str = "5min"   # entry timeframe
    mid_tf: str = "15min"   # POI / volume-profile timeframe
    high_tf: str = "60min"  # top-level trend / POI timeframe

    # ----- Trend (rule 1) ----------------------------------------------------
    sma_period: int = 50    # price > SMA => bullish, price < SMA => bearish

    # ----- Imbalance / Fair Value Gap (rule 2) -------------------------------
    require_same_color: bool = True   # all 3 candles must share the trend color
    min_gap_atr: float = 0.0          # ignore gaps smaller than this * ATR (0=off)
    require_mtf: bool = True          # require a nested imbalance on another TF
    # Pairs of (higher, lower) timeframes that can form a multi-TF imbalance.
    # Defaults: 1h contains 15m, 1h contains 5m, 15m contains 5m.

    # ----- Volume profile / POC tie-breaker ----------------------------------
    vp_bins: int = 48                 # price buckets for the 15m volume profile
    swing_lookback: int = 5           # pivot strength for swing/leg detection

    # ----- Entry patterns (rule 3) -------------------------------------------
    wick_body_ratio: float = 2.0      # hammer/star: long wick >= ratio * body
    body_max_frac: float = 0.34       # hammer/star: body <= frac of total range
    opp_wick_max_frac: float = 0.25   # hammer/star: opposite wick small

    # ----- Risk model (dynamic ATR trail) ------------------------------------
    atr_period: int = 14
    atr_mult: float = 1.0             # trail distance = atr_mult * ATR
    stop_mode: str = "poi"            # "poi" (zone edge) or "signal" (candle)
    stop_buffer_atr: float = 0.1      # extra room beyond the initial stop
    breakeven_at_r: float = 1.0       # move to break-even once this R is reached
    one_position: bool = True         # only one trade open at a time
    max_bars_in_trade: Optional[int] = None  # force-exit after N bars (None=off)

    # ----- Money management (for the equity curve) ---------------------------
    starting_equity: float = 10_000.0
    risk_per_trade: float = 0.01      # fraction of equity risked per trade
    cost_per_trade_r: float = 0.0     # round-trip cost expressed in R

    # -------------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Config":
        known = {f.name for f in fields(cls)}
        clean: dict[str, Any] = {}
        for k, v in (d or {}).items():
            if k not in known:
                continue
            # coerce numeric strings coming from the web form
            cur = getattr(cls, k, None)
            if isinstance(cur, bool):
                clean[k] = v in (True, "true", "True", "on", 1, "1")
            elif isinstance(cur, int) and not isinstance(cur, bool):
                clean[k] = int(v) if v not in (None, "") else cur
            elif isinstance(cur, float):
                clean[k] = float(v) if v not in (None, "") else cur
            else:
                clean[k] = v
        return cls(**clean)

    @property
    def tf_order(self) -> list[str]:
        """Timeframes from highest to lowest."""
        return [self.high_tf, self.mid_tf, self.base_tf]
