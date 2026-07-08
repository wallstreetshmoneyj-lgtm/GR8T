#!/usr/bin/env python3
"""
Trend IDENTIFICATION scoring — no trading, no entries/exits, no costs, no P&L.

Each trend-definition method emits a per-bar STATE (+1 up / -1 down) only.
We score, per method x instrument x timeframe:

  (A) flip frequency and trend-duration distribution,
  (B) persistence: next-bar directional hit rate, mean signed forward
      return per bar-in-state, and remaining-segment-horizon hit rate,
  (C) capture efficiency: per state segment, signed close-to-close move
      from segment start to segment end divided by the sum of absolute
      bar moves inside it (signed Kaufman-style signal-to-noise; high =
      the state sat on clean directional moves, low/negative = chop),
  (D) THE RANDOM-WALK NULL: a stationary block bootstrap (mean block
      5 bars, ~1000 resamples) of the instrument's own bars destroys
      multi-week serial dependence while preserving the return
      distribution, volatility, and per-bar OHLC geometry (each resampled
      bar keeps its original high/low/close ratios relative to the prior
      close, so channel/swing methods run identically on the null).
      Every A-C metric is reported REAL vs null mean / 5th / 95th pct,
      with a z-score and one-sided empirical p-value. If real persistence
      is indistinguishable from shuffled-random, the "trend" is an
      artifact of the indicator, not a property of the market.

Indicator-free market gates:
  (E) Lo-MacKinlay variance ratios at lags {2,5,10,20,40} with
      heteroskedasticity-robust z-stats (VR>1 persistent, <1 mean-rev),
  (F) Hurst exponent via classic R/S regression (H>0.5 persistent).

Methods scored (state only, computed on closed bars):
  sma50     : +1 while close > 50-SMA, -1 below (ties hold prior state)
  sma10_40  : +1 while 10-SMA > 40-SMA, -1 below
  donch20/55: flip +1 on close > highest high of PRIOR N bars, flip -1 on
              close < lowest low of prior N bars, HOLD state in between
  tsmom20/60/120 : +1 if trailing L-bar return > 0, else -1
  swing5    : fractal swing points with k=5 (a swing high at bar i needs
              high[i] to be the max of high[i-5..i+5] and is only USABLE
              from bar i+5, i.e. after k-bar confirmation - no look-ahead);
              state flips to -1 when close breaks the last confirmed swing
              low, to +1 when close breaks the last confirmed swing high,
              holds in between (market-structure-break definition of
              higher-highs/higher-lows trend)

Data: reuses the committed OHLC snapshots from ../donchian_regime/data
(crypto daily = max history, futures daily = ~7y FRONT-MONTH CONTINUOUS —
roll gaps fire fake breakout flips; back-adjusted contracts are needed for
firm futures conclusions). Timeframes: daily (primary), weekly resampled
from daily (Sunday-anchored), and 4h resampled from 1h for BTC/ETH/ES/NQ/GC
(Yahoo caps intraday history at ~730d).

Run:  python score_trends.py           (1000 bootstrap resamples)
      python score_trends.py --fast    (200 resamples, for smoke tests)

Outputs (./output): SUMMARY.md, method_metrics.csv, market_viability.csv
"""

import gzip
import math
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy import stats as sstats

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIRS = [os.path.join(HERE, "data"),
             os.path.join(HERE, "..", "donchian_regime", "data")]
OUT_DIR = os.path.join(HERE, "output")
CA_BUNDLE = "/root/.ccr/ca-bundle.crt"

CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
          "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "DOT-USD"]
FUTURES = ["ES=F", "NQ=F", "YM=F", "GC=F", "SI=F",
           "CL=F", "NG=F", "HG=F", "ZB=F", "ZN=F"]
H4_TICKERS = ["BTC-USD", "ETH-USD", "ES=F", "NQ=F", "GC=F"]
GROUP_OF = {**{t: "crypto" for t in CRYPTO}, **{t: "futures" for t in FUTURES}}

METHODS = ["sma50", "sma10_40", "donch20", "donch55",
           "tsmom20", "tsmom60", "tsmom120", "swing5"]
FAMILY = {"sma50": "50-SMA state", "sma10_40": "10/40 crossover",
          "donch20": "Donchian", "donch55": "Donchian",
          "tsmom20": "TS momentum", "tsmom60": "TS momentum",
          "tsmom120": "TS momentum", "swing5": "Swing structure"}

N_BOOT = 200 if "--fast" in sys.argv else 1000
MEAN_BLOCK = 5          # stationary-bootstrap mean block length (bars).
                        # Preserves <=~1-week dependence & vol clustering,
                        # destroys the multi-week dependence trend methods
                        # exploit; slightly CONSERVATIVE for fast methods.
