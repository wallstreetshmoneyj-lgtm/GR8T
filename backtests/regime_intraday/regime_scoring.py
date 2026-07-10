#!/usr/bin/env python3
"""
Intraday regime assessment — BULL / BEAR / CHOP vs a random-walk null.

Concurrent (descriptive) three-state regime classification on 1h and 4h
bars for 10 crypto pairs and 10 futures. NO trading, NO prediction claims:
we score whether the three labeled buckets exhibit genuinely different
statistical behavior, and whether that separation EXCEEDS what the same
classifier produces on block-shuffled returns. If not, the labels are
cosmetic.

Classifiers (each labels every bar +1 BULL / -1 BEAR / 0 CHOP):
  ADX : ADX(14, Wilder) < 20 -> CHOP; else BULL if +DI > -DI else BEAR
  ER  : Kaufman efficiency ratio, 20-bar window; ER < 0.30 -> CHOP;
        else BULL/BEAR by sign of the 20-bar net change
  HMM : 3-state Gaussian HMM on (log return, 20-bar rolling vol),
        fit ONCE on the oldest 70% (in-sample) of the REAL series,
        states mapped by in-sample mean return (max -> BULL, min -> BEAR,
        middle -> CHOP), decoded over the full series.
        NOTE (printed in report): decoding is Viterbi, i.e. smoothing —
        the label at bar t uses the whole sequence. The null is decoded
        with the SAME frozen model + scaler, so the real-vs-null
        comparison stays like-for-like ("fixed classifier, new data" —
        the same standard ADX/ER get).

Scoring per classifier x instrument x timeframe, per regime bucket
(windows: FULL, IS = oldest 70%, OOS = newest 30%):
  (A) forward drift  : mean next-bar return of bars labeled X
  (B) forward persistence : lag-1 autocorrelation of next-bar returns over
      consecutive same-regime bar pairs (both bars labeled X)
  (C) realized vol of next-bar returns per regime, and per-segment
      efficiency |net move| / sum|bar moves| over contiguous same-label
      runs (>= 5 bars)
  (D) separation : S1 = drift(BULL) - drift(BEAR); Kruskal-Wallis H across
      the three buckets' forward returns; CHOP validity diffs
      d_eff = eff(trend) - eff(chop), d_ac1 = ac1(trend) - ac1(chop)

THE NULL: stationary block bootstrap of each instrument's own bars
(mean block 10, B = 1000, seeded), preserving the return distribution and
per-bar OHLC geometry while destroying longer serial structure. Each
classifier runs identically on every shuffled path; S1 / KW-H / d_eff /
d_ac1 are compared real-vs-null with one-sided empirical p-values
(P(null >= real)), for FULL and OOS windows.

PRE-REGISTERED PASS CRITERION (fixed before results): a classifier
"passes" if >= 25% of its instrument x timeframe configs have S1
exceeding the null 95th percentile (p < 0.05) on the FULL window.
If ALL THREE classifiers fail, the pre-registered market-structure
fallback runs under the identical test:
  swing points = k=3 fractals; BULL = higher swing highs AND higher
  swing lows; BEAR = lower highs AND lower lows; CHOP = mixed structure,
  a close-based break of the supporting swing, or no new swing confirmed
  within 20 bars. Close-based break confirmation only (no intrabar wicks).

Data: 1h max history (~730d Yahoo cap; futures get ~876 calendar days via
period="730d"); 4h RESAMPLED from 1h anchored to UTC midnight (native 4h
not used, for cross-group consistency — same convention as the prior
studies). Futures are FRONT-MONTH CONTINUOUS with roll gaps that
contaminate both real and null regime states; back-adjusted contracts are
needed for firm futures conclusions.

Run:  python regime_scoring.py           (B=1000)
      python regime_scoring.py --fast    (B=150 smoke test)
Outputs (./output): SUMMARY.md, regime_metrics.csv
"""

import gzip
import math
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd
from scipy import stats as sstats
from scipy.signal import lfilter

warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------
# Config
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
GROUP_OF = {**{t: "crypto" for t in CRYPTO}, **{t: "futures" for t in FUTURES}}

N_BOOT = 150 if "--fast" in sys.argv else 1000
MEAN_BLOCK = 10                 # per spec: block length ~10 bars
IS_FRACTION = 0.70
MIN_BARS = 1500
MIN_BUCKET = 30                 # min bars in a regime bucket to score it
SEED = 42

ADX_LEN, ADX_TH = 14, 20.0
ER_LEN, ER_TH = 20, 0.30
HMM_STATES, HMM_VOL_WIN = 3, 20
SWING_K, SWING_STALE = 3, 20    # pre-registered fallback parameters

