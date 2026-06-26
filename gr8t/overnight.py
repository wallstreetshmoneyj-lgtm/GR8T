"""GR8T Overnight — the strategy that actually works.

After disproving SMC, intraday momentum, and gap-continuation on S&P intraday,
the data pointed somewhere specific: the equity risk premium is almost entirely
an OVERNIGHT phenomenon. Over 30 years of SPY, holding only close->open captured
~all of the gains at a HIGHER Sharpe than buy-and-hold, while the open->close
session was essentially flat. This module backtests capturing it.

  * Long from the cash close to the next cash open (hold overnight), flat during
    the day. One round-trip per day (MOC buy, MOO sell), so even a couple bps of
    cost is small against the ~3 bps/day overnight drift.
  * Compared against intraday-only and buy-and-hold so the asymmetry is obvious.

Not intraday by design — that is the point: on a liquid index the intraday
session is efficient and flat; the durable edge is overnight. An ES trader
captures it by being long the Globex/overnight session and flat in RTH.

    python -m gr8t.overnight --symbol SPY --report overnight.html
"""
from __future__ import annotations

import argparse
import numpy as np
import pandas as pd

from .data import fetch_yahoo


def legs(df: pd.DataFrame, cost_bps: float = 1.0) -> pd.DataFrame:
    df = df.dropna().copy()
    o, c = df["open"].to_numpy(float), df["close"].to_numpy(float)
    pc = np.roll(c, 1)
    f = pd.DataFrame(index=df.index[1:])
    f["overnight"] = (o / pc - 1)[1:]
    f["intraday"] = (c / o - 1)[1:]
    f["buyhold"] = (c / pc - 1)[1:]
    f["overnight_net"] = f["overnight"] - cost_bps / 1e4   # one round-trip/day
    return f


def _stats(r: np.ndarray) -> dict:
    eq = np.cumprod(1 + r)
    peak = np.maximum.accumulate(eq)
    yrs = len(r) / 252
    return {
        "total_pct": float((eq[-1] - 1) * 100),
        "cagr_pct": float(eq[-1] ** (1 / yrs) - 1) * 100,
        "sharpe": float(r.mean() / r.std() * np.sqrt(252)) if r.std() else 0.0,
        "max_dd_pct": float((1 - eq / peak).max() * 100),
        "win_pct": float((r > 0).mean() * 100),
        "mean_bps": float(r.mean() * 1e4),
    }


def summarize(f: pd.DataFrame) -> dict:
    return {k: _stats(f[k].to_numpy()) for k in ("overnight_net", "intraday", "buyhold")}


def fmt(summary: dict) -> str:
    cols = [("overnight_net", "OVERNIGHT (net)"), ("intraday", "intraday"), ("buyhold", "buy & hold")]
    rows = [("Total return", "total_pct", "{:+.0f}%"), ("CAGR", "cagr_pct", "{:+.1f}%"),
            ("Sharpe (ann.)", "sharpe", "{:.2f}"), ("Max drawdown", "max_dd_pct", "{:.1f}%"),
            ("Win rate", "win_pct", "{:.1f}%"), ("Mean / day", "mean_bps", "{:+.1f} bps")]
    out = [f"  {'metric':16}" + "".join(f"{lbl:>18}" for _, lbl in cols)]
    out.append("  " + "-" * (16 + 18 * len(cols)))
    for label, key, f in rows:
        out.append(f"  {label:16}" + "".join(f"{f.format(summary[c][key]):>18}" for c, _ in cols))
    return "\n".join(out)


def by_year(f: pd.DataFrame) -> pd.DataFrame:
    g = f.assign(year=f.index.year).groupby("year")
    return g.apply(lambda d: pd.Series({
        "overnight%": (np.prod(1 + d["overnight_net"]) - 1) * 100,
        "intraday%": (np.prod(1 + d["intraday"]) - 1) * 100,
        "buyhold%": (np.prod(1 + d["buyhold"]) - 1) * 100,
    }), include_groups=False)


def build_report(f, summary, yr, symbol, source) -> str:
    from .report import _svg_line, _svg_bars, _PAGE, _card
    s = summary["overnight_net"]
    sign = lambda x: "pos" if x > 0 else "neg"
    cards = [
        _card("Overnight Sharpe", f"{s['sharpe']:.2f}", sign(s["sharpe"] - 0.5)),
        _card("Overnight CAGR", f"{s['cagr_pct']:+.1f}%", "pos"),
        _card("Overnight max DD", f"{s['max_dd_pct']:.1f}%", "neg"),
        _card("Intraday Sharpe", f"{summary['intraday']['sharpe']:.2f}", "neg"),
        _card("Buy&hold Sharpe", f"{summary['buyhold']['sharpe']:.2f}"),
        _card("Overnight win%", f"{s['win_pct']:.1f}%"),
    ]
    eq_on = list(np.cumprod(1 + f["overnight_net"].to_numpy()))
    eq_bh = list(np.cumprod(1 + f["buyhold"].to_numpy()))
    eq_id = list(np.cumprod(1 + f["intraday"].to_numpy()))
    yrs = [str(int(y)) for y in yr.index]
    onb = [round(float(x), 1) for x in yr["overnight%"]]
    idb = [round(float(x), 1) for x in yr["intraday%"]]
    sec = [
        ("Overnight equity (compounded, net of cost)", _svg_line([round(x, 3) for x in eq_on], color="#1f9d55", baseline=1.0, fmt="{:.0f}")),
        ("Buy & hold equity", _svg_line([round(x, 3) for x in eq_bh], color="#8b97a7", baseline=1.0, fmt="{:.0f}")),
        ("Intraday equity (flat for 30 years)", _svg_line([round(x, 3) for x in eq_id], color="#e3342f", baseline=1.0, fmt="{:.2f}")),
        ("Overnight return % by year", _svg_bars(onb, ["#1f9d55" if v >= 0 else "#e3342f" for v in onb], labels=yrs, fmt="{:+.0f}", label_every=max(1, len(yrs)//12))),
        ("Intraday return % by year", _svg_bars(idb, ["#1f9d55" if v >= 0 else "#e3342f" for v in idb], labels=yrs, fmt="{:+.0f}", label_every=max(1, len(yrs)//12))),
    ]
    charts = "".join(f"<section class='panel'><h3>{t}</h3>{svg}</section>" for t, svg in sec)
    subtitle = (f"overnight (close→open) vs intraday vs buy&hold · {symbol} daily · "
                f"{f.index[0].date()} → {f.index[-1].date()} · {len(f)} days · {source}")
    body = f"<section class='cards'>{''.join(cards)}</section>{charts}"
    return _PAGE.format(title=f"{symbol} · overnight edge", subtitle=subtitle, body=body)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Overnight vs intraday edge")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--range", default="30y")
    p.add_argument("--cost-bps", type=float, default=1.0)
    p.add_argument("--report", metavar="PATH")
    args = p.parse_args(argv)

    df = fetch_yahoo(args.symbol, interval="1d", rng=args.range)
    f = legs(df, cost_bps=args.cost_bps)
    summary = summarize(f)
    yr = by_year(f)
    print(f"\nGR8T Overnight — {args.symbol} daily · {f.index[0].date()} → {f.index[-1].date()} "
          f"· {len(f)} days · cost {args.cost_bps}bp/day")
    print("=" * 70)
    print(fmt(summary))
    if args.report:
        with open(args.report, "w") as fh:
            fh.write(build_report(f, summary, yr, args.symbol, "yahoo daily"))
        print(f"\nWrote visual report -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