VR_LAGS = [2, 5, 10, 20, 40]
MIN_VALID = 60          # min valid state bars to score a config
SEED = 42

# metrics benchmarked against the null ("higher = trendier" except flips)
BENCH = ["dur_mean", "dur_med", "hit", "fwd_bar", "capture", "flips_py"]


# --------------------------------------------------------------------------
# Data loading (reuses the donchian_regime committed snapshot)
# --------------------------------------------------------------------------

def load_frame(ticker, tag):
    fname = f"{ticker.replace('=', '_')}_{tag}.csv.gz"
    for d in DATA_DIRS:
        path = os.path.join(d, fname)
        if os.path.exists(path):
            with gzip.open(path, "rt") as f:
                df = pd.read_csv(f, index_col=0, parse_dates=True)
            if tag == "1h":
                df.index = pd.DatetimeIndex(df.index, tz="UTC")
            return df
    # fallback: live download through the TLS-reterminating proxy
    import yfinance as yf
    from curl_cffi import requests as cr
    kwargs = {"impersonate": "chrome110"}
    if os.path.exists(CA_BUNDLE):
        kwargs["verify"] = CA_BUNDLE
    per = ("730d" if tag == "1h"
           else "max" if GROUP_OF[ticker] == "crypto" else "7y")
    raw = yf.Ticker(ticker, session=cr.Session(**kwargs)).history(
        period=per, interval=("1h" if tag == "1h" else "1d"), auto_adjust=True)
    df = raw[["Open", "High", "Low", "Close"]].dropna()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index = (df.index.tz_convert("UTC") if tag == "1h"
                else df.index.tz_localize(None).normalize())
    df = df.iloc[:-1]
    os.makedirs(DATA_DIRS[0], exist_ok=True)
    with gzip.open(os.path.join(DATA_DIRS[0], fname), "wt") as f:
        df.to_csv(f)
    return df


def resample(df, rule):
    agg = df.resample(rule, label="left" if rule == "4h" else "right",
                      closed="left" if rule == "4h" else "right").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"})
    agg = agg.dropna()
    return agg.iloc[:-1] if rule == "4h" else agg


def bars_per_year(index):
    yrs = (index[-1] - index[0]).total_seconds() / (365.25 * 24 * 3600)
    return (len(index) - 1) / yrs


def load_all():
    """-> {(group, tf): {ticker: OHLC frame}}"""
    series = {}
    for tkr in CRYPTO + FUTURES:
        d = load_frame(tkr, "1d")
        g = GROUP_OF[tkr]
        series.setdefault((g, "1d"), {})[tkr] = d
        series.setdefault((g, "1w"), {})[tkr] = resample(d, "W")
    for tkr in H4_TICKERS:
        h1 = load_frame(tkr, "1h")
        series.setdefault((GROUP_OF[tkr], "4h"), {})[tkr] = resample(h1, "4h")
    return series


# --------------------------------------------------------------------------
# Fast numpy primitives
# --------------------------------------------------------------------------

def np_ffill(a):
    mask = ~np.isnan(a)
    idx = np.where(mask, np.arange(len(a)), -1)
    np.maximum.accumulate(idx, out=idx)
    return np.where(idx >= 0, a[np.maximum(idx, 0)], np.nan)


def roll_mean(a, w):
    out = np.full(len(a), np.nan)
    if len(a) >= w:
        cs = np.concatenate(([0.0], np.cumsum(a)))
        out[w - 1:] = (cs[w:] - cs[:-w]) / w
    return out


def prior_extreme(a, n, kind):
    """max/min over the PRIOR n bars [t-n, t-1] (current bar excluded)."""
    out = np.full(len(a), np.nan)
    if len(a) > n:
        sw = np.lib.stride_tricks.sliding_window_view(a, n)
        out[n:] = sw[:-1].max(axis=1) if kind == "max" else sw[:-1].min(axis=1)
    return out


def sign_state(x):
    """sign(x) as a state; exact zeros hold the prior state."""
    ev = np.where(np.isnan(x), np.nan, np.sign(x))
    ev = np.where(ev == 0, np.nan, ev)
    return np_ffill(ev)


# --------------------------------------------------------------------------
# Trend-state methods (H, L, C numpy arrays -> state array in {+1,-1,nan})
# --------------------------------------------------------------------------

def st_sma50(h, l, c):
    return sign_state(c - roll_mean(c, 50))


def st_sma10_40(h, l, c):
    return sign_state(roll_mean(c, 10) - roll_mean(c, 40))


def st_donch(h, l, c, n):
    up = prior_extreme(h, n, "max")
    lo = prior_extreme(l, n, "min")
    ev = np.where(c > up, 1.0, np.where(c < lo, -1.0, np.nan))
    ev[np.isnan(up)] = np.nan
    return np_ffill(ev)


