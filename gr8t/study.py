"""Trend-filter study: does multi-timeframe MA alignment actually predict trend?

This deliberately ignores the entry/exit logic. For every base bar it classifies
the market state from the moving-average alignment (aligned-bull / aligned-bear /
mixed) using only information available at that bar, then measures the *forward*
return over several horizons. A trend filter "works" if, beyond the market's
unconditional drift:

  * aligned-bull bars are followed by up moves more often than baseline, and
  * aligned-bear bars are followed by down moves more often than baseline,

while the mixed state looks like chop (little directional follow-through) and the
state doesn't whipsaw every few bars.

It compares SMA vs EMA, and all-3-timeframe alignment vs the highest timeframe
alone. Forward returns use future data on purpose — that is the question being
asked ("given the state now, what happens next?"), and every *state* is computed
without look-ahead, so this is a predictiveness study, not a tradeable signal.

    python -m gr8t.study --symbol ES=F --preset swing --report es_trend.html
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .config import Config
from .data import load_base, resample, synthetic_series, bar_duration
from .indicators import moving_average


# --------------------------------------------------------------------------- #
# state construction (no look-ahead)
# --------------------------------------------------------------------------- #
def _tf_trend(htf: pd.DataFrame, period: int, kind: str) -> np.ndarray:
    ma = moving_average(htf["close"], period, kind)
    return np.where(htf["close"] > ma, "bull",
                    np.where(htf["close"] < ma, "bear", "none"))


def _aligned_to_base(base_index: pd.DatetimeIndex, htf: pd.DataFrame, tf: str,
                     period: int, kind: str) -> pd.Series:
    """Project a higher-timeframe MA trend onto the base index using only the
    most recently *completed* HTF bar (as-of join on close times)."""
    trend = _tf_trend(htf, period, kind)
    htf_close = (htf.index + bar_duration(tf)).as_unit("ns")
    base_dt = (base_index[1] - base_index[0]) if len(base_index) > 1 else pd.Timedelta(0)
    left = pd.DataFrame({"ct": (base_index + base_dt).as_unit("ns")})
    right = pd.DataFrame({"ct": htf_close, "tr": trend})
    merged = pd.merge_asof(left.sort_values("ct"), right.sort_values("ct"),
                           on="ct", direction="backward", allow_exact_matches=True)
    return pd.Series(merged["tr"].to_numpy(), index=base_index).fillna("none")


def states(base: pd.DataFrame, cfg: Config, kind: str, strictness: str) -> pd.Series:
    """Per-base-bar trend state ('bull'/'bear'/'none').

    strictness: 'all3' (every timeframe agrees), '2of3' (majority), or
    'high' (the highest timeframe alone)."""
    mid = resample(base, cfg.mid_tf)
    high = resample(base, cfg.high_tf)
    tb = _tf_trend(base, cfg.sma_period, kind)            # base TF, at its own close
    tm = _aligned_to_base(base.index, mid, cfg.mid_tf, cfg.sma_period, kind).to_numpy()
    th = _aligned_to_base(base.index, high, cfg.high_tf, cfg.sma_period, kind).to_numpy()

    if strictness == "high":
        out = th
    else:
        bull = (tb == "bull").astype(int) + (tm == "bull").astype(int) + (th == "bull").astype(int)
        bear = (tb == "bear").astype(int) + (tm == "bear").astype(int) + (th == "bear").astype(int)
        need = 3 if strictness == "all3" else 2
        out = np.where(bull >= need, "bull", np.where(bear >= need, "bear", "none"))
    return pd.Series(out, index=base.index)


# --------------------------------------------------------------------------- #
# forward-return analysis
# --------------------------------------------------------------------------- #
def forward_return(close: pd.Series, h: int) -> np.ndarray:
    c = close.to_numpy(dtype=float)
    out = np.full(len(c), np.nan)
    out[:-h] = c[h:] / c[:-h] - 1.0
    return out


def _whipsaw(state: pd.Series) -> dict:
    s = state.to_numpy()
    flips = int((s[1:] != s[:-1]).sum())
    # average run length while in an aligned (bull/bear) state
    runs, cur, prev = [], 0, None
    for v in s:
        if v in ("bull", "bear"):
            if v == prev:
                cur += 1
            else:
                if cur:
                    runs.append(cur)
                cur = 1
        else:
            if cur:
                runs.append(cur)
            cur = 0
        prev = v
    if cur:
        runs.append(cur)
    return {"flips": flips, "median_run": float(np.median(runs)) if runs else 0.0}


# --------------------------------------------------------------------------- #
# crossover persistence: when all 3 TFs fully align, how long does it hold?
# --------------------------------------------------------------------------- #
def crossover_runs(base: pd.DataFrame, cfg: Config, kind: str):
    """Find every 'full crossover' (the bar all three timeframes first agree)
    and measure how many consecutive bars the aligned state holds before it
    breaks. Returns {'bull': [...], 'bear': [...]} run lengths plus, for each
    run, whether it ended by flipping to the opposite side or just decaying to
    mixed, and a right-censored flag for a run still open at the data end."""
    s = states(base, cfg, kind, "all3").to_numpy()
    n = len(s)
    runs = {"bull": [], "bear": []}
    ends = {"bull": {"flip": 0, "mixed": 0, "open": 0},
            "bear": {"flip": 0, "mixed": 0, "open": 0}}
    prev = None
    for i in range(n):
        cur = s[i]
        if cur in ("bull", "bear") and cur != prev:        # a fresh full crossover
            j = i
            while j < n and s[j] == cur:
                j += 1
            runs[cur].append(j - i)
            opp = "bear" if cur == "bull" else "bull"
            if j >= n:
                ends[cur]["open"] += 1
            elif s[j] == opp:
                ends[cur]["flip"] += 1
            else:
                ends[cur]["mixed"] += 1
        prev = cur
    return runs, ends


def _pct(arr, q):
    return float(np.percentile(arr, q)) if len(arr) else float("nan")


def persistence_summary(base: pd.DataFrame, cfg: Config, kind: str) -> dict:
    runs, ends = crossover_runs(base, cfg, kind)
    bar_min = bar_duration(cfg.base_tf).total_seconds() / 60.0
    out = {"kind": kind.upper(), "bar_min": bar_min}
    for d in ("bull", "bear"):
        r = np.array(runs[d], dtype=float)
        e = ends[d]
        tot = max(int(r.sum()), 0)
        out[d] = {
            "events": len(r),
            "median": float(np.median(r)) if r.size else 0.0,
            "mean": float(r.mean()) if r.size else 0.0,
            "p25": _pct(r, 25), "p75": _pct(r, 75), "p90": _pct(r, 90),
            "max": float(r.max()) if r.size else 0.0,
            # whipsaw share: aligned state lost within ~30 min and ~1h
            "pct_le_6": float((r <= 6).mean() * 100) if r.size else 0.0,
            "pct_le_12": float((r <= 12).mean() * 100) if r.size else 0.0,
            "pct_ge_78": float((r >= 78).mean() * 100) if r.size else 0.0,  # >= ~1 day
            "flip": e["flip"], "mixed": e["mixed"], "open": e["open"],
            "bars_total": tot,
        }
    return out


_RUN_BUCKETS = [(0, 6, "≤30m"), (6, 12, "30-60m"), (12, 24, "1-2h"),
                (24, 48, "2-4h"), (48, 78, "4h-1d"), (78, 234, "1-3d"),
                (234, 10**9, ">3d")]


def _bucket_counts(run_lengths):
    r = np.array(run_lengths, dtype=float)
    return [int(((r > lo) & (r <= hi)).sum()) if i else int((r <= hi).sum())
            for i, (lo, hi, _) in enumerate(_RUN_BUCKETS)]


@dataclass
class Row:
    kind: str
    strictness: str
    horizon: int
    horizon_lbl: str
    pct_bull: float
    pct_bear: float
    pct_mix: float
    base_p_up: float
    bull_p_up: float
    bear_p_dn: float
    edge_bull: float        # bull P(up) - baseline P(up)   (drift-adjusted)
    edge_bear: float        # bear P(dn) - baseline P(dn)
    mean_cont: float        # mean continuation return (bull:+fwd, bear:-fwd)
    mean_mix_abs: float     # mean |fwd| in the mixed state (chop magnitude)
    flips: int
    median_run: float


def _bars_per_day(base_tf: str) -> float:
    dt = bar_duration(base_tf)
    if dt >= pd.Timedelta("1D"):
        return 1.0
    # ~6.5h RTH for intraday equities/futures sampled by Yahoo
    return (6.5 * 3600) / dt.total_seconds()


def _horizons(base_tf: str) -> list[tuple[int, str]]:
    bpd = _bars_per_day(base_tf)
    specs = [(0.5, "½d"), (1, "1d"), (3, "3d"), (5, "1wk")]
    out = []
    for days, lbl in specs:
        h = max(1, round(days * bpd))
        out.append((h, lbl))
    # de-duplicate identical bar counts
    seen, uniq = set(), []
    for h, lbl in out:
        if h not in seen:
            seen.add(h)
            uniq.append((h, lbl))
    return uniq


def run_study(base: pd.DataFrame, cfg: Config, *,
              kinds=("sma", "ema"), strictnesses=("all3", "high")) -> list[Row]:
    close = base["close"]
    horizons = _horizons(cfg.base_tf)
    rows: list[Row] = []
    for h, lbl in horizons:
        fwd = forward_return(close, h)
        valid = ~np.isnan(fwd)
        base_p_up = float((fwd[valid] > 0).mean())
        for kind in kinds:
            for strict in strictnesses:
                st = states(base, cfg, kind, strict)
                w = _whipsaw(st)
                s = st.to_numpy()
                m = valid
                is_bull = (s == "bull") & m
                is_bear = (s == "bear") & m
                is_mix = (s == "none") & m
                n = int(m.sum())
                bull_fwd = fwd[is_bull]
                bear_fwd = fwd[is_bear]
                bull_p_up = float((bull_fwd > 0).mean()) if bull_fwd.size else float("nan")
                bear_p_dn = float((bear_fwd < 0).mean()) if bear_fwd.size else float("nan")
                cont = np.concatenate([bull_fwd, -bear_fwd]) if (bull_fwd.size + bear_fwd.size) else np.array([])
                rows.append(Row(
                    kind=kind.upper(), strictness=strict, horizon=h, horizon_lbl=lbl,
                    pct_bull=float(is_bull.sum()) / n * 100,
                    pct_bear=float(is_bear.sum()) / n * 100,
                    pct_mix=float(is_mix.sum()) / n * 100,
                    base_p_up=base_p_up * 100,
                    bull_p_up=bull_p_up * 100,
                    bear_p_dn=bear_p_dn * 100,
                    edge_bull=(bull_p_up - base_p_up) * 100,
                    edge_bear=(bear_p_dn - (1 - base_p_up)) * 100,
                    mean_cont=float(cont.mean()) * 100 if cont.size else float("nan"),
                    mean_mix_abs=float(np.abs(fwd[is_mix]).mean()) * 100 if is_mix.any() else float("nan"),
                    flips=w["flips"], median_run=w["median_run"],
                ))
    return rows


# --------------------------------------------------------------------------- #
# text + visual output
# --------------------------------------------------------------------------- #
def format_table(rows: list[Row], cfg: Config) -> str:
    hdr = (f"{'method':6} {'align':5} {'horiz':5} "
           f"{'%bull':>6} {'%bear':>6} {'%mix':>6}  "
           f"{'baseUp':>6} {'bullUp':>6} {'bearDn':>6}  "
           f"{'edgeB':>6} {'edgeS':>6}  {'contRet':>8} {'mixVol':>7}  {'flips':>6} {'run':>5}")
    lines = [hdr, "-" * len(hdr)]
    for r in rows:
        lines.append(
            f"{r.kind:6} {r.strictness:5} {r.horizon_lbl:>5} "
            f"{r.pct_bull:6.1f} {r.pct_bear:6.1f} {r.pct_mix:6.1f}  "
            f"{r.base_p_up:6.1f} {r.bull_p_up:6.1f} {r.bear_p_dn:6.1f}  "
            f"{r.edge_bull:+6.1f} {r.edge_bear:+6.1f}  {r.mean_cont:+8.3f} {r.mean_mix_abs:7.3f}  "
            f"{r.flips:6d} {r.median_run:5.0f}")
    legend = (
        "\nedgeB = bull P(up) - baseline P(up)   |   edgeS = bear P(down) - baseline P(down)\n"
        "  (both > 0 means alignment adds directional info beyond drift)\n"
        "contRet = mean continuation return %/horizon   |   mixVol = mean |return| in mixed state\n"
        "flips = state changes over the sample   |   run = median aligned-run length (bars)")
    return "\n".join(lines) + "\n" + legend


def build_study_report(rows: list[Row], cfg: Config, meta: dict, source: str) -> str:
    from .report import _svg_bars, _PAGE, _card

    # pick the 1-day horizon as the headline (or the middle one)
    by_h = sorted({r.horizon for r in rows})
    head_h = by_h[min(1, len(by_h) - 1)]
    head = [r for r in rows if r.horizon == head_h]

    cards = []
    for r in head:
        cls = "pos" if (r.edge_bull > 0 and r.edge_bear > 0) else ("neg" if (r.edge_bull < 0 or r.edge_bear < 0) else "")
        cards.append(_card(f"{r.kind} {r.strictness} · edges @{r.horizon_lbl}",
                           f"+{r.edge_bull:.1f} / {r.edge_bear:+.1f} pp", cls))
    cards_html = "".join(cards)

    # charts: continuation edge by config, per horizon
    sections = []
    labels = [f"{r.kind}/{r.strictness}/{r.horizon_lbl}" for r in rows]
    edge_b = [round(r.edge_bull, 2) for r in rows]
    edge_s = [round(r.edge_bear, 2) for r in rows]
    cont = [round(r.mean_cont, 3) for r in rows]
    col_b = ["#1f9d55" if x >= 0 else "#e3342f" for x in edge_b]
    col_s = ["#1f9d55" if x >= 0 else "#e3342f" for x in edge_s]
    col_c = ["#1f9d55" if x >= 0 else "#e3342f" for x in cont]
    sections.append(("Bull edge: P(up | aligned-bull) − baseline, pp",
                     _svg_bars(edge_b, col_b, labels=labels, fmt="{:+.0f}", label_every=1)))
    sections.append(("Bear edge: P(down | aligned-bear) − baseline, pp",
                     _svg_bars(edge_s, col_s, labels=labels, fmt="{:+.0f}", label_every=1)))
    sections.append(("Mean continuation return, %/horizon",
                     _svg_bars(cont, col_c, labels=labels, fmt="{:+.1f}", label_every=1)))
    charts_html = "".join(f'<section class="panel"><h3>{t}</h3>{svg}</section>'
                          for t, svg in sections)

    # table
    th = ("<tr><th class='l'>method</th><th class='l'>align</th><th>horiz</th>"
          "<th>%bull</th><th>%bear</th><th>%mix</th><th>base↑</th><th>bull↑</th>"
          "<th>bear↓</th><th>edgeB</th><th>edgeS</th><th>contRet</th>"
          "<th>flips</th><th>run</th></tr>")
    trs = []
    for r in rows:
        ec = "pos" if r.edge_bull > 0 else "neg"
        sc = "pos" if r.edge_bear > 0 else "neg"
        trs.append(
            f"<tr><td class='l'>{r.kind}</td><td class='l'>{r.strictness}</td>"
            f"<td>{r.horizon_lbl}</td><td>{r.pct_bull:.0f}</td><td>{r.pct_bear:.0f}</td>"
            f"<td>{r.pct_mix:.0f}</td><td>{r.base_p_up:.1f}</td><td>{r.bull_p_up:.1f}</td>"
            f"<td>{r.bear_p_dn:.1f}</td><td class='{ec}'>{r.edge_bull:+.1f}</td>"
            f"<td class='{sc}'>{r.edge_bear:+.1f}</td><td>{r.mean_cont:+.2f}</td>"
            f"<td>{r.flips}</td><td>{r.median_run:.0f}</td></tr>")
    table = (f'<section class="panel"><h3>Full results</h3><div class="tw"><table>'
             f'<thead>{th}</thead><tbody>{"".join(trs)}</tbody></table></div></section>')

    tfs = f"{cfg.base_tf}/{cfg.mid_tf}/{cfg.high_tf}"
    subtitle = (f"trend-filter predictiveness · {tfs} · {meta.get('start','?')} → "
                f"{meta.get('end','?')} · {meta.get('n_base','?')} bars · {source}")
    body = (f'<section class="cards">{cards_html}</section>{charts_html}{table}')
    return _PAGE.format(title=f"{cfg.symbol} · trend study", subtitle=subtitle, body=body)


# --------------------------------------------------------------------------- #
# persistence output
# --------------------------------------------------------------------------- #
def _fmt_dur(bars: float, bar_min: float) -> str:
    mins = bars * bar_min
    if mins < 60:
        return f"{mins:.0f}m"
    if mins < 60 * 24:
        return f"{mins/60:.1f}h"
    return f"{mins/60/24:.1f}d"


def format_persistence(summaries: list[dict], cfg: Config) -> str:
    bm = summaries[0]["bar_min"]
    lines = []
    for d in ("bull", "bear"):
        lines.append(f"\n  Full {d.upper()} crossover — how long the all-3 aligned state holds")
        hdr = (f"  {'MA':4} {'events':>6} {'median':>8} {'mean':>8} {'p75':>8} {'p90':>8} "
               f"{'max':>8}  {'≤30m':>6} {'≥1d':>6}  {'flip%':>6} {'mix%':>6} {'%time':>6}")
        lines.append(hdr)
        lines.append("  " + "-" * (len(hdr) - 2))
        for s in summaries:
            x = s[d]
            n_end = max(x["flip"] + x["mixed"] + x["open"], 1)
            pct_time = x["bars_total"]  # filled below as %
            lines.append(
                f"  {s['kind']:4} {x['events']:6d} "
                f"{_fmt_dur(x['median'], bm):>8} {_fmt_dur(x['mean'], bm):>8} "
                f"{_fmt_dur(x['p75'], bm):>8} {_fmt_dur(x['p90'], bm):>8} {_fmt_dur(x['max'], bm):>8}  "
                f"{x['pct_le_6']:5.0f}% {x['pct_ge_78']:5.0f}%  "
                f"{x['flip']/n_end*100:5.0f}% {x['mixed']/n_end*100:5.0f}% "
                f"{x['_pct_time']:5.1f}%")
        lines.append("")
    legend = ("  median/mean/p75/p90/max = duration the aligned state holds after a full crossover\n"
              "  ≤30m = share of crossovers that un-align within 30 min (whipsaw)\n"
              "  ≥1d  = share that hold at least one trading day\n"
              "  flip%/mix% = how the run ends (flips to opposite vs decays to mixed)\n"
              "  %time = share of all bars spent in that aligned state")
    return "\n".join(lines) + "\n" + legend


def build_persistence_report(summaries: list[dict], runs_by_kind: dict,
                             cfg: Config, meta: dict, source: str) -> str:
    from .report import _svg_bars, _PAGE, _card

    bm = summaries[0]["bar_min"]
    cards = []
    for s in summaries:
        for d in ("bull", "bear"):
            x = s[d]
            cards.append(_card(f"{s['kind']} {d} median hold",
                               _fmt_dur(x["median"], bm),
                               "neg" if x["pct_le_6"] >= 40 else ""))
    cards_html = "".join(cards)

    labels = [f"{lo//1}-{hi if hi < 10**8 else '∞'}" for (lo, hi, lbl) in _RUN_BUCKETS]
    labels = [lbl for (_, _, lbl) in _RUN_BUCKETS]
    sections = []
    for d in ("bull", "bear"):
        for kind in ("sma", "ema"):
            counts = _bucket_counts(runs_by_kind[kind][d])
            col = ["#1f9d55" if d == "bull" else "#e3342f"] * len(counts)
            sections.append((f"{kind.upper()} · {d} crossover hold-time distribution",
                             _svg_bars([float(c) for c in counts], col,
                                       labels=labels, fmt="{:.0f}", label_every=1)))
    charts_html = "".join(f'<section class="panel"><h3>{t}</h3>{svg}</section>'
                          for t, svg in sections)
    tfs = f"{cfg.base_tf}/{cfg.mid_tf}/{cfg.high_tf}"
    subtitle = (f"full-crossover persistence · {tfs} · {meta.get('start','?')} → "
                f"{meta.get('end','?')} · {meta.get('n_base','?')} bars · {source}")
    body = f'<section class="cards">{cards_html}</section>{charts_html}'
    return _PAGE.format(title=f"{cfg.symbol} · crossover persistence",
                        subtitle=subtitle, body=body)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Trend-filter predictiveness study")
    p.add_argument("--symbol", default="ES=F")
    p.add_argument("--preset", choices=list(Config.PRESETS), default="swing")
    p.add_argument("--sma-period", type=int, dest="sma_period")
    p.add_argument("--report", metavar="PATH")
    p.add_argument("--persistence", action="store_true",
                   help="measure how long the all-3 aligned state holds after a full crossover")
    p.add_argument("--synthetic", action="store_true")
    args = p.parse_args(argv)

    cfg = Config.preset(args.preset, symbol=args.symbol)
    if args.sma_period:
        cfg.sma_period = args.sma_period

    source = "yahoo"
    if args.synthetic:
        base = synthetic_series(n=4000)
        cfg.symbol = "SYNTH"
        source = "synthetic"
    else:
        try:
            base = load_base(cfg)
        except Exception as e:  # noqa: BLE001
            print(f"data load failed ({e}); using synthetic", flush=True)
            base = synthetic_series(n=4000)
            cfg.symbol = "SYNTH"
            source = "synthetic"

    meta = {"start": base.index[0].date(), "end": base.index[-1].date(), "n_base": len(base)}
    header = (f"\n{cfg.symbol} · {cfg.base_tf}/{cfg.mid_tf}/{cfg.high_tf} "
              f"· {meta['start']} → {meta['end']} · {len(base)} bars · {cfg.sma_period}-period MA")

    if args.persistence:
        summaries, runs_by_kind = [], {}
        for kind in ("sma", "ema"):
            s = persistence_summary(base, cfg, kind)
            for d in ("bull", "bear"):
                s[d]["_pct_time"] = s[d]["bars_total"] / len(base) * 100
            summaries.append(s)
            runs, _ = crossover_runs(base, cfg, kind)
            runs_by_kind[kind] = runs
        print(header + "\nFull-crossover persistence — all three timeframes aligned")
        print("=" * 104)
        print(format_persistence(summaries, cfg))
        if args.report:
            with open(args.report, "w") as f:
                f.write(build_persistence_report(summaries, runs_by_kind, cfg, meta, source))
            print(f"\nWrote visual persistence report -> {args.report}")
        return 0

    rows = run_study(base, cfg)
    print(header.replace("\n", "\nTrend study — ", 1))
    print("=" * 120)
    print(format_table(rows, cfg))
    if args.report:
        with open(args.report, "w") as f:
            f.write(build_study_report(rows, cfg, meta, source))
        print(f"\nWrote visual study -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