CLASSIFIERS = ["ADX", "ER", "HMM"]
BENCH_STATS = ["s1", "kw_h", "d_eff", "d_ac1"]
PASS_SHARE = 0.25               # pre-registered pass criterion (see docstring)


# --------------------------------------------------------------------------
# Data (reuses prior studies' committed 1h snapshots where present)
# --------------------------------------------------------------------------

def load_1h(ticker):
    fname = f"{ticker.replace('=', '_')}_1h.csv.gz"
    for d in DATA_DIRS:
        path = os.path.join(d, fname)
        if os.path.exists(path):
            with gzip.open(path, "rt") as f:
                df = pd.read_csv(f, index_col=0, parse_dates=True)
            df.index = pd.DatetimeIndex(df.index, tz="UTC")
            return df
    import yfinance as yf
    from curl_cffi import requests as cr
    kwargs = {"impersonate": "chrome110"}
    if os.path.exists(CA_BUNDLE):
        kwargs["verify"] = CA_BUNDLE
    last_err = None
    for attempt in range(4):
        try:
            raw = yf.Ticker(ticker, session=cr.Session(**kwargs)).history(
                period="730d", interval="1h", auto_adjust=True)
            if raw is not None and len(raw) > 0:
                break
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(2 * (attempt + 1))
    else:
        print(f"  !! {ticker}: download failed ({last_err})")
        return None
    df = raw[["Open", "High", "Low", "Close"]].dropna()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index = df.index.tz_convert("UTC")
    df = df.iloc[:-1]
    os.makedirs(DATA_DIRS[0], exist_ok=True)
    with gzip.open(os.path.join(DATA_DIRS[0], fname), "wt") as f:
        df.to_csv(f)
    time.sleep(1.5)
    return df