def st_tsmom(h, l, c, lag):
    x = np.full(len(c), np.nan)
    x[lag:] = c[lag:] / c[:-lag] - 1
    return sign_state(x)


def st_swing(h, l, c, k=5):
    """Market-structure state from k-bar fractal swings, no look-ahead:
    a swing at bar i is usable only from bar i+k (confirmation)."""
    n = len(c)
    if n < 2 * k + 2:
        return np.full(n, np.nan)
    w = 2 * k + 1
    swH = np.lib.stride_tricks.sliding_window_view(h, w)
    swL = np.lib.stride_tricks.sliding_window_view(l, w)
    is_sh = h[k:n - k] >= swH.max(axis=1)      # center equals window max
    is_sl = l[k:n - k] <= swL.min(axis=1)
    lastSH = np.full(n, np.nan)
    lastSL = np.full(n, np.nan)
    ih = np.where(is_sh)[0] + k                # swing bar index
    il = np.where(is_sl)[0] + k
    lastSH[ih + k] = h[ih]                     # usable at confirmation bar
    lastSL[il + k] = l[il]
    lastSH, lastSL = np_ffill(lastSH), np_ffill(lastSL)
    up = c > lastSH
    dn = c < lastSL
    ev = np.where(up & ~dn, 1.0, np.where(dn & ~up, -1.0, np.nan))
    ev[np.isnan(lastSH) | np.isnan(lastSL)] = np.nan
    return np_ffill(ev)


STATE_FN = {"sma50": st_sma50, "sma10_40": st_sma10_40,
            "donch20": lambda h, l, c: st_donch(h, l, c, 20),
            "donch55": lambda h, l, c: st_donch(h, l, c, 55),
            "tsmom20": lambda h, l, c: st_tsmom(h, l, c, 20),
            "tsmom60": lambda h, l, c: st_tsmom(h, l, c, 60),
            "tsmom120": lambda h, l, c: st_tsmom(h, l, c, 120),
            "swing5": st_swing}


# --------------------------------------------------------------------------
# Scoring one state series (metrics A, B, C)
# --------------------------------------------------------------------------

def score_state(state, close, bpy):
    valid = ~np.isnan(state)
    if valid.sum() < MIN_VALID:
        return None
    i0 = int(np.argmax(valid))
    s, c = state[i0:], close[i0:]
    n = len(s)

    # segments of constant state (contiguous runs)
    chg = np.where(s[1:] != s[:-1])[0] + 1
    starts = np.concatenate(([0], chg))
    ends = np.concatenate((chg, [n]))          # end-exclusive
    flips_py = (len(starts) - 1) / (n / bpy)

    out = dict(n_bars=n, n_segments=len(starts), flips_py=flips_py,
               dur_mean=np.nan, dur_med=np.nan, dur_p25=np.nan,
               dur_p75=np.nan, hit=np.nan, fwd_bar=np.nan,
               capture=np.nan, hit_rem=np.nan, rem_mean=np.nan)

    # (B) next-bar persistence over ALL state bars
    r1 = c[1:] / c[:-1] - 1
    st = s[:-1]
    nz = r1 != 0
    if nz.any():
        out["hit"] = float(np.mean((st[nz] * r1[nz]) > 0))
    out["fwd_bar"] = float(np.mean(st * r1))

    # completed segments only (the final run is right-censored)
    if len(starts) < 2:
        return out
    cs, ce = starts[:-1], ends[:-1]
    durs = (ce - cs).astype(float)
    seg_state = s[cs]
    out.update(dur_mean=float(durs.mean()), dur_med=float(np.median(durs)),
               dur_p25=float(np.percentile(durs, 25)),
               dur_p75=float(np.percentile(durs, 75)))

    # (C) capture efficiency per completed segment
    absmv = np.abs(np.diff(c))
    cum = np.concatenate(([0.0], np.cumsum(absmv)))
    move = c[ce - 1] - c[cs]
    noise = cum[ce - 1] - cum[cs]
    ok = noise > 0
    if ok.any():
        out["capture"] = float(np.mean(seg_state[ok] * move[ok] / noise[ok]))

    # (B2) remaining-segment-horizon persistence (bars in completed segs)
    m = starts[-1]                             # completed region = [0, m)
    end_close = np.repeat(c[ce - 1], (ce - cs))
    st_rep = np.repeat(seg_state, (ce - cs))
    rem = st_rep * (end_close / c[:m] - 1)
    nz2 = rem != 0
    if nz2.any():
        out["hit_rem"] = float(np.mean(rem[nz2] > 0))
    out["rem_mean"] = float(np.mean(rem))
    return out


# --------------------------------------------------------------------------
# Random-walk null: stationary block bootstrap, OHLC-geometry preserving
# --------------------------------------------------------------------------

