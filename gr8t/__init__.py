"""GR8T — a backtester for the trend / point-of-interest / entry strategy.

trend (50-SMA confluence on 1h+15m+5m) -> POI (multi-timeframe imbalance,
POC tie-breaker) -> entry (5m candle pattern) -> dynamic ATR-trailed risk.
"""
from .config import Config
from .backtest import Backtester, BacktestResult, Trade
from .strategy import Strategy, Signal
from .stats import compute_stats, format_stats

__all__ = [
    "Config", "Backtester", "BacktestResult", "Trade",
    "Strategy", "Signal", "compute_stats", "format_stats",
]
__version__ = "0.1.0"
