"""Command-line backtest runner.

Examples:
    python -m gr8t.cli --symbol SPY --period 60d
    python -m gr8t.cli --symbol NQ=F --period 30d --atr-mult 1.5
    python -m gr8t.cli --synthetic            # offline, deterministic demo
"""
from __future__ import annotations

import argparse
import json
import sys

from .config import Config
from .data import load_base, synthetic_series, resample
from .backtest import Backtester
from .stats import compute_stats, format_stats


def build_config(args) -> Config:
    cfg = Config()
    for k, v in vars(args).items():
        if v is None:
            continue
        key = k.replace("-", "_")
        if hasattr(cfg, key):
            setattr(cfg, key, v)
    return cfg


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="GR8T strategy backtester")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--period", default="60d")
    p.add_argument("--atr-period", type=int, dest="atr_period")
    p.add_argument("--atr-mult", type=float, dest="atr_mult")
    p.add_argument("--sma-period", type=int, dest="sma_period")
    p.add_argument("--risk-per-trade", type=float, dest="risk_per_trade")
    p.add_argument("--stop-mode", choices=["poi", "signal"], dest="stop_mode")
    p.add_argument("--no-mtf", action="store_true", help="disable multi-TF requirement")
    p.add_argument("--preset", choices=list(Config.PRESETS),
                   help="timeframe preset: intraday (5m/15m/1h, 60d) or swing (1h/4h/1d, ~2y)")
    p.add_argument("--report", metavar="PATH", help="write a visual HTML report")
    p.add_argument("--synthetic", action="store_true", help="use offline synthetic data")
    p.add_argument("--offline", action="store_true", help="use cached data only")
    p.add_argument("--json", action="store_true", help="emit stats as JSON")
    args = p.parse_args(argv)

    if args.preset:
        base = Config.preset(args.preset)
        for k, v in vars(args).items():
            key = k.replace("-", "_")
            if v is not None and hasattr(base, key) and key not in (
                    "base_tf", "mid_tf", "high_tf", "period"):
                setattr(base, key, v)
        cfg = base
    else:
        cfg = build_config(args)
    if args.no_mtf:
        cfg.require_mtf = False

    source = "yahoo"
    if args.synthetic:
        base = synthetic_series(n=1500)
        cfg.symbol = "SYNTH"
        source = "synthetic"
    else:
        try:
            base = load_base(cfg, offline=args.offline)
        except Exception as e:  # noqa: BLE001
            print(f"Data load failed ({e}); falling back to --synthetic.", file=sys.stderr)
            base = synthetic_series(n=1500)
            cfg.symbol = "SYNTH"
            source = "synthetic"

    result = Backtester(base, cfg).run()
    result.set_exit_times()
    stats = compute_stats(result.trades, cfg)

    if args.report:
        from .report import build_report
        meta = {"start": base.index[0].date(), "end": base.index[-1].date(),
                "n_base": len(base)}
        with open(args.report, "w") as f:
            f.write(build_report(result, cfg, source=source, meta=meta))
        print(f"Wrote visual report -> {args.report}")

    if args.json:
        print(json.dumps(stats, indent=2, default=str))
        return 0

    print(f"\nGR8T backtest — {cfg.symbol}  ({len(base)} x {cfg.base_tf} bars,"
          f" {base.index[0].date()} → {base.index[-1].date()})")
    print(f"Resampled: {len(resample(base, cfg.mid_tf))} x {cfg.mid_tf},"
          f" {len(resample(base, cfg.high_tf))} x {cfg.high_tf}")
    print("-" * 64)
    print(format_stats(stats))
    print("-" * 64)
    if result.trades:
        print("Last trades:")
        for t in result.trades[-5:]:
            print(f"  {t.entry_time:%Y-%m-%d %H:%M}  {t.direction:4s} "
                  f"{t.pattern:18s} {t.poi_tf:>6s}  {t.r_multiple:+.2f}R  "
                  f"[{t.exit_reason}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