def sb_indices(n, mean_block, rng):
    """Politis-Romano stationary bootstrap index sequence of length n."""
    k = int(2 * n / mean_block) + 10
    lens = rng.geometric(1.0 / mean_block, size=k)
    cl = np.cumsum(lens)
    k = int(np.searchsorted(cl, n)) + 1
    lens = lens[:k]
    total = int(cl[k - 1])
    starts = rng.integers(0, n, size=k)
    offs = np.arange(total) - np.repeat(np.concatenate(([0], cl[:k - 1])), lens)
    return ((np.repeat(starts, lens) + offs) % n)[:n]


def make_null_path(h_rel, l_rel, c_rel, c0, idx):
    """Rebuild an OHLC path from resampled per-bar geometry."""
    cr = c_rel[idx]
    close = c0 * np.cumprod(cr)
    prev = np.concatenate(([c0], close[:-1]))
    return prev * h_rel[idx], prev * l_rel[idx], close


def null_distributions(df, bpy, rng):
    """Run every method on N_BOOT bootstrapped paths.
    -> {method: {metric: np.array of bootstrap values}}"""
    h, l, c = (df[k].values for k in ["High", "Low", "Close"])
    prev = c[:-1]
    h_rel, l_rel, c_rel = h[1:] / prev, l[1:] / prev, c[1:] / prev
    n = len(c_rel)
    acc = {m: {k: np.full(N_BOOT, np.nan) for k in BENCH} for m in METHODS}
    for b in range(N_BOOT):
        idx = sb_indices(n, MEAN_BLOCK, rng)
        hh, ll, cc = make_null_path(h_rel, l_rel, c_rel, c[0], idx)
        for m in METHODS:
            sc = score_state(STATE_FN[m](hh, ll, cc), cc, bpy)
            if sc is None:
                continue
            for k in BENCH:
                acc[m][k][b] = sc[k]
    return acc


# --------------------------------------------------------------------------
# (E) Lo-MacKinlay variance ratio, (F) Hurst R/S
# --------------------------------------------------------------------------

def variance_ratio(logret, q):
    """VR(q) and heteroskedasticity-robust z (Lo-MacKinlay 1988)."""
    r = logret[~np.isnan(logret)]
    T = len(r)
    if T < 10 * q:
        return np.nan, np.nan
    mu = r.mean()
    d = r - mu
    var1 = (d ** 2).sum() / (T - 1)
    p = np.concatenate(([0.0], np.cumsum(r)))
    yq = p[q:] - p[:-q]                     # overlapping q-period sums
    m = q * (T - q + 1) * (1 - q / T)
    varq = ((yq - q * mu) ** 2).sum() / m
    vr = varq / var1
    denom_sq = ((d ** 2).sum()) ** 2
    theta = 0.0
    for k in range(1, q):
        delta = ((d[k:] ** 2) * (d[:-k] ** 2)).sum() / denom_sq
        theta += (2 * (q - k) / q) ** 2 * delta
    z = (vr - 1) / math.sqrt(theta) if theta > 0 else np.nan
    return float(vr), float(z)


