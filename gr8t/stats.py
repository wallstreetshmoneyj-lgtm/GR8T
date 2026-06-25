"""Performance statistics computed from a list of trades."""
from __future__ import annotations

from typing import Any

import numpy as np

from .config import Config
from .backtest import Trade


def _max_drawdown(curve: np.ndarray) -> float:
    """Max peak-to-trough drawdown of a cumulative curve (same units as curve)."""
    if curve.size == 0:
        return 0.0
    peaks = np.maximum.accumulate(curve)
    return float((peaks - curve).max())


def compute_stats(trades: list[Trade], cfg: Config) -> dict[str, Any]:
    n = len(trades)
    if n == 0:
        return {"trades": 0, "note": "no trades generated for these parameters"}

    r = np.array([t.r_multiple - cfg.cost_per_trade_r for t in trades], dtype=float)
    wins = r[r > 0]
    losses = r[r <= 0]
    cum_r = np.cumsum(r)

    # equity curve (compounded fixed-fractional risk)
    equity = cfg.starting_equity
    eq_curve = []
    for x in r:
        equity *= (1.0 + cfg.risk_per_trade * x)
        eq_curve.append(equity)
    eq_curve = np.array(eq_curve)

    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float("inf")

    # consecutive losses
    max_cons_loss = cur = 0
    for x in r:
        cur = cur + 1 if x <= 0 else 0
        max_cons_loss = max(max_cons_loss, cur)

    bars = np.array([t.bars_held for t in trades], dtype=float)
    be_rate = float(np.mean([t.reached_be for t in trades]))

    return {
        "trades": n,
        "wins": int((r > 0).sum()),
        "losses": int((r <= 0).sum()),
        "win_rate": float((r > 0).mean()),
        "expectancy_r": float(r.mean()),
        "total_r": float(r.sum()),
        "avg_win_r": float(wins.mean()) if wins.size else 0.0,
        "avg_loss_r": float(losses.mean()) if losses.size else 0.0,
        "payoff_ratio": (float(wins.mean() / -losses.mean())
                         if wins.size and losses.size else float("inf")),
        "profit_factor": profit_factor,
        "max_drawdown_r": _max_drawdown(cum_r),
        "best_trade_r": float(r.max()),
        "worst_trade_r": float(r.min()),
        "max_consecutive_losses": int(max_cons_loss),
        "avg_bars_held": float(bars.mean()),
        "breakeven_reached_rate": be_rate,
        "starting_equity": cfg.starting_equity,
        "ending_equity": float(eq_curve[-1]),
        "return_pct": float((eq_curve[-1] / cfg.starting_equity - 1.0) * 100.0),
        "max_drawdown_pct": float(
            _max_drawdown(eq_curve) / np.maximum.accumulate(eq_curve).max() * 100.0
        ),
        "risk_per_trade_pct": cfg.risk_per_trade * 100.0,
    }


def stats_series(trades: list[Trade], cfg: Config) -> dict[str, Any]:
    """Derived series for charts: equity, drawdown, cumulative R, per-trade R,
    an R-multiple histogram and monthly R totals."""
    import pandas as pd

    if not trades:
        return {"equity": [], "drawdown": [], "cum_r": [], "per_trade": [],
                "histogram": {"edges": [], "counts": [], "colors": []},
                "monthly": []}

    r = np.array([t.r_multiple - cfg.cost_per_trade_r for t in trades], dtype=float)
    cum_r = np.cumsum(r)

    equity = [cfg.starting_equity]
    eq = cfg.starting_equity
    for x in r:
        eq *= (1.0 + cfg.risk_per_trade * x)
        equity.append(eq)
    equity = np.array(equity)
    peaks = np.maximum.accumulate(equity)
    dd_pct = (equity / peaks - 1.0) * 100.0

    per_trade = []
    for i, t in enumerate(trades):
        per_trade.append({
            "n": i + 1,
            "r": round(float(r[i]), 3),
            "direction": t.direction,
            "pattern": t.pattern,
            "exit_time": (pd.Timestamp(t.exit_time).strftime("%Y-%m-%d %H:%M")
                          if t.exit_time is not None else ""),
        })

    # R-multiple histogram (fixed 0.5R buckets spanning the observed range)
    lo = float(np.floor(r.min() * 2) / 2)
    hi = float(np.ceil(r.max() * 2) / 2)
    edges = np.arange(lo, hi + 0.5, 0.5)
    if len(edges) < 2:
        edges = np.array([lo, lo + 0.5])
    counts, _ = np.histogram(r, bins=edges)
    colors = ["#1f9d55" if (edges[i] + edges[i + 1]) / 2 >= 0 else "#e3342f"
              for i in range(len(counts))]

    # monthly R totals
    monthly: dict[str, float] = {}
    for i, t in enumerate(trades):
        if t.exit_time is None:
            continue
        key = pd.Timestamp(t.exit_time).strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0.0) + float(r[i])
    monthly_list = [{"month": k, "r": round(v, 2)} for k, v in sorted(monthly.items())]

    return {
        "equity": [round(float(x), 2) for x in equity],
        "drawdown": [round(float(x), 2) for x in dd_pct],
        "cum_r": [round(float(x), 3) for x in cum_r],
        "per_trade": per_trade,
        "histogram": {
            "edges": [round(float(x), 2) for x in edges],
            "counts": [int(c) for c in counts],
            "colors": colors,
        },
        "monthly": monthly_list,
    }


def format_stats(stats: dict[str, Any]) -> str:
    if stats.get("trades", 0) == 0:
        return "No trades were generated for these parameters."
    rows = [
        ("Trades", f"{stats['trades']}  ({stats['wins']}W / {stats['losses']}L)"),
        ("Win rate", f"{stats['win_rate']*100:.1f}%"),
        ("Expectancy", f"{stats['expectancy_r']:+.3f} R / trade"),
        ("Total", f"{stats['total_r']:+.2f} R"),
        ("Avg win / loss", f"{stats['avg_win_r']:+.2f} R / {stats['avg_loss_r']:+.2f} R"),
        ("Payoff ratio", f"{stats['payoff_ratio']:.2f}"),
        ("Profit factor", f"{stats['profit_factor']:.2f}"),
        ("Max drawdown", f"{stats['max_drawdown_r']:.2f} R  ({stats['max_drawdown_pct']:.1f}%)"),
        ("Best / worst", f"{stats['best_trade_r']:+.2f} R / {stats['worst_trade_r']:+.2f} R"),
        ("Max consec. losses", f"{stats['max_consecutive_losses']}"),
        ("Reached break-even", f"{stats['breakeven_reached_rate']*100:.1f}%"),
        ("Avg bars held", f"{stats['avg_bars_held']:.1f}"),
        ("Equity", f"${stats['starting_equity']:,.0f} -> ${stats['ending_equity']:,.0f} "
                   f"({stats['return_pct']:+.1f}% @ {stats['risk_per_trade_pct']:.1f}% risk)"),
    ]
    w = max(len(k) for k, _ in rows)
    return "\n".join(f"  {k.ljust(w)} : {v}" for k, v in rows)