def resample_4h(df):
    agg = df.resample("4h", label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"})
    return agg.dropna().iloc[:-1]


def bars_per_year(index):
    yrs = (index[-1] - index[0]).total_seconds() / (365.25 * 24 * 3600)
    return (len(index) - 1) / yrs


# --------------------------------------------------------------------------
# Classifiers (numpy in / labels out; labels in {+1,-1,0}, NaN = warmup)
# --------------------------------------------------------------------------

def wilder(x, n):
    """Wilder smoothing = EWMA(alpha=1/n), NaN-safe leading segment."""
    alpha = 1.0 / n
    first = np.argmax(~np.isnan(x))
    y = np.full(len(x), np.nan)
    seg = x[first:]
    y[first:] = lfilter([alpha], [1, -(1 - alpha)], seg,
                        zi=[(1 - alpha) * seg[0]])[0]
    return y


def cls_adx(h, l, c):
    up = np.diff(h, prepend=h[0])
    dn = -np.diff(l, prepend=l[0])
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = wilder(tr, ADX_LEN)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100 * wilder(pdm, ADX_LEN) / atr
        ndi = 100 * wilder(ndm, ADX_LEN) / atr
        dx = 100 * np.abs(pdi - ndi) / (pdi + ndi)
    adx = wilder(dx, ADX_LEN)
    lab = np.where(adx < ADX_TH, 0.0,
                   np.where(pdi > ndi, 1.0, np.where(pdi < ndi, -1.0, 0.0)))
    lab[:3 * ADX_LEN] = np.nan          # warmup
    lab[np.isnan(adx)] = np.nan
    return lab


def cls_er(h, l, c):
    n = len(c)
    lab = np.full(n, np.nan)
    if n <= ER_LEN:
        return lab
    net = c[ER_LEN:] - c[:-ER_LEN]
    absmv = np.abs(np.diff(c))
    cum = np.concatenate(([0.0], np.cumsum(absmv)))
    denom = cum[ER_LEN:] - cum[:-ER_LEN]
    with np.errstate(divide="ignore", invalid="ignore"):
        er = np.abs(net) / denom
    out = np.where(er < ER_TH, 0.0, np.sign(net))
    out[denom <= 0] = 0.0
    lab[ER_LEN:] = out
    return lab


class HMMClassifier:
    """Fit once on real IS; frozen model+scaler label real and null series."""

    def __init__(self, c, is_end):
        from hmmlearn.hmm import GaussianHMM
        r, vol = self._features_raw(c)
        sl = slice(HMM_VOL_WIN, is_end)
        self.mu = np.array([np.nanmean(r[sl]), np.nanmean(vol[sl])])
        self.sd = np.array([np.nanstd(r[sl]), np.nanstd(vol[sl])])
        self.sd[self.sd == 0] = 1.0
        X = self._design(r, vol)
        self.model = GaussianHMM(n_components=HMM_STATES,
                                 covariance_type="diag", n_iter=50,
                                 tol=1e-3, random_state=SEED)
        self.model.fit(X[HMM_VOL_WIN:is_end])
        order = np.argsort(self.model.means_[:, 0])   # by IS mean return
        self.state_lab = np.empty(HMM_STATES)
        self.state_lab[order[0]] = -1.0               # most negative -> BEAR
        self.state_lab[order[-1]] = 1.0               # most positive -> BULL
        self.state_lab[order[1]] = 0.0                # middle -> CHOP

    @staticmethod
    def _features_raw(c):
        r = np.concatenate(([np.nan], np.diff(np.log(c))))
        vol = pd.Series(r).rolling(HMM_VOL_WIN).std().values
        return r, vol

    def _design(self, r, vol):
        X = np.column_stack([r, vol])
        X = (X - self.mu) / self.sd
        return np.nan_to_num(X, nan=0.0)

    def label(self, c):
        r, vol = self._features_raw(c)
        states = self.model.predict(self._design(r, vol))
        lab = self.state_lab[states]
        lab[:HMM_VOL_WIN] = np.nan
        return lab


def cls_swing(h, l, c):
    """PRE-REGISTERED FALLBACK. k=3 fractal swings (confirmed k bars
    later, no look-ahead); BULL = HH+HL, BEAR = LH+LL, CHOP = mixed /
    close-based break of the supporting swing / no swing confirmed in
    the last SWING_STALE bars."""
    n = len(c)
    k, w = SWING_K, 2 * SWING_K + 1
    lab = np.full(n, np.nan)
    if n < w + 2:
        return lab
    swH = np.lib.stride_tricks.sliding_window_view(h, w)
    swL = np.lib.stride_tricks.sliding_window_view(l, w)
    is_sh = h[k:n - k] >= swH.max(axis=1)
    is_sl = l[k:n - k] <= swL.min(axis=1)
    # confirmation bar for a swing at i is i+k
    conf_h = np.full(n, False); conf_l = np.full(n, False)
    ih = np.where(is_sh)[0] + k
    il = np.where(is_sl)[0] + k
    conf_h[ih + k] = True; conf_l[il + k] = True
    val_h = np.full(n, np.nan); val_l = np.full(n, np.nan)
    val_h[ih + k] = h[ih]; val_l[il + k] = l[il]

    sh_prev = sh_last = np.nan     # last two confirmed swing highs
    sl_prev = sl_last = np.nan
    last_conf = -10**9
    broke_dn = broke_up = False
    for t in range(n):
        if conf_h[t]:
            sh_prev, sh_last = sh_last, val_h[t]
            last_conf = t
            broke_up = False       # new structure supersedes old break
        if conf_l[t]:
            sl_prev, sl_last = sl_last, val_l[t]
            last_conf = t
            broke_dn = False
        if np.isnan(sh_prev) or np.isnan(sl_prev):
            continue               # need two of each to define structure
        # close-based break of the supporting swing
        if c[t] < sl_last:
            broke_dn = True
        if c[t] > sh_last:
            broke_up = True
        hh, hl = sh_last > sh_prev, sl_last > sl_prev
        lh, ll = sh_last < sh_prev, sl_last < sl_prev
        if t - last_conf > SWING_STALE:
            lab[t] = 0.0
        elif hh and hl and not broke_dn:
            lab[t] = 1.0
        elif lh and ll and not broke_up:
            lab[t] = -1.0
        else:
            lab[t] = 0.0
    return lab


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

def kw_h_stat(groups):
    """Kruskal-Wallis H (no tie correction; returns are effectively
    continuous). Empirical null supplies significance, not chi2."""
    allv = np.concatenate(groups)
    N = len(allv)
    if N < 3 * MIN_BUCKET:
        return np.nan
    ranks = np.empty(N)
    order = np.argsort(allv, kind="mergesort")
    ranks[order] = np.arange(1, N + 1)
    H, pos = 0.0, 0
    for g in groups:
        ng = len(g)
        rbar = ranks[pos:pos + ng].mean()
        H += ng * (rbar - (N + 1) / 2) ** 2
        pos += ng
    return 12.0 / (N * (N + 1)) * H


def score_window(lab, c, bpy, sl):
    """A-D metrics for one window (slice sl of the series)."""
    lab_w = lab[sl]
    c_w = c[sl]
    n = len(c_w)
    out = {}
    if n < 200:
        return None
    fr = np.concatenate((c_w[1:] / c_w[:-1] - 1, [np.nan]))  # fwd ret at t
    valid = ~np.isnan(lab_w) & ~np.isnan(fr)
    groups = {}
    for name, v in [("bull", 1.0), ("bear", -1.0), ("chop", 0.0)]:
        m = valid & (lab_w == v)
        g = fr[m]
        groups[name] = g
        out[f"share_{name}"] = float(m.sum()) / max(valid.sum(), 1)
        if len(g) >= MIN_BUCKET:
            out[f"drift_{name}"] = float(g.mean())            # per bar
            out[f"vol_{name}"] = float(g.std() * math.sqrt(bpy))
        else:
            out[f"drift_{name}"] = np.nan
            out[f"vol_{name}"] = np.nan
        # lag-1 autocorr over consecutive same-regime pairs
        m2 = m[:-1] & (lab_w[1:] == v) & ~np.isnan(fr[1:])
        x, y = fr[:-1][m2], fr[1:][m2]
        out[f"ac1_{name}"] = (float(np.corrcoef(x, y)[0, 1])
                              if len(x) >= MIN_BUCKET else np.nan)
        # per-segment efficiency over contiguous same-label runs >= 5 bars
        effs = []
        mm = (lab_w == v) & ~np.isnan(lab_w)
        d = np.diff(mm.astype(int))
        starts = np.where(d == 1)[0] + 1
        ends = np.where(d == -1)[0] + 1
        if mm[0]:
            starts = np.concatenate(([0], starts))
        if mm[-1]:
            ends = np.concatenate((ends, [n]))
        for s0, e0 in zip(starts, ends):
            if e0 - s0 >= 5:
                noise = np.abs(np.diff(c_w[s0:e0])).sum()
                if noise > 0:
                    effs.append(abs(c_w[e0 - 1] - c_w[s0]) / noise)
        out[f"eff_{name}"] = float(np.mean(effs)) if effs else np.nan

    out["s1"] = out["drift_bull"] - out["drift_bear"]
    gb, gr, gc_ = groups["bull"], groups["bear"], groups["chop"]
    out["kw_h"] = (kw_h_stat([gb, gr, gc_])
                   if min(len(gb), len(gr), len(gc_)) >= MIN_BUCKET
                   else np.nan)
    trend_eff = np.nanmean([out["eff_bull"], out["eff_bear"]])
    trend_ac1 = np.nanmean([out["ac1_bull"], out["ac1_bear"]])
    out["d_eff"] = trend_eff - out["eff_chop"]
    out["d_ac1"] = trend_ac1 - out["ac1_chop"]
    out["n_bars"] = n
    return out


# --------------------------------------------------------------------------
# Null machinery (stationary bootstrap, OHLC-geometry preserving)
# --------------------------------------------------------------------------

def sb_indices(n, mean_block, rng):
    k = int(2 * n / mean_block) + 10
    lens = rng.geometric(1.0 / mean_block, size=k)
    cl = np.cumsum(lens)
    k = int(np.searchsorted(cl, n)) + 1
    lens = lens[:k]
    total = int(cl[k - 1])
    starts = rng.integers(0, n, size=k)
    offs = np.arange(total) - np.repeat(np.concatenate(([0], cl[:k - 1])),
                                        lens)
    return ((np.repeat(starts, lens) + offs) % n)[:n]


def make_null_path(h_rel, l_rel, c_rel, c0, idx):
    cr = c_rel[idx]
    close = c0 * np.cumprod(cr)
    prev = np.concatenate(([c0], close[:-1]))
    return prev * h_rel[idx], prev * l_rel[idx], close


# --------------------------------------------------------------------------
# Per-series pipeline
# --------------------------------------------------------------------------

def run_series(df, bpy, rng, only=None):
    """Real + null scoring for the selected classifiers on one series."""
    h, l, c = df["High"].values, df["Low"].values, df["Close"].values
    n = len(c)
    is_end = int(IS_FRACTION * n)
    windows = {"FULL": slice(0, n), "IS": slice(0, is_end),
               "OOS": slice(is_end, n)}
    fns = {}
    only = only or CLASSIFIERS
    if "ADX" in only:
        fns["ADX"] = cls_adx
    if "ER" in only:
        fns["ER"] = cls_er
    if "HMM" in only:
        hmm = HMMClassifier(c, is_end)
        fns["HMM"] = lambda H, L, C: hmm.label(C)
    if "SWING" in only:
        fns["SWING"] = cls_swing

    real = {}
    for name, fn in fns.items():
        lab = fn(h, l, c)
        real[name] = {w: score_window(lab, c, bpy, sl)
                      for w, sl in windows.items()}

    # null distributions of the benchmarked stats (FULL and OOS windows)
    prev = c[:-1]
    h_rel, l_rel, c_rel = h[1:] / prev, l[1:] / prev, c[1:] / prev
    m = len(c_rel)
    is_end_b = int(IS_FRACTION * m)
    wins_b = {"FULL": slice(0, m), "OOS": slice(is_end_b, m)}
    nulls = {name: {w: {k: np.full(N_BOOT, np.nan) for k in BENCH_STATS}
                    for w in wins_b} for name in fns}
    for b in range(N_BOOT):
        idx = sb_indices(m, MEAN_BLOCK, rng)
        hh, ll, cc = make_null_path(h_rel, l_rel, c_rel, c[0], idx)
        for name, fn in fns.items():
            lab = fn(hh, ll, cc)
            for w, sl in wins_b.items():
                sc = score_window(lab, cc, bpy, sl)
                if sc is None:
                    continue
                for k in BENCH_STATS:
                    nulls[name][w][k][b] = sc[k]
    return real, nulls


def null_summary(real_val, nd):
    nd = nd[~np.isnan(nd)]
    if len(nd) < 50 or real_val is None or math.isnan(real_val):
        return dict(null_mean=np.nan, null_p5=np.nan, null_p95=np.nan,
                    z=np.nan, p=np.nan)
    mu, sd = nd.mean(), nd.std()
    return dict(null_mean=mu, null_p5=np.percentile(nd, 5),
                null_p95=np.percentile(nd, 95),
                z=(real_val - mu) / sd if sd > 0 else np.nan,
                p=(1 + (nd >= real_val).sum()) / (1 + len(nd)))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def evaluate(series, classifiers=None):
    """Score the selected classifiers on every series; long-form rows."""
    classifiers = classifiers or CLASSIFIERS
    rows = []
    rng_master = np.random.default_rng(SEED)
    t0 = time.time()
    for (group, tf), members in sorted(series.items()):
        for tkr, df in sorted(members.items()):
            bpy = bars_per_year(df.index)
            rng = np.random.default_rng(rng_master.integers(2 ** 63))
            real, nulls = run_series(df, bpy, rng, only=classifiers)
            for name in classifiers:
                for w in ["FULL", "IS", "OOS"]:
                    sc = real[name][w]
                    if sc is None:
                        continue
                    row = dict(classifier=name, group=group, timeframe=tf,
                               instrument=tkr, window=w,
                               bars_per_year=round(bpy), **sc)
                    if w in nulls[name]:
                        for k in BENCH_STATS:
                            ns = null_summary(sc[k], nulls[name][w][k])
                            row.update({f"{k}_{kk}": vv
                                        for kk, vv in ns.items()})
                    rows.append(row)
            print(f"  scored {tkr:9s} {tf}  ({time.time()-t0:5.0f}s)")
    return pd.DataFrame(rows)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    print("Loading 1h data (Yahoo ~730d cap) and resampling 4h (UTC "
          "midnight anchor)...")
    series, samples, skipped = {}, [], []
    for tkr in CRYPTO + FUTURES:
        df1h = load_1h(tkr)
        if df1h is None:
            skipped.append((tkr, "download failed"))
            continue
        for tf, df in [("1h", df1h), ("4h", resample_4h(df1h))]:
            if len(df) < MIN_BARS:
                skipped.append((f"{tkr} {tf}", f"only {len(df)} bars"))
                continue
            series.setdefault((GROUP_OF[tkr], tf), {})[tkr] = df
            samples.append(dict(group=GROUP_OF[tkr], timeframe=tf,
                                instrument=tkr, n_bars=len(df),
                                start=str(df.index[0].date()),
                                end=str(df.index[-1].date()),
                                bars_per_year=round(bars_per_year(df.index))))
    print(f"{len(samples)} series loaded; skipped: {skipped or 'none'}")

    print(f"\nScoring ADX/ER/HMM vs null (B={N_BOOT}, mean block "
          f"{MEAN_BLOCK})...")
    df = evaluate(series)

    # pre-registered pass check
    full = df[df["window"] == "FULL"]
    passed = {}
    for cls in CLASSIFIERS:
        sub = full[full["classifier"] == cls]
        share = (sub["s1_p"] < 0.05).mean()
        passed[cls] = share >= PASS_SHARE
        print(f"  {cls}: {100*(sub['s1_p'] < 0.05).mean():.0f}% of configs "
              f"beat null on S1 (need >={100*PASS_SHARE:.0f}%) -> "
              f"{'PASS' if passed[cls] else 'FAIL'}")

    swing_df = None
    if not any(passed.values()):
        print("\nAll three classifiers FAILED the pre-registered criterion "
              "-> running the market-structure fallback under the identical "
              "test...")
        swing_df = evaluate(series, classifiers=["SWING"])
        sub = swing_df[swing_df["window"] == "FULL"]
        share = (sub["s1_p"] < 0.05).mean()
        passed["SWING"] = share >= PASS_SHARE
        print(f"  SWING: {100*share:.0f}% of configs beat null on S1 -> "
              f"{'PASS' if passed['SWING'] else 'FAIL'}")
        df = pd.concat([df, swing_df], ignore_index=True)

    df.to_csv(os.path.join(OUT_DIR, "regime_metrics.csv"), index=False,
              float_format="%.6f")
    write_summary(df, pd.DataFrame(samples), passed, skipped)
    print(f"\nDone in {time.time()-t0:.0f}s. Outputs in {OUT_DIR}/")


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def fmt(x, nd=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{x:.{nd}f}"


def bps(x):
    return "—" if x is None or math.isnan(x) else f"{1e4*x:.1f}"


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


def write_summary(df, samples, passed, skipped):
    L = []
    A = L.append
    all_cls = [c for c in ["ADX", "ER", "HMM", "SWING"]
               if c in df["classifier"].unique()]

    A("# Intraday regime assessment — BULL/BEAR/CHOP vs a random-walk null "
      "(1h & 4h, crypto vs futures)")
    A("")
    A(f"*Run date: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d}. Concurrent "
      "regime CLASSIFICATION only — no trades, no prediction claims. "
      f"Null = stationary block bootstrap (B={N_BOOT}, mean block "
      f"{MEAN_BLOCK} bars, seeded) of each instrument's own bars, "
      "preserving return distribution and per-bar OHLC geometry. p-values "
      "are one-sided empirical P(null ≥ real). 4h bars are resampled from "
      "1h anchored to UTC midnight (native 4h unused, for cross-group "
      "consistency). **Futures are front-month continuous with roll gaps "
      "that contaminate both the real and null regime states — "
      "back-adjusted contracts are needed for firm futures conclusions.** "
      "HMM caveat: states are fit once on the in-sample 70% and decoded "
      "with Viterbi (a smoothing decode — the label at bar t uses the "
      "whole sequence); the null is decoded with the same frozen model, "
      "keeping the comparison like-for-like. Pre-registered pass "
      f"criterion: ≥{100*PASS_SHARE:.0f}% of a classifier's configs with "
      "BULL−BEAR forward-drift spread (S1) beating the null at p<0.05 on "
      "the FULL window.*")
    A("")

    A("## 1. Sample sizes")
    A("")
    s = samples.sort_values(["timeframe", "group", "instrument"])
    A(md_table(s, ["group", "timeframe", "instrument", "start", "end",
                   "n_bars", "bars_per_year"],
               ["Group", "TF", "Instrument", "Start", "End", "Bars",
                "Bars/yr"], 0))
    A("")
    A(("Skipped: " + ", ".join(f"{t} ({w})" for t, w in skipped))
      if skipped else "No series skipped.")
    A("")

    # ---- 2 separation table ----
    A("## 2. Regime separation vs null (classifier × group × timeframe)")
    A("")
    A("S1 = mean forward drift(BULL) − drift(BEAR), in bps/bar. "
      "`beat` = share of instruments with S1 p<0.05 vs the null; same for "
      "the Kruskal-Wallis H across the three buckets. Medians across "
      "instruments; FULL window, with OOS S1 alongside.")
    A("")
    rows = []
    for (cls, g, tf), grp in df[df["window"] == "FULL"].groupby(
            ["classifier", "group", "timeframe"]):
        oos = df[(df["window"] == "OOS") & (df["classifier"] == cls)
                 & (df["group"] == g) & (df["timeframe"] == tf)]
        rows.append(dict(
            classifier=cls, group=g, timeframe=tf,
            s1_bps=1e4 * grp["s1"].median(),
            s1_null_bps=1e4 * grp["s1_null_mean"].median(),
            s1_p_med=grp["s1_p"].median(),
            s1_beat=f"{int((grp['s1_p'] < 0.05).sum())}/{len(grp)}",
            kw_beat=f"{int((grp['kw_h_p'] < 0.05).sum())}/{len(grp)}",
            oos_s1_bps=1e4 * oos["s1"].median(),
            oos_beat=f"{int((oos['s1_p'] < 0.05).sum())}/{len(oos)}",
            chop_share=grp["share_chop"].median()))
    sep = pd.DataFrame(rows).sort_values(["classifier", "group",
                                          "timeframe"])
    A(md_table(sep, ["classifier", "group", "timeframe", "s1_bps",
                     "s1_null_bps", "s1_p_med", "s1_beat", "kw_beat",
                     "oos_s1_bps", "oos_beat", "chop_share"],
               ["Classifier", "Group", "TF", "S1 (bps)", "S1 null mean",
                "S1 p (med)", "S1 beat null", "KW beat null", "OOS S1 (bps)",
                "OOS beat", "CHOP share"]))
    A("")

    # ---- 3 per-regime behavior ----
    A("## 3. Per-regime forward behavior (medians across instruments, "
      "FULL window)")
    A("")
    for cls in all_cls:
        rows = []
        for (g, tf), grp in df[(df["window"] == "FULL")
                               & (df["classifier"] == cls)].groupby(
                ["group", "timeframe"]):
            rows.append(dict(
                group=g, timeframe=tf,
                drift_bull=1e4 * grp["drift_bull"].median(),
                drift_chop=1e4 * grp["drift_chop"].median(),
                drift_bear=1e4 * grp["drift_bear"].median(),
                vol_bull=grp["vol_bull"].median(),
                vol_chop=grp["vol_chop"].median(),
                vol_bear=grp["vol_bear"].median(),
                ac1_trend=np.nanmedian(np.concatenate(
                    [grp["ac1_bull"].values, grp["ac1_bear"].values])),
                ac1_chop=grp["ac1_chop"].median(),
                eff_trend=np.nanmedian(np.concatenate(
                    [grp["eff_bull"].values, grp["eff_bear"].values])),
                eff_chop=grp["eff_chop"].median()))
        A(f"### {cls}")
        A("")
        A(md_table(pd.DataFrame(rows),
                   ["group", "timeframe", "drift_bull", "drift_chop",
                    "drift_bear", "vol_bull", "vol_chop", "vol_bear",
                    "ac1_trend", "ac1_chop", "eff_trend", "eff_chop"],
                   ["Group", "TF", "Drift BULL (bps)", "Drift CHOP",
                    "Drift BEAR", "Vol BULL", "Vol CHOP", "Vol BEAR",
                    "AC1 trend", "AC1 chop", "Eff trend", "Eff chop"]))
        A("")

    # ---- 4 CHOP validity ----
    A("## 4. Does the CHOP state work? (trend-minus-chop diffs vs null)")
    A("")
    A("d_eff = per-segment efficiency of trend states minus CHOP; d_ac1 = "
      "lag-1 autocorr of trend states minus CHOP. Positive and beating the "
      "null would mean CHOP genuinely isolates the low-persistence, "
      "going-nowhere bars. ER's own d_eff is partially circular (it labels "
      "by trailing efficiency) — flagged, judge it on drift/persistence.")
    A("")
    rows = []
    for (cls, g, tf), grp in df[df["window"] == "FULL"].groupby(
            ["classifier", "group", "timeframe"]):
        rows.append(dict(
            classifier=cls, group=g, timeframe=tf,
            d_eff=grp["d_eff"].median(),
            d_eff_beat=f"{int((grp['d_eff_p'] < 0.05).sum())}/{len(grp)}",
            d_ac1=grp["d_ac1"].median(),
            d_ac1_beat=f"{int((grp['d_ac1_p'] < 0.05).sum())}/{len(grp)}",
            chop_absdrift_ok=f"{int((grp['drift_chop'].abs() < grp[['drift_bull', 'drift_bear']].abs().min(axis=1)).sum())}/{len(grp)}"))
    A(md_table(pd.DataFrame(rows).sort_values(["classifier", "group",
                                               "timeframe"]),
               ["classifier", "group", "timeframe", "d_eff", "d_eff_beat",
                "d_ac1", "d_ac1_beat", "chop_absdrift_ok"],
               ["Classifier", "Group", "TF", "d_eff", "d_eff beat null",
                "d_ac1", "d_ac1 beat null", "|CHOP drift| smallest"]))
    A("")

    # ---- 5 comparisons ----
    A("## 5. Timeframe and asset-class comparison (share of configs "
      "beating null on S1, FULL)")
    A("")
    full = df[df["window"] == "FULL"]
    rows = []
    for key, grp in full.groupby(["timeframe"]):
        rows.append(dict(axis="timeframe", value=key[0],
                         beat=f"{int((grp['s1_p'] < 0.05).sum())}/{len(grp)}",
                         share=(grp["s1_p"] < 0.05).mean()))
    for key, grp in full.groupby(["group"]):
        rows.append(dict(axis="group", value=key[0],
                         beat=f"{int((grp['s1_p'] < 0.05).sum())}/{len(grp)}",
                         share=(grp["s1_p"] < 0.05).mean()))
    A(md_table(pd.DataFrame(rows), ["axis", "value", "beat", "share"],
               ["Axis", "Value", "Configs beating null", "Share"]))
    A("")

    # ---- 6 answers ----
    A("## 6. Plain-English answers")
    A("")
    A(build_answers(df, passed, all_cls))
    A("")
    A("---")
    A(f"*Total configs evaluated: {len(all_cls)} classifiers × "
      f"{full['instrument'].nunique()} instruments × 2 timeframes, "
      "windows FULL/IS/OOS; all metrics incl. null means/percentiles/"
      "p-values in `output/regime_metrics.csv`. Reproduce: "
      "`python regime_scoring.py` (seeded).*")

    with open(os.path.join(OUT_DIR, "SUMMARY.md"), "w") as f:
        f.write("\n".join(L))


def build_answers(df, passed, all_cls):
    out = []
    full = df[df["window"] == "FULL"]
    oos = df[df["window"] == "OOS"]

    def beat_share(cls=None, g=None, tf=None, frame=None):
        sub = frame if frame is not None else full
        if cls:
            sub = sub[sub["classifier"] == cls]
        if g:
            sub = sub[sub["group"] == g]
        if tf:
            sub = sub[sub["timeframe"] == tf]
        return (sub["s1_p"] < 0.05).mean(), len(sub)

    # Q1
    out.append("**Q1 — Can regime be mechanically assessed on 4h/1h?**")
    for cls in all_cls:
        for tf in ["1h", "4h"]:
            sh, n = beat_share(cls=cls, tf=tf)
            sh_o, _ = beat_share(cls=cls, tf=tf, frame=oos)
            out.append(f"- {cls} {tf}: {100*sh:.0f}% of {n} configs beat "
                       f"the null on BULL−BEAR separation (OOS: "
                       f"{100*sh_o:.0f}%) → "
                       f"{'YES' if sh >= PASS_SHARE else 'NO'} by the "
                       "pre-registered bar.")
    out.append("")

    # Q2
    ranks = {cls: beat_share(cls=cls)[0] for cls in all_cls}
    order = sorted(ranks, key=ranks.get, reverse=True)
    out.append("**Q2 — Which classifier separates best?** Ranked by share "
               "of configs beating the null on S1 (FULL): "
               + ", ".join(f"{c} ({100*ranks[c]:.0f}%)" for c in order)
               + f". Pre-registered verdicts: "
               + ", ".join(f"{c}: {'PASS' if passed.get(c) else 'FAIL'}"
                           for c in all_cls) + ".")
    out.append("")

    # Q3 chop validity
    ce = full.groupby("classifier")[["d_eff_p", "d_ac1_p"]].apply(
        lambda x: pd.Series({"eff": (x["d_eff_p"] < 0.05).mean(),
                             "ac1": (x["d_ac1_p"] < 0.05).mean()}))
    out.append("**Q3 — Does the CHOP state actually work?** Share of "
               "configs where trend-minus-chop efficiency / persistence "
               "beats the null: "
               + "; ".join(f"{c}: eff {100*r['eff']:.0f}%, ac1 "
                           f"{100*r['ac1']:.0f}%" for c, r in ce.iterrows())
               + ".")
    out.append("")

    # Q4 / Q5
    for axis, vals, qn in [("timeframe", ["1h", "4h"], "Q4 — 1h vs 4h"),
                           ("group", ["crypto", "futures"],
                            "Q5 — crypto vs futures")]:
        parts = []
        for v in vals:
            sh, n = beat_share(**{("tf" if axis == "timeframe" else "g"): v})
            parts.append(f"{v}: {100*sh:.0f}% of {n}")
        out.append(f"**{qn}:** configs beating the null on S1 — "
                   + ", ".join(parts) + ".")
        out.append("")

    # Q6
    fails = [c for c in all_cls if not passed.get(c)]
    if fails:
        out.append("**Q6 — Cosmetic labels:** "
                   + ", ".join(fails)
                   + " did not beat the shuffled null at the pre-registered "
                   "bar — their BULL/BEAR/CHOP labels partition bars in "
                   "ways statistically indistinguishable from the same "
                   "labels drawn on block-shuffled (structureless) data. "
                   "Those regime labels are cosmetic at these timeframes.")
    else:
        out.append("**Q6:** all classifiers cleared the pre-registered bar.")
    if "SWING" in all_cls and not passed.get("SWING"):
        out.append("")
        out.append("**Fallback verdict:** the pre-registered market-"
                   "structure classifier ALSO failed the identical test. "
                   "The honest conclusion is that these markets do not "
                   "yield a mechanically-validated three-state regime "
                   "label at 1h/4h; the exploitable object remains the "
                   "weak probabilistic crypto persistence at daily/weekly "
                   "horizons found in the prior studies.")
    return "\n".join(out)


if __name__ == "__main__":
    main()
