"""Flask web UI for the GR8T backtester.

Run:  python -m webui.app      (then open http://127.0.0.1:5000)

Endpoints:
  GET  /                -> the single-page chart UI
  POST /api/backtest    -> run a backtest, return candles + markers + stats
  GET  /api/symbols     -> a few suggested symbols
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request, render_template

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gr8t.config import Config
from gr8t.data import load_base, synthetic_series, resample
from gr8t.indicators import sma
from gr8t.backtest import Backtester
from gr8t.stats import compute_stats

app = Flask(__name__)

_LWC_URL = ("https://unpkg.com/lightweight-charts@4.1.3/dist/"
            "lightweight-charts.standalone.production.js")
_LWC_PATH = Path(__file__).resolve().parent / "static" / "lightweight-charts.js"


def ensure_assets() -> None:
    """Vendor the charting library on first launch so the UI has no hard CDN
    dependency at runtime. Best-effort: the page also falls back to the CDN."""
    if _LWC_PATH.exists() and _LWC_PATH.stat().st_size > 1000:
        return
    try:
        import requests
        r = requests.get(_LWC_URL, timeout=60, headers={"User-Agent": "GR8T"})
        r.raise_for_status()
        _LWC_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LWC_PATH.write_text(r.text)
        print(f"[gr8t] cached charting library -> {_LWC_PATH}")
    except Exception as e:  # noqa: BLE001
        print(f"[gr8t] could not vendor charting library ({e}); page uses CDN.")

SUGGESTED = [
    {"symbol": "SPY", "label": "S&P 500 ETF"},
    {"symbol": "QQQ", "label": "Nasdaq 100 ETF"},
    {"symbol": "ES=F", "label": "S&P 500 futures"},
    {"symbol": "NQ=F", "label": "Nasdaq futures"},
    {"symbol": "AAPL", "label": "Apple"},
    {"symbol": "NVDA", "label": "Nvidia"},
]

_SHORT_TF = {"60min": "1h", "15min": "15m", "5min": "5m"}


def _epoch(ts: pd.Timestamp) -> int:
    return int(pd.Timestamp(ts).timestamp())


def _candles(df: pd.DataFrame) -> list[dict]:
    out = []
    for t, row in df.iterrows():
        out.append({
            "time": _epoch(t),
            "open": round(float(row["open"]), 4),
            "high": round(float(row["high"]), 4),
            "low": round(float(row["low"]), 4),
            "close": round(float(row["close"]), 4),
        })
    return out


def _line(series: pd.Series) -> list[dict]:
    out = []
    for t, v in series.dropna().items():
        out.append({"time": _epoch(t), "value": round(float(v), 4)})
    return out


def build_payload(cfg: Config, base: pd.DataFrame, source: str) -> dict:
    result = Backtester(base, cfg).run()
    result.set_exit_times()
    stats = compute_stats(result.trades, cfg)

    sma_series = sma(base["close"], cfg.sma_period)

    markers = []
    trades = []
    seen_eq_times = set()
    equity = []
    for tr in result.trades:
        is_bull = tr.direction == "bull"
        markers.append({
            "time": _epoch(tr.entry_time),
            "position": "belowBar" if is_bull else "aboveBar",
            "color": "#1f9d55" if is_bull else "#e3342f",
            "shape": "arrowUp" if is_bull else "arrowDown",
            "text": f"{_SHORT_TF.get(tr.poi_tf, tr.poi_tf)} {tr.pattern.split('_')[0]}",
        })
        if tr.exit_time is not None:
            markers.append({
                "time": _epoch(tr.exit_time),
                "position": "aboveBar" if is_bull else "belowBar",
                "color": "#8795a1",
                "shape": "circle",
                "text": f"{tr.r_multiple:+.2f}R",
            })
            et = _epoch(tr.exit_time)
            while et in seen_eq_times:
                et += 1
            seen_eq_times.add(et)
            equity.append({"time": et, "value": round(float(tr.equity_after), 2)})
        trades.append({
            "entry_unix": _epoch(tr.entry_time),
            "exit_unix": _epoch(tr.exit_time) if tr.exit_time is not None else None,
            "entry_time": pd.Timestamp(tr.entry_time).strftime("%Y-%m-%d %H:%M"),
            "exit_time": (pd.Timestamp(tr.exit_time).strftime("%Y-%m-%d %H:%M")
                          if tr.exit_time is not None else "—"),
            "direction": tr.direction,
            "pattern": tr.pattern,
            "poi_tf": _SHORT_TF.get(tr.poi_tf, tr.poi_tf),
            "poi_lower": round(tr.poi_lower if hasattr(tr, "poi_lower") else 0, 4),
            "entry_price": round(tr.entry_price, 4),
            "init_stop": round(tr.init_stop, 4),
            "exit_price": round(tr.exit_price, 4),
            "r": round(tr.r_multiple, 3),
            "reason": tr.exit_reason,
            "reached_be": tr.reached_be,
        })

    # attach POI zone bounds (kept on the Signal, matched by entry index)
    sig_by_index = {s.index: s for s in result.signals}
    for tr_dict, tr in zip(trades, result.trades):
        sig = sig_by_index.get(tr.entry_index)
        if sig is not None:
            tr_dict["poi_lower"] = round(float(sig.poi.lower), 4)
            tr_dict["poi_upper"] = round(float(sig.poi.upper), 4)
            tr_dict["poc"] = round(float(sig.poc), 4) if sig.poc is not None else None
            tr_dict["n_candidates"] = sig.n_candidates

    markers.sort(key=lambda m: m["time"])
    return {
        "ok": True,
        "source": source,
        "symbol": cfg.symbol,
        "bars": _candles(base),
        "sma": _line(sma_series),
        "sma_period": cfg.sma_period,
        "markers": markers,
        "trades": trades,
        "equity": equity,
        "stats": stats,
        "meta": {
            "n_base": len(base),
            "n_mid": len(resample(base, cfg.mid_tf)),
            "n_high": len(resample(base, cfg.high_tf)),
            "start": pd.Timestamp(base.index[0]).strftime("%Y-%m-%d"),
            "end": pd.Timestamp(base.index[-1]).strftime("%Y-%m-%d"),
        },
    }


@app.route("/")
def index():
    ensure_assets()
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.route("/api/symbols")
def symbols():
    return jsonify(SUGGESTED)


@app.route("/api/backtest", methods=["POST"])
def backtest():
    try:
        params = request.get_json(force=True) or {}
        cfg = Config.from_dict(params)
        use_synth = bool(params.get("synthetic"))
        source = "synthetic"
        if use_synth:
            base = synthetic_series(n=1500)
            cfg.symbol = "SYNTH"
        else:
            try:
                base = load_base(cfg)
                source = "yahoo"
            except Exception as e:  # noqa: BLE001
                base = synthetic_series(n=1500)
                cfg.symbol = "SYNTH"
                source = f"synthetic (live fetch failed: {e})"
        payload = build_payload(cfg, base, source)
        payload["config"] = cfg.to_dict()
        return jsonify(payload)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
