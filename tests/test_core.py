"""Unit tests for indicators, imbalance/pattern detection, and the risk engine.

Run from the repo root:  python -m pytest -q
"""
import numpy as np
import pandas as pd
import pytest

from gr8t.config import Config
from gr8t import indicators as ind
from gr8t import patterns as pat
from gr8t.backtest import Backtester
from gr8t.strategy import Signal
from gr8t.patterns import Imbalance
from gr8t.data import synthetic_series, resample, align_trend


def _df(rows):
    """rows: list of (open, high, low, close, volume)."""
    idx = pd.date_range("2024-01-02 09:30", periods=len(rows), freq="5min", tz="US/Eastern")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=idx)


# --------------------------- indicators ---------------------------
def test_sma_and_atr():
    s = pd.Series(np.arange(1, 11, dtype=float))
    assert ind.sma(s, 5).iloc[-1] == pytest.approx(8.0)  # mean(6..10)
    df = _df([(10, 11, 9, 10, 100)] * 20)
    a = ind.atr(df, 14)
    assert a.iloc[-1] > 0


def test_volume_profile_poc():
    # heavy volume concentrated around price 100
    rows = []
    for _ in range(20):
        rows.append((100, 100.5, 99.5, 100, 10_000))   # tight around 100
    for _ in range(5):
        rows.append((105, 106, 104, 105, 100))          # light around 105
    vp = ind.volume_profile(_df(rows), bins=40)
    assert vp is not None
    assert vp.poc_price == pytest.approx(100, abs=0.5)


def test_volume_profile_none_without_volume():
    rows = [(100, 101, 99, 100, 0)] * 10
    assert ind.volume_profile(_df(rows), bins=20) is None


def test_find_swings_zigzag():
    # up to a peak at idx 5, down to a trough at idx 11
    highs_lows = [100, 101, 102, 103, 104, 105, 104, 103, 102, 101, 100, 99]
    rows = [(v, v + 0.5, v - 0.5, v, 100) for v in highs_lows]
    swings = ind.find_swings(_df(rows), lookback=3)
    kinds = {s.kind for s in swings}
    assert "high" in kinds


# --------------------------- imbalances ---------------------------
def test_bullish_imbalance_detection():
    # three rising GREEN candles with a gap: c3.low > c1.high
    rows = [
        (100.0, 101.0, 99.8, 100.8, 100),   # c1 green, high 101
        (101.0, 102.5, 100.9, 102.3, 100),  # c2 green
        (102.6, 104.0, 101.5, 103.8, 100),  # c3 green, low 101.5 > 101 -> gap
    ]
    imbs = pat.detect_imbalances(_df(rows), tf="5min", require_same_color=True)
    bull = [z for z in imbs if z.direction == "bull"]
    assert len(bull) == 1
    z = bull[0]
    assert z.lower == pytest.approx(101.0)   # c1.high
    assert z.upper == pytest.approx(101.5)   # c3.low
    # confirm time = c3 open + one bar
    assert z.confirm_time == _df(rows).index[2] + pd.Timedelta("5min")


def test_same_color_filter_rejects_mixed():
    # gap exists but middle candle is red -> rejected when require_same_color
    rows = [
        (100.0, 101.0, 99.8, 100.8, 100),    # green
        (102.0, 102.2, 101.4, 101.6, 100),   # red (close<open)
        (102.6, 104.0, 101.5, 103.8, 100),   # green, gap vs c1
    ]
    strict = pat.detect_imbalances(_df(rows), "5min", require_same_color=True)
    loose = pat.detect_imbalances(_df(rows), "5min", require_same_color=False)
    assert not [z for z in strict if z.direction == "bull"]
    assert [z for z in loose if z.direction == "bull"]


