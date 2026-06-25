"""Backtest engine: turns strategy Signals into simulated trades, applying the
dynamic risk model (initial POI stop -> break-even at 1:1 -> ATR trail on each
new closed high/low) and producing trades + an equity curve.

Intrabar assumptions (conservative): within a bar the stop is checked before
the target; a level moved this bar (break-even / new trail) only takes effect
from the next bar; gaps through the stop fill at the bar open.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np
import pandas as pd

from .config import Config
from .patterns import Imbalance
from .strategy import Strategy, Signal


@dataclass
class Trade:
    direction: str
    entry_index: int
    entry_time: pd.Timestamp
    entry_price: float
    init_stop: float
    risk: float                  # entry-to-stop distance (1R in price)
    pattern: str
    poi_tf: str
    exit_index: int = -1
    exit_time: Optional[pd.Timestamp] = None
    exit_price: float = float("nan")
    exit_reason: str = ""
    r_multiple: float = float("nan")
    bars_held: int = 0
    mae_r: float = 0.0           # max adverse excursion in R
    mfe_r: float = 0.0           # max favourable excursion in R
    reached_be: bool = False
    equity_after: float = float("nan")

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("entry_time", "exit_time"):
            if d[k] is not None:
                d[k] = pd.Timestamp(d[k]).isoformat()
        return d


class Backtester:
    def __init__(self, base: pd.DataFrame, cfg: Config):
        self.cfg = cfg
        self.base = base
        self.strategy = Strategy(base, cfg)

    def _initial_stop(self, sig: Signal, atr_i: float) -> Optional[float]:
        cfg = self.cfg
        bar = self.base.iloc[sig.index]
        buf = cfg.stop_buffer_atr * atr_i
        if sig.direction == "bull":
            base_stop = sig.poi.lower if cfg.stop_mode == "poi" else float(bar["low"])
            stop = min(base_stop, float(bar["low"])) - buf
            if stop >= sig.entry_price:
                return None
        else:
            base_stop = sig.poi.upper if cfg.stop_mode == "poi" else float(bar["high"])
            stop = max(base_stop, float(bar["high"])) + buf
            if stop <= sig.entry_price:
                return None
        return float(stop)

    def run(self) -> "BacktestResult":
        cfg = self.cfg
        base = self.base
        o = base["open"].to_numpy(float)
        h = base["high"].to_numpy(float)
        l = base["low"].to_numpy(float)
        c = base["close"].to_numpy(float)
        atr_arr = self.strategy.atr.to_numpy(float)
        n = len(base)

        trades: list[Trade] = []
        equity = cfg.starting_equity
        i = max(cfg.sma_period, cfg.atr_period)
        signals_log: list[Signal] = []

        while i < n:
            sig = self.strategy.evaluate(i)
            if sig is None:
                i += 1
                continue
            atr_i = atr_arr[i]
            if not np.isfinite(atr_i):
                i += 1
                continue
            init_stop = self._initial_stop(sig, atr_i)
            if init_stop is None:
                i += 1
                continue
            signals_log.append(sig)

            tr = self._simulate(sig, init_stop, o, h, l, c, atr_arr, n)
            # money management: risk a fixed fraction per trade
            equity *= (1.0 + cfg.risk_per_trade * tr.r_multiple)
            tr.equity_after = equity
            trades.append(tr)

            # one position at a time: resume after the exit bar
            i = (tr.exit_index + 1) if tr.exit_index >= 0 else (i + 1)

        return BacktestResult(cfg=cfg, base=base, strategy=self.strategy,
                              trades=trades, signals=signals_log,
                              equity_final=equity)

    def _simulate(self, sig: Signal, init_stop: float,
                  o, h, l, c, atr_arr, n) -> Trade:
        cfg = self.cfg
        d = sig.direction
        entry = sig.entry_price
        risk = abs(entry - init_stop)
        stop = init_stop
        be_done = False
        established = entry  # best closed extreme in our favour
        target1 = entry + cfg.breakeven_at_r * risk if d == "bull" else entry - cfg.breakeven_at_r * risk

        tr = Trade(direction=d, entry_index=sig.index, entry_time=sig.time,
                   entry_price=entry, init_stop=init_stop, risk=risk,
                   pattern=sig.pattern, poi_tf=sig.poi.tf)

        j = sig.index + 1
        while j < n:
            # --- MAE/MFE bookkeeping (in R) ---
            if d == "bull":
                tr.mae_r = min(tr.mae_r, (l[j] - entry) / risk)
                tr.mfe_r = max(tr.mfe_r, (h[j] - entry) / risk)
            else:
                tr.mae_r = min(tr.mae_r, (entry - h[j]) / risk)
                tr.mfe_r = max(tr.mfe_r, (entry - l[j]) / risk)

            # --- 1) stop check (conservative: before target) ---
            if d == "bull" and l[j] <= stop:
                fill = min(o[j], stop) if o[j] < stop else stop
                return self._close(tr, j, fill, "stop" if not be_done else "trail/be", entry, risk, be_done)
            if d == "bear" and h[j] >= stop:
                fill = max(o[j], stop) if o[j] > stop else stop
                return self._close(tr, j, fill, "stop" if not be_done else "trail/be", entry, risk, be_done)

            # --- 2) break-even at 1:1 ---
            if not be_done:
                if (d == "bull" and h[j] >= target1) or (d == "bear" and l[j] <= target1):
                    stop = entry  # move to break-even
                    be_done = True
                    tr.reached_be = True

            # --- 3) ATR trail on each new *closed* extreme (after BE) ---
            if d == "bull":
                established = max(established, h[j])
            else:
                established = min(established, l[j])
            if be_done and np.isfinite(atr_arr[j]):
                if d == "bull":
                    stop = max(stop, established - cfg.atr_mult * atr_arr[j])
                else:
                    stop = min(stop, established + cfg.atr_mult * atr_arr[j])

            # --- 4) optional max hold ---
            if cfg.max_bars_in_trade and (j - sig.index) >= cfg.max_bars_in_trade:
                return self._close(tr, j, c[j], "max_bars", entry, risk, be_done)

            j += 1

        # ran out of data -> close at last bar
        return self._close(tr, n - 1, c[n - 1], "eod", entry, risk, be_done)

    @staticmethod
    def _close(tr: Trade, j: int, price: float, reason: str,
               entry: float, risk: float, be_done: bool) -> Trade:
        tr.exit_index = j
        tr.exit_price = float(price)
        tr.exit_reason = reason
        tr.bars_held = j - tr.entry_index
        if tr.direction == "bull":
            tr.r_multiple = (price - entry) / risk
        else:
            tr.r_multiple = (entry - price) / risk
        return tr


@dataclass
class BacktestResult:
    cfg: Config
    base: pd.DataFrame
    strategy: Strategy
    trades: list[Trade]
    signals: list[Signal]
    equity_final: float

    def set_exit_times(self) -> None:
        for t in self.trades:
            if t.exit_index >= 0 and t.exit_time is None:
                t.exit_time = self.base.index[t.exit_index]

    @property
    def r_series(self) -> np.ndarray:
        return np.array([t.r_multiple for t in self.trades], dtype=float)