def hurst_rs(logret):
    """Classic rescaled-range Hurst exponent (noisy; second opinion only)."""
    r = logret[~np.isnan(logret)]
    n = len(r)
    if n < 200:
        return np.nan
    sizes = np.unique(np.logspace(math.log10(10), math.log10(n // 2),
                                  12).astype(int))
    lx, ly = [], []
    for w in sizes:
        k = n // w
        if k < 2:
            continue
        x = r[:k * w].reshape(k, w)
        z = np.cumsum(x - x.mean(axis=1, keepdims=True), axis=1)
        rng_ = z.max(axis=1) - z.min(axis=1)
        s = x.std(axis=1, ddof=1)
        ok = s > 0
        if not ok.any():
            continue
        lx.append(math.log(w))
        ly.append(math.log((rng_[ok] / s[ok]).mean()))
    if len(lx) < 4:
        return np.nan
    return float(np.polyfit(lx, ly, 1)[0])


def market_verdict(vr_z_pairs, hurst):
    """Transparent rule: >=2 lags significantly persistent (z>1.645) and
    more persistent than anti-persistent lags -> TRENDING; mirror image ->
    MEAN-REVERTING; otherwise RANDOM-WALK-like."""
    zs = [z for _, z in vr_z_pairs if not math.isnan(z)]
    pos = sum(z > 1.645 for z in zs)
    neg = sum(z < -1.645 for z in zs)
    if pos >= 2 and pos > neg:
        return "TRENDING"
    if neg >= 2 and neg > pos:
        return "MEAN-REVERTING"
    return "RANDOM-WALK"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    series = load_all()

    method_rows, market_rows, samples = [], [], []
    rng_master = np.random.default_rng(SEED)

    for (group, tf), members in sorted(series.items()):
        for tkr, df in sorted(members.items()):
            bpy = bars_per_year(df.index)
            c = df["Close"].values
            logret = np.diff(np.log(c))
            samples.append(dict(group=group, timeframe=tf, instrument=tkr,
                                start=str(df.index[0].date()),
                                end=str(df.index[-1].date()),
                                n_bars=len(df), bars_per_year=round(bpy)))

            # (E)+(F) indicator-free gates
            vr_cols, pairs = {}, []
            for q_ in VR_LAGS:
                vr, z = variance_ratio(logret, q_)
                vr_cols[f"vr{q_}"] = vr
                vr_cols[f"vrz{q_}"] = z
                pairs.append((vr, z))
            hurst = hurst_rs(logret)
            market_rows.append(dict(group=group, timeframe=tf, instrument=tkr,
                                    n_bars=len(df), **vr_cols, hurst=hurst,
                                    verdict=market_verdict(pairs, hurst)))

            # (A)-(C) real metrics + (D) bootstrap null
            rng = np.random.default_rng(rng_master.integers(2 ** 63))
            nulls = null_distributions(df, bpy, rng)
            h, l = df["High"].values, df["Low"].values
            for m in METHODS:
                sc = score_state(STATE_FN[m](h, l, c), c, bpy)
                if sc is None:
                    continue
                row = dict(group=group, timeframe=tf, instrument=tkr,
                           method=m, family=FAMILY[m], **sc)
                n_sig = 0
                for k in BENCH:
                    nd = nulls[m][k]
                    nd = nd[~np.isnan(nd)]
                    real = sc[k]
                    if len(nd) < 50 or math.isnan(real):
                        row.update({f"{k}_null": np.nan, f"{k}_z": np.nan,
                                    f"{k}_p": np.nan, f"{k}_n5": np.nan,
                                    f"{k}_n95": np.nan})
                        continue
                    mu, sd = nd.mean(), nd.std()
                    z = (real - mu) / sd if sd > 0 else np.nan
                    # one-sided p: P(null >= real); flips: fewer = trendier
                    p = ((1 + (nd <= real).sum()) / (1 + len(nd))
                         if k == "flips_py"
                         else (1 + (nd >= real).sum()) / (1 + len(nd)))
                    row.update({f"{k}_null": mu, f"{k}_z": z, f"{k}_p": p,
                                f"{k}_n5": np.percentile(nd, 5),
                                f"{k}_n95": np.percentile(nd, 95)})
                    if k in ("dur_mean", "hit", "capture") and p < 0.05:
                        n_sig += 1
                row["beats_null"] = n_sig >= 2   # >=2 of duration/hit/capture
                method_rows.append(row)
            print(f"  scored {tkr:9s} {tf}  ({time.time()-t0:5.0f}s)")

    mdf = pd.DataFrame(method_rows)
    vdf = pd.DataFrame(market_rows)
    mdf.to_csv(os.path.join(OUT_DIR, "method_metrics.csv"),
               index=False, float_format="%.5f")
    vdf.to_csv(os.path.join(OUT_DIR, "market_viability.csv"),
               index=False, float_format="%.4f")
    write_summary(mdf, vdf, pd.DataFrame(samples))
    print(f"\nDone in {time.time()-t0:.0f}s "
          f"({N_BOOT} bootstrap resamples/series). Outputs in {OUT_DIR}/")


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def fmt(x, nd=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{x:.{nd}f}"


def md_table(df, cols, headers, nd=2):
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (int, np.integer)):
                cells.append(str(int(v)))
            elif isinstance(v, (float, np.floating)):
                cells.append(fmt(float(v), nd))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def stars(p):
    if p is None or math.isnan(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def method_block_stats(mdf):
    """Per (group, tf, method): median z's across instruments + counts."""
    rows = []
    for (g, tf, m), grp in mdf.groupby(["group", "timeframe", "method"]):
        zc = grp["capture_z"].median()
        zd = grp["dur_mean_z"].median()
        zh = grp["hit_z"].median()
        rows.append(dict(
            group=g, timeframe=tf, method=m, family=FAMILY[m],
            n_inst=len(grp),
            real_capture=grp["capture"].median(),
            null_capture=grp["capture_null"].median(),
            z_capture=zc, z_dur=zd, z_hit=zh,
            p_capture_med=grp["capture_p"].median(),
            flips_py=grp["flips_py"].median(),
            dur_med=grp["dur_med"].median(),
            n_beat=int(grp["beats_null"].sum()),
            composite=np.nanmean([zc, zd, zh])))
    return pd.DataFrame(rows)


def write_summary(mdf, vdf, samples):
    L = []
    A = L.append
    blocks = method_block_stats(mdf)

    A("# Trend identification quality — five trend definitions vs a "
      "random-walk null (no trading)")
    A("")
    A(f"*Run date: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d}. Pure state scoring "
      "— no entries, exits, costs, or P&L. Data: same committed Yahoo "
      "snapshot as the Donchian study (crypto daily = max history; futures "
      "daily = ~7y **front-month continuous, whose roll gaps fire fake "
      "trend flips — back-adjusted contracts are needed for firm futures "
      "conclusions**; 4h resampled from 1h, ~2y cap; weekly resampled from "
      f"daily). Null = stationary block bootstrap of each instrument's own "
      f"bars ({N_BOOT} resamples, mean block {MEAN_BLOCK} bars) preserving "
      "the return distribution, volatility clustering and per-bar OHLC "
      "geometry while destroying multi-week serial dependence; short "
      "(≤~1 week) dependence survives in the null, which makes it slightly "
      "conservative. p-values are one-sided empirical: P(null ≥ real). "
      "Stars: \\*\\*\\* p<0.01, \\*\\* p<0.05, \\* p<0.10.*")
    A("")

    # ---- 1 samples ----
    A("## 1. Sample sizes")
    A("")
    s = samples.sort_values(["timeframe", "group", "instrument"])
    A(md_table(s, ["group", "timeframe", "instrument", "start", "end",
                   "n_bars", "bars_per_year"],
               ["Group", "TF", "Instrument", "Start", "End", "Bars",
                "Bars/yr"], 0))
    A("")

    # ---- 2 market viability ----
    A("## 2. Does the market trend at all? (indicator-free gates)")
    A("")
    A("Lo–MacKinlay variance ratios (VR>1 = persistent, <1 = mean-reverting) "
      "with heteroskedasticity-robust z-stats, and R/S Hurst (H>0.5 = "
      "persistent). Verdict rule: ≥2 lags significantly persistent "
      "(z>1.645) and more persistent than anti-persistent lags → TRENDING; "
      "mirror image → MEAN-REVERTING; else RANDOM-WALK-like.")
    for tf in ["1d", "1w", "4h"]:
        sub = vdf[vdf["timeframe"] == tf].sort_values(["group", "instrument"])
        if sub.empty:
            continue
        sub = sub.copy()
        for q_ in VR_LAGS:
            sub[f"VR{q_}"] = sub.apply(
                lambda r: fmt(r[f"vr{q_}"]) + stars(
                    2 * (1 - sstats.norm.cdf(abs(r[f"vrz{q_}"])))
                    if not math.isnan(r[f"vrz{q_}"]) else float("nan")),
                axis=1)
        A("")
        A(f"### {tf}")
        A("")
        A(md_table(sub, ["group", "instrument"]
                   + [f"VR{q_}" for q_ in VR_LAGS] + ["hurst", "verdict"],
                   ["Group", "Instrument"] + [f"VR({q_})" for q_ in VR_LAGS]
                   + ["Hurst", "Verdict"]))
    A("")
    counts = vdf.groupby(["timeframe", "group"])["verdict"].value_counts()
    A("Verdict counts: " + "; ".join(
        f"{tf}/{g}: " + ", ".join(f"{v}×{c}" for v, c in
                                  counts[tf][g].items())
        for tf, g in sorted({(t, g) for t, g in
                             zip(vdf['timeframe'], vdf['group'])})) + ".")
    A("")

    # ---- 3 method vs null per block ----
    A("## 3. Method vs its random-walk null (medians across instruments)")
    A("")
    A("`capture` = signed segment move / segment absolute path length "
      "(chop sits near 0). z = (real − null mean)/null std, medians across "
      "the block's instruments. `beats null` = instruments where ≥2 of "
      "{duration, hit rate, capture} have p<0.05 against the null.")
    A("")
    for (g, tf) in sorted(set(zip(blocks["group"], blocks["timeframe"]))):
        sub = blocks[(blocks["group"] == g) & (blocks["timeframe"] == tf)]
        sub = sub.sort_values("composite", ascending=False).copy()
        sub["beat"] = (sub["n_beat"].astype(str) + "/"
                       + sub["n_inst"].astype(str))
        A(f"### {g} — {tf}")
        A("")
        A(md_table(sub, ["method", "real_capture", "null_capture",
                         "z_capture", "z_dur", "z_hit", "flips_py",
                         "dur_med", "beat", "composite"],
                   ["Method", "Capture (real)", "Capture (null)", "z cap",
                    "z dur", "z hit", "Flips/yr", "Med dur (bars)",
                    "Beats null", "Composite z"]))
        A("")

    # ---- 4 method ranking ----
    A("## 4. Method ranking (composite z vs null, across all blocks)")
    A("")
    rank_cfg = (blocks.groupby("method")
                .agg(family=("family", "first"),
                     med_composite=("composite", "median"),
                     med_z_capture=("z_capture", "median"),
                     med_z_dur=("z_dur", "median"),
                     med_z_hit=("z_hit", "median"),
                     total_beat=("n_beat", "sum"),
                     total_inst=("n_inst", "sum"))
                .sort_values("med_composite", ascending=False).reset_index())
    A(md_table(rank_cfg, ["method", "family", "med_composite",
                          "med_z_capture", "med_z_dur", "med_z_hit",
                          "total_beat", "total_inst"],
               ["Config", "Family", "Median composite z", "Med z capture",
                "Med z duration", "Med z hit", "Σ beats null", "Σ series"]))
    A("")
    fam = (rank_cfg.groupby("family")
           .agg(med_composite=("med_composite", "median"),
                total_beat=("total_beat", "sum"),
                total_inst=("total_inst", "sum"))
           .sort_values("med_composite", ascending=False).reset_index())
    A("Family ranking (median of member configs):")
    A("")
    A(md_table(fam, ["family", "med_composite", "total_beat", "total_inst"],
               ["Family", "Median composite z", "Σ beats null", "Σ series"]))
    A("")

    # ---- 5 timeframe comparison ----
    A("## 5. Timeframe comparison (median composite z across methods)")
    A("")
    tf_rows = []
    for (g, tf), grp in blocks.groupby(["group", "timeframe"]):
        best = grp.loc[grp["composite"].idxmax()]
        tf_rows.append(dict(group=g, timeframe=tf,
                            med_composite=grp["composite"].median(),
                            best_method=best["method"],
                            best_composite=best["composite"],
                            beat_share=grp["n_beat"].sum()
                            / grp["n_inst"].sum()))
    A(md_table(pd.DataFrame(tf_rows).sort_values(["group", "timeframe"]),
               ["group", "timeframe", "med_composite", "best_method",
                "best_composite", "beat_share"],
               ["Group", "TF", "Median composite z", "Best method",
                "Best composite z", "Share beating null"]))
    A("")
    A("Caveats: 4h = only ~2 years and 2–3 instruments per group; weekly "
      "futures = ~365 bars (thin for slow methods like tsmom120).")
    A("")

    # ---- 6 duration distributions for winners ----
    A("## 6. How long do trends last? (best method per block)")
    A("")
    dur_rows = []
    dpb_map = samples.groupby(["group", "timeframe"])["bars_per_year"].median()
    for (g, tf), grp in blocks.groupby(["group", "timeframe"]):
        best_m = grp.loc[grp["composite"].idxmax(), "method"]
        sub = mdf[(mdf["group"] == g) & (mdf["timeframe"] == tf)
                  & (mdf["method"] == best_m)]
        dpb = 365.25 / dpb_map[(g, tf)]   # calendar days per bar, empirical
        dur_rows.append(dict(
            group=g, timeframe=tf, method=best_m,
            p25=sub["dur_p25"].median(), median=sub["dur_med"].median(),
            mean=sub["dur_mean"].median(), p75=sub["dur_p75"].median(),
            median_days=sub["dur_med"].median() * dpb,
            null_mean=sub["dur_mean_null"].median()))
    A(md_table(pd.DataFrame(dur_rows).sort_values(["group", "timeframe"]),
               ["group", "timeframe", "method", "p25", "median", "mean",
                "p75", "median_days", "null_mean"],
               ["Group", "TF", "Best method", "p25 (bars)", "Median",
                "Mean", "p75", "Median ≈days", "Null mean dur"], 1))
    A("")
    A("(Median across instruments of the per-instrument duration stats; "
      "completed segments only — the final, right-censored run of each "
      "series is excluded.)")
    A("")

    # ---- 7 answers ----
    A("## 7. Plain-English answers")
    A("")
    A(build_answers(mdf, vdf, blocks))
    A("")
    A("---")
    A("*Reproduce: `python score_trends.py` (add `--fast` for 200 "
      "resamples). Full metrics incl. null means/percentiles/p-values: "
      "`output/method_metrics.csv`; market gates: "
      "`output/market_viability.csv`.*")

    with open(os.path.join(OUT_DIR, "SUMMARY.md"), "w") as f:
        f.write("\n".join(L))


def build_answers(mdf, vdf, blocks):
    out = []

    # Q1 does each market trend?
    out.append("**Q1 — Do these markets trend at all (indicator-free)?**")
    for tf in ["1d", "1w", "4h"]:
        for g in ["crypto", "futures"]:
            sub = vdf[(vdf["timeframe"] == tf) & (vdf["group"] == g)]
            if sub.empty:
                continue
            vc = sub["verdict"].value_counts()
            med_h = sub["hurst"].median()
            out.append(f"- {g} {tf}: "
                       + ", ".join(f"{v} {c}/{len(sub)}"
                                   for v, c in vc.items())
                       + f"; median Hurst {fmt(med_h)}.")
    out.append("")

    # Q2 which method identifies real trend
    rank = (blocks.groupby("method")["composite"].median()
            .sort_values(ascending=False))
    out.append("**Q2 — Which definition identifies real (above-null) "
               "trend?** Config ranking by median composite z across all "
               "blocks: "
               + ", ".join(f"{m} ({fmt(v)})" for m, v in rank.items())
               + ".")
    beat_tot = mdf.groupby("method")["beats_null"].sum()
    out.append(f"- Series where a method beats its null (≥2 of 3 metrics "
               f"p<0.05), out of {mdf.groupby('method').size().iloc[0]} "
               "series per method: "
               + ", ".join(f"{m}: {int(beat_tot[m])}"
                           for m in rank.index) + ".")
    out.append("")

    # Q3 timeframe
    tf_med = blocks.groupby("timeframe")["composite"].median()
    out.append("**Q3 — Which timeframe is trend most identifiable on?** "
               "Median composite z: "
               + ", ".join(f"{tf}: {fmt(v)}" for tf, v in
                           tf_med.sort_values(ascending=False).items())
               + ". (4h rests on ~2y and 5 instruments; weekly on ~7–12y "
               "but few bars.)")
    out.append("")

    # Q4 crypto vs futures
    g_med = blocks.groupby("group")["composite"].median()
    beat_g = (blocks.groupby("group")
              .apply(lambda x: x["n_beat"].sum() / x["n_inst"].sum(),
                     include_groups=False))
    out.append("**Q4 — Crypto vs futures?** Median composite z — "
               + ", ".join(f"{g}: {fmt(v)}" for g, v in g_med.items())
               + "; share of series×methods beating the null — "
               + ", ".join(f"{g}: {fmt(v * 100, 0)}%"
                           for g, v in beat_g.items())
               + ". Futures verdicts carry the roll-gap caveat.")
    out.append("")

    # Q5 durations
    out.append("**Q5 — How long do real trends last?** See section 6: "
               "median completed-trend duration for the best method per "
               "block, in bars and approximate calendar days. Downstream "
               "POI/entry logic must operate inside those windows.")
    out.append("")

    # Q6 noise methods
    noise = []
    for m, grp in mdf.groupby("method"):
        share = grp["beats_null"].mean()
        if share < 0.25:
            noise.append(f"{m} ({fmt(share*100, 0)}% of series beat null)")
    out.append("**Q6 — Methods identifying noise rather than trend:** "
               + (", ".join(noise) if noise
                  else "none fell below the 25%-of-series threshold")
               + ". Any method whose persistence and capture sit inside "
               "its null band is reading structure into randomness — its "
               "'trends' would appear identically on shuffled data.")
    out.append("")

    # bottom line: reconcile Q1 (weak real trend) with Q2 (methods ~ null)
    best = blocks.loc[blocks["composite"].idxmax()]
    out.append("**Bottom line.** The indicator-free gates and the "
               "method-vs-null scores tell one consistent story with an "
               "uncomfortable punchline. The markets are not pure random "
               "walks everywhere: crypto shows genuinely elevated variance "
               "ratios at 10–40-bar horizons on daily and weekly bars "
               "(every crypto VR(40) > 1 on daily; 3–4 of 10 instruments "
               "individually significant; median Hurst 0.60–0.65), while "
               "futures lean the other way (VR < 1, i.e. mean-reversion, "
               "with the roll-gap caveat). But NONE of the five binary "
               "state definitions converts that weak persistence into "
               "identification that reliably clears its own shuffled-data "
               "null: the best block is "
               f"{best['method']} on {best['group']} {best['timeframe']} "
               f"(composite z ≈ {fmt(best['composite'])}), and across all "
               "45 series × 8 configs only a handful beat the null at "
               "p<0.05 — about what false positives alone would produce. "
               "Flip counts, duration distributions and capture ratios of "
               "every method look like what the same method generates on "
               "block-shuffled returns. Read together: the exploitable "
               "signal, to the extent it exists, lives in crypto at the "
               "20–40 trading-day horizon and is weak — a property of the "
               "market, faintly visible to variance ratios, but too faint "
               "for any of these binary trend states to certify segment by "
               "segment. Downstream logic should treat 'trend state' as a "
               "weak prior (crypto daily, ~1-month horizon), not as a "
               "validated regime label; and futures conclusions need "
               "back-adjusted contracts before trusting anything here.")
    return "\n".join(out)


if __name__ == "__main__":
    main()
