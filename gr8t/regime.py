"""Out-of-sample / regime robustness test for the lean strategy.

Uses GitHub 1-minute OANDA SPX500 data (an ES proxy) to run the leanest config
that tested best in the lab — pattern entry at any same-/mixed-colour gap (5m/
15m/1h POIs), 1h-SMA trend, 1.5-ATR stop, fixed 1:2 target, no same-colour /
multi-TF / order-flow filters — across distinct market regimes, including real
downtrends that Yahoo's 60-day window never let us test. Splits long vs short to
see whether the short side works once there is an actual downtrend.

    python -m gr8t.regime --report regime.html
"""
from __future__ import annotations

import argparse
import numpy as np
import pandas as pd

from .config import Config
from .data import load_github, synthetic_series
from .stats import compute_stats
from .poi_lab import run_poi_lab, _exp_cost

# (label, start 'YYYY-MM', end, one-line character)
WINDOWS = [
    ("2014 H1 uptrend", "2014-01", "2014-06", "steady bull"),
    ("2015 H2 correction", "2015-08", "2015-10", "China selloff + chop"),
    ("2011 EU crisis", "2011-07", "2011-09", "sharp bear (~-15%)"),
    ("2018 Q4 bear", "2018-10", "2018-12", "bear (~-14%)"),
    ("2017 H1 grind", "2017-01", "2017-06", "low-vol bull"),
]


def _row(ts, cfg, cost=0.5):
    s = compute_stats(ts, cfg)
    if not s.get("trades"):
        return None
    e5, _ = _exp_cost(ts, cost)
    return dict(n=s["trades"], win=s["win_rate"] * 100, e0=s["expectancy_r"],
                e5=e5, pf=s["profit_factor"], total=s["total_r"])


def run_regimes(symbol="SPX500", windows=WINDOWS, synthetic=False):
    out = {}
    for label, start, end, _ in windows:
        try:
            base = synthetic_series(n=6000) if synthetic else load_github(symbol, start, end)
        except Exception as e:  # noqa: BLE001
            print(f"  [skip {label}: {e}]")
            continue
        cfg = Config.preset("intraday", symbol=symbol)
        trades, _ = run_poi_lab(base, cfg, "high", entry_mode="pattern",
                                stop_atr_mult=1.5, target_rr=2.0)
        ret = (base["close"].iloc[-1] / base["close"].iloc[0] - 1) * 100
        out[label] = {"trades": trades, "ret": ret,
                      "span": (str(base.index[0].date()), str(base.index[-1].date()))}
    return out


def format_regimes(results, cfg) -> str:
    lines = ["  Lean config (1h trend · all gaps · 1.5 ATR stop · 1:2 target) across regimes",
             f"  {'regime':22}{'mkt%':>7} {'n':>5} {'win%':>6} {'exp@0':>7} {'exp@0.5pt':>9} "
             f"{'PF':>5} {'totalR':>7}"]
    lines.append("  " + "-" * 80)
    pooled = []
    for label, d in results.items():
        ts = d["trades"]
        pooled += ts
        m = _row(ts, cfg)
        if not m:
            lines.append(f"  {label:22}{d['ret']:+6.1f}%  n=0")
            continue
        lines.append(f"  {label:22}{d['ret']:+6.1f}% {m['n']:5d} {m['win']:6.1f} "
                     f"{m['e0']:+7.3f} {m['e5']:+9.3f} {m['pf']:5.2f} {m['total']:+7.1f}")
    pm = _row(pooled, cfg)
    if pm:
        lines.append("  " + "-" * 80)
        lines.append(f"  {'POOLED (all regimes)':22}{'':7} {pm['n']:5d} {pm['win']:6.1f} "
                     f"{pm['e0']:+7.3f} {pm['e5']:+9.3f} {pm['pf']:5.2f} {pm['total']:+7.1f}")

    # long vs short — the key question a downtrend finally answers
    lines.append("\n  Long vs short (expectancy @0.5pt / n)")
    lines.append(f"  {'regime':22}{'LONG':>18}{'SHORT':>18}")
    for label, d in results.items():
        longs = [t for t in d["trades"] if t.direction == "bull"]
        shorts = [t for t in d["trades"] if t.direction == "bear"]
        lm, sm = _row(longs, cfg), _row(shorts, cfg)
        ls = f"{lm['e5']:+.3f}/{lm['n']}" if lm else "—"
        ss = f"{sm['e5']:+.3f}/{sm['n']}" if sm else "—"
        lines.append(f"  {label:22}{ls:>18}{ss:>18}")
    return "\n".join(lines)


