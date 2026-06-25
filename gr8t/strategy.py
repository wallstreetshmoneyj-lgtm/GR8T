"""The GR8T strategy: trend confluence -> multi-timeframe imbalance POI ->
5m candle-pattern entry. Produces entry signals; position/risk management lives
in backtest.py.

All evaluation at base-bar i uses only information available at the close of
bar i (completed higher-timeframe bars, confirmed imbalances), so signals are
free of look-ahead bias.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .config import Config
from .data import resample, align_trend, bar_duration
from .indicators import sma, atr, current_leg_range, volume_profile
from .patterns import Imbalance, detect_imbalances, entry_pattern


@dataclass
class Signal:
    index: int
    time: pd.Timestamp
    direction: str
    entry_price: float
    pattern: str
    poi: Imbalance
    nested_tf: str
    poc: Optional[float] = None
    n_candidates: int = 1


class Strategy:
    def __init__(self, base: pd.DataFrame, cfg: Config):
        self.cfg = cfg
        self.base = base
        self._prepare()

    # ---- precompute everything that doesn't depend on the open position ----
    def _prepare(self) -> None:
        cfg, base = self.cfg, self.base
        self.base_dt = base.index[1] - base.index[0]
        # close time of each base bar, kept tz-aware so as-of searches are exact
        self.base_close_time = base.index + self.base_dt

        # higher timeframes (resampled from the base for perfect consistency)
        self.mid = resample(base, cfg.mid_tf)
        self.high = resample(base, cfg.high_tf)

        # trend per timeframe, aligned to the base index without look-ahead
        s5 = sma(base["close"], cfg.sma_period)
        self.trend_5 = pd.Series(
            np.where(base["close"] > s5, "bull",
                     np.where(base["close"] < s5, "bear", "none")),
            index=base.index,
        )
        self.trend_15 = align_trend(base, self.mid, cfg.mid_tf, cfg.sma_period)
        self.trend_1h = align_trend(base, self.high, cfg.high_tf, cfg.sma_period)

        conf = np.where(
            (self.trend_5.to_numpy() == self.trend_15.to_numpy())
            & (self.trend_15.to_numpy() == self.trend_1h.to_numpy())
            & (self.trend_5.to_numpy() != "none"),
            self.trend_5.to_numpy(), "none",
        )
        self.confluence = pd.Series(conf, index=base.index)

        self.atr = atr(base, cfg.atr_period)

        # imbalances on every timeframe
        frames = {cfg.base_tf: base, cfg.mid_tf: self.mid, cfg.high_tf: self.high}
        self.imbalances: list[Imbalance] = []
        for tf, df in frames.items():
            self.imbalances.extend(
                detect_imbalances(df, tf, require_same_color=cfg.require_same_color)
            )
        self._index_imbalances()

    def _index_imbalances(self) -> None:
        """Attach base-bar usability + invalidation indices to each imbalance."""
        base = self.base
        closes = base["close"].to_numpy(dtype=float)
        ct = self.base_close_time
        n = len(base)
        for imb in self.imbalances:
            # first base bar that closes strictly AFTER candle 3 -> price can return
            start = int(ct.searchsorted(imb.confirm_time, side="right"))
            imb_meta = {"usable_from": start, "invalid_from": n}
            if start < n:
                if imb.direction == "bull":
                    breach = closes[start:] < imb.lower
                else:
                    breach = closes[start:] > imb.upper
                if breach.any():
                    imb_meta["invalid_from"] = start + int(breach.argmax())
            imb._meta = imb_meta  # type: ignore[attr-defined]

    # ---- per-bar evaluation -------------------------------------------------
    def _active_pois(self, i: int) -> list[Imbalance]:
        """Imbalances, in the trend direction, that are confirmed, not yet
        invalidated, MTF-confirmed, and tapped by bar i."""
        direction = self.confluence.iloc[i]
        if direction == "none":
            return []
        bar = self.base.iloc[i]
        lo, hi = float(bar["low"]), float(bar["high"])

        live = [
            imb for imb in self.imbalances
            if imb.direction == direction
            and imb._meta["usable_from"] <= i < imb._meta["invalid_from"]  # type: ignore[attr-defined]
        ]
        # tapped by this bar (price trades into the zone)
        tapped = [imb for imb in live if lo <= imb.upper and hi >= imb.lower]
        if not tapped:
            return []

        if not self.cfg.require_mtf:
            return tapped

        # MTF: keep zones that overlap a confirmed imbalance on a *different* TF
        mtf: list[Imbalance] = []
        for imb in tapped:
            for other in live:
                if other.tf != imb.tf and imb.overlaps(other):
                    mtf.append(imb)
                    break
        return mtf

    def _poc_for_bar(self, i: int) -> Optional[float]:
        """POC of the 15m volume profile over the current structure leg, as of i."""
        t = self.base.index[i]
        mid_pos = int(self.mid.index.searchsorted(t, side="right")) - 1
        if mid_pos < 0:
            return None
        leg = current_leg_range(self.mid, self.cfg.swing_lookback, as_of_index=mid_pos)
        if leg is None:
            return None
        seg = self.mid.loc[leg.start_time: self.mid.index[mid_pos]]
        vp = volume_profile(seg, self.cfg.vp_bins)
        return vp.poc_price if vp else None

    def _select_poi(self, candidates: list[Imbalance], i: int) -> tuple[Imbalance, Optional[float], int]:
        """Apply the POC tie-breaker: the imbalance whose mid is closest to the
        15m POC. Falls back to the zone closest to current price when volume
        is unavailable."""
        if len(candidates) == 1:
            return candidates[0], None, 1
        poc = self._poc_for_bar(i)
        if poc is not None:
            best = min(candidates, key=lambda z: abs(z.mid - poc))
            return best, poc, len(candidates)
        price = float(self.base["close"].iloc[i])
        best = min(candidates, key=lambda z: abs(z.mid - price))
        return best, None, len(candidates)

    def evaluate(self, i: int) -> Optional[Signal]:
        cfg = self.cfg
        if i < cfg.sma_period or i < cfg.atr_period:
            return None
        direction = self.confluence.iloc[i]
        if direction == "none":
            return None
        pois = self._active_pois(i)
        if not pois:
            return None
        pattern = entry_pattern(self.base, i, direction, cfg)
        if pattern is None:
            return None
        poi, poc, n = self._select_poi(pois, i)
        return Signal(
            index=i,
            time=self.base.index[i],
            direction=direction,
            entry_price=float(self.base["close"].iloc[i]),
            pattern=pattern,
            poi=poi,
            nested_tf=poi.tf,
            poc=poc,
            n_candidates=n,
        )