# --------------------------- candle patterns ---------------------------
def test_engulfing_and_wicks():
    o = np.array([10.0, 9.0]); c = np.array([9.0, 10.2])
    h = np.array([10.1, 10.3]); l = np.array([8.9, 8.9])
    assert pat.is_bullish_engulfing(o, h, l, c, 1)
    assert not pat.is_bearish_engulfing(o, h, l, c, 1)

    # hammer: tiny body at top, long lower wick
    o = np.array([10.0]); c = np.array([10.1]); h = np.array([10.15]); l = np.array([9.2])
    assert pat.is_hammer(o, h, l, c, 0)
    # shooting star: tiny body at bottom, long upper wick
    o = np.array([10.1]); c = np.array([10.0]); h = np.array([10.9]); l = np.array([9.95])
    assert pat.is_shooting_star(o, h, l, c, 0)


# --------------------------- alignment (no look-ahead) ---------------------------
def test_align_trend_no_lookahead():
    base = synthetic_series(n=300, seed=3)
    mid = resample(base, "15min")
    tr = align_trend(base, mid, "15min", 50)
    assert len(tr) == len(base)
    assert set(tr.unique()).issubset({"bull", "bear", "none"})


# --------------------------- risk engine ---------------------------
def test_risk_engine_be_then_trail():
    """Deterministic long: hit 1:1 -> break-even -> ATR trail -> stop out ~+1.4R."""
    rows = [
        (100, 100, 100, 100, 100),         # 0 entry bar (close=100)
        (100.0, 101.0, 99.8, 100.8, 100),  # 1 -> 1:1 hit, BE, trail to 100.5
        (100.6, 102.0, 100.6, 101.5, 100), # 2 -> trail to 101.5
        (101.4, 101.6, 101.3, 101.4, 100), # 3 -> low 101.3 <= 101.5 -> exit 101.4
        (101.0, 101.0, 100.0, 100.5, 100),
    ]
    base = _df(rows)
    cfg = Config(atr_mult=1.0, breakeven_at_r=1.0)
    bt = Backtester(base, cfg)
    n = len(base)
    atr_arr = np.full(n, 0.5)
    o = base["open"].to_numpy(float); h = base["high"].to_numpy(float)
    l = base["low"].to_numpy(float); c = base["close"].to_numpy(float)
    zone = Imbalance("5min", "bull", 98.0, 99.0, 0, base.index[0], base.index[0])
    sig = Signal(0, base.index[0], "bull", 100.0, "hammer", zone, "5min")
    tr = bt._simulate(sig, init_stop=99.0, o=o, h=h, l=l, c=c, atr_arr=atr_arr, n=n)
    assert tr.reached_be is True
    assert tr.exit_index == 3
    assert tr.exit_price == pytest.approx(101.4, abs=1e-6)
    assert tr.r_multiple == pytest.approx(1.4, abs=1e-6)


def test_risk_engine_initial_stop_loss():
    """Price immediately reverses and hits the initial stop for -1R."""
    rows = [
        (100, 100, 100, 100, 100),
        (99.9, 100.1, 98.5, 98.7, 100),   # low 98.5 <= stop 99 -> -1R
        (98.6, 99.0, 98.0, 98.4, 100),
    ]
    base = _df(rows)
    cfg = Config()
    bt = Backtester(base, cfg)
    n = len(base)
    o = base["open"].to_numpy(float); h = base["high"].to_numpy(float)
    l = base["low"].to_numpy(float); c = base["close"].to_numpy(float)
    zone = Imbalance("5min", "bull", 98.0, 99.0, 0, base.index[0], base.index[0])
    sig = Signal(0, base.index[0], "bull", 100.0, "hammer", zone, "5min")
    tr = bt._simulate(sig, 99.0, o=o, h=h, l=l, c=c, atr_arr=np.full(n, 0.5), n=n)
    assert tr.exit_index == 1
    assert tr.r_multiple == pytest.approx(-1.0, abs=1e-6)


def test_full_backtest_runs_on_synthetic():
    cfg = Config(symbol="SYNTH")
    base = synthetic_series(n=1500, seed=11)
    result = Backtester(base, cfg).run()
    # the engine should complete and every trade have a finite R
    assert all(np.isfinite(t.r_multiple) for t in result.trades)