def build_report(results, cfg, source) -> str:
    from .report import _svg_bars, _PAGE, _card
    labels = list(results.keys())
    e5 = [round((_row(results[k]["trades"], cfg) or {"e5": 0})["e5"], 3) for k in labels]
    rets = [round(results[k]["ret"], 1) for k in labels]
    pooled = [t for k in labels for t in results[k]["trades"]]
    pm = _row(pooled, cfg) or {"e5": 0, "n": 0}

    cards = [
        _card("pooled expectancy @0.5pt", f"{pm['e5']:+.3f}R", "pos" if pm["e5"] > 0 else "neg"),
        _card("pooled trades", f"{pm['n']}"),
        _card("regimes positive @0.5pt", f"{sum(1 for v in e5 if v > 0)}/{len(e5)}"),
        _card("data", "GitHub OANDA SPX500 1m"),
    ]
    short_e5 = []
    for k in labels:
        sm = _row([t for t in results[k]["trades"] if t.direction == "bear"], cfg)
        short_e5.append(round(sm["e5"], 3) if sm else 0.0)
    long_e5 = []
    for k in labels:
        lm = _row([t for t in results[k]["trades"] if t.direction == "bull"], cfg)
        long_e5.append(round(lm["e5"], 3) if lm else 0.0)

    sec = [
        ("Expectancy @0.5pt by regime",
         _svg_bars(e5, ["#1f9d55" if v >= 0 else "#e3342f" for v in e5], labels=labels, fmt="{:+.2f}", label_every=1)),
        ("Market return % by regime",
         _svg_bars(rets, ["#1f9d55" if v >= 0 else "#e3342f" for v in rets], labels=labels, fmt="{:+.0f}", label_every=1)),
        ("LONG expectancy @0.5pt by regime",
         _svg_bars(long_e5, ["#1f9d55" if v >= 0 else "#e3342f" for v in long_e5], labels=labels, fmt="{:+.2f}", label_every=1)),
        ("SHORT expectancy @0.5pt by regime",
         _svg_bars(short_e5, ["#1f9d55" if v >= 0 else "#e3342f" for v in short_e5], labels=labels, fmt="{:+.2f}", label_every=1)),
    ]
    charts = "".join(f"<section class='panel'><h3>{t}</h3>{svg}</section>" for t, svg in sec)
    subtitle = (f"regime robustness · lean config (1h trend, all gaps, 1.5 ATR, 1:2) · "
                f"SPX500 1m via GitHub · {source}")
    return _PAGE.format(title=f"{cfg.symbol} · regime test", subtitle=subtitle,
                        body=f"<section class='cards'>{''.join(cards)}</section>{charts}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Regime robustness test")
    p.add_argument("--symbol", default="SPX500")
    p.add_argument("--report", metavar="PATH")
    p.add_argument("--synthetic", action="store_true")
    args = p.parse_args(argv)

    print(f"\nRegime robustness — {args.symbol} (GitHub OANDA 1m) · lean exp-3 config")
    print("=" * 92)
    results = run_regimes(args.symbol, synthetic=args.synthetic)
    if not results:
        print("no regimes loaded")
        return 1
    cfg = Config.preset("intraday", symbol=args.symbol)
    print(format_regimes(results, cfg))
    if args.report:
        with open(args.report, "w") as f:
            f.write(build_report(results, cfg, "synthetic" if args.synthetic else "github"))
        print(f"\nWrote visual regime report -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
