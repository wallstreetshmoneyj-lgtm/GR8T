"""
INDEX SCREENER — cost, CAGR, standard deviation across every candidate.

Run in Claude Code on your machine:
    pip install pandas numpy requests
    python index_screener.py

-------------------------------------------------------------------------------
THE METHODOLOGY PROBLEM THIS SOLVES
-------------------------------------------------------------------------------
These funds have wildly different inception dates. XLE launched 1998, VOO 2010,
AVUV 2019. Comparing "CAGR" across them using each fund's full history is
meaningless: AVUV's number covers only a bull run, XLE's includes 2008.

So the script runs TWO kinds of passes:

  PASS 1 — ERA TABLES. Three fixed windows: 2000s (2000-2009), 2010s
           (2010-2019), 2020s (2020-present). Every fund appears in every
           table; a fund that didn't exist yet (or has under 24 months of
           data in the window) gets a blank row. A 'From' date later than
           the era start means the fund launched mid-era — partial window,
           read with care. Within one table, filled rows are comparable.

  PASS 2 — FULL HISTORY. Each fund's own max history (floored at 2000-01),
           with the start date printed next to it. Useful context, NOT
           comparable across rows.

Nothing before 2000-01 is used, even for funds whose data goes back further
(DIA, XLE, QQQ).

All returns are monthly, dividend-adjusted (total return). Volatility is
annualized by sqrt(12). Never compare these stdev figures to a number you
found on a website unless you know that site's sampling frequency — monthly
sampling structurally understates vol relative to daily.
-------------------------------------------------------------------------------
"""

import time
import numpy as np
import pandas as pd
import requests

PERIODS_PER_YEAR = 12
RF_ANNUAL = 0.0          # set to a real T-bill rate if you want honest Sharpes

ANALYSIS_START = "2000-01"   # nothing before this month is used, ever
MIN_MONTHS = 24              # blank a fund's row if it has less than this in a window

ERAS = [                     # (label, start, end) — end None = latest month
    ("2000s", "2000-01", "2009-12"),
    ("2010s", "2010-01", "2019-12"),
    ("2020s", "2020-01", None),
]


# =============================================================================
# UNIVERSE — expense ratios are HARDCODED. Verify each on the issuer page.
# Fees change; this list will go stale.
# =============================================================================
UNIVERSE = {
    # --- US broad market ---
    "VTI":  ("US total market",            0.03, "US broad"),
    "VOO":  ("S&P 500",                    0.03, "US broad"),
    "SPLG": ("S&P 500 (cheapest)",         0.02, "US broad"),
    "ITOT": ("US total market (iShares)",  0.03, "US broad"),
    "QQQ":  ("Nasdaq-100 (orig, 1999)",    0.20, "US broad"),
    "QQQM": ("Nasdaq-100",                 0.15, "US broad"),
    "ONEQ": ("Nasdaq Composite",           0.21, "US broad"),
    "DIA":  ("Dow 30 (price-weighted)",    0.16, "US broad"),
    "IWB":  ("Russell 1000",               0.15, "US broad"),
    "IWM":  ("Russell 2000 (small)",       0.19, "US broad"),
    "IJH":  ("S&P MidCap 400",             0.05, "US broad"),
    "IJR":  ("S&P SmallCap 600",           0.06, "US broad"),
    "VXF":  ("Extended mkt (VTI minus VOO)", 0.05, "US broad"),

    # --- Style ---
    "VUG":  ("Large growth",               0.04, "Style"),
    "SCHG": ("Large growth (Schwab)",      0.04, "Style"),
    "VTV":  ("Large value",                0.04, "Style"),
    "VBR":  ("Small value (Vanguard)",     0.07, "Style"),
    "VIOV": ("S&P 600 small value",        0.10, "Style"),
    "AVUV": ("Small value (Avantis)",      0.25, "Style"),

    # --- Factor ---
    "MTUM": ("Momentum",                   0.15, "Factor"),
    "QUAL": ("Quality",                    0.15, "Factor"),
    "USMV": ("Minimum volatility",         0.15, "Factor"),
    "SPLV": ("Low volatility",             0.25, "Factor"),
    "RSP":  ("S&P 500 equal weight",       0.20, "Factor"),
    "SCHD": ("Dividend growth + quality",  0.06, "Factor"),
    "VIG":  ("Dividend growth (10yr)",     0.05, "Factor"),
    "VYM":  ("High dividend yield",        0.06, "Factor"),

    # --- International ---
    "VT":   ("Total world incl US",        0.05, "International"),
    "VXUS": ("Total intl ex-US",           0.08, "International"),
    "VEA":  ("Developed ex-US (FTSE)",     0.03, "International"),
    "IDEV": ("Developed ex-US (MSCI)",     0.04, "International"),
    "EFA":  ("EAFE (MSCI)",                0.33, "International"),
    "VWO":  ("Emerging (FTSE, no Korea)",  0.06, "International"),
    "IEMG": ("Emerging (MSCI, has Korea)", 0.09, "International"),
    "AVEM": ("Emerging (Avantis)",         0.33, "International"),
    "VGK":  ("Europe",                     0.09, "International"),
    "AVDV": ("Intl small value",           0.36, "International"),

    # --- Sector, for your energy sleeve ---
    "XLE":  ("Energy (S&P 500 only)",      0.08, "Sector"),
    "VDE":  ("Energy (broad)",             0.09, "Sector"),
}


# =============================================================================
# DATA
# =============================================================================

def fetch_monthly(ticker, retries=3):
    """Monthly dividend-adjusted closes from Yahoo's public chart API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": "max", "interval": "1mo", "events": "div,split"}
    headers = {"User-Agent": "Mozilla/5.0"}

    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=20)
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            ts = pd.to_datetime(res["timestamp"], unit="s")
            adj = res["indicators"]["adjclose"][0]["adjclose"]
            s = pd.Series(adj, index=ts, name=ticker).dropna()
            s.index = s.index.to_period("M").to_timestamp("M")
            return s[~s.index.duplicated(keep="last")].iloc[:-1]  # drop partial month
        except Exception as e:
            if attempt == retries - 1:
                print(f"  FAILED {ticker}: {e}")
                return None
            time.sleep(2 ** attempt)


# =============================================================================
# METRICS
# =============================================================================

def cagr(r):
    return (1 + r).prod() ** (PERIODS_PER_YEAR / len(r)) - 1


def ann_stdev(r):
    return r.std(ddof=1) * np.sqrt(PERIODS_PER_YEAR)


def sharpe(r):
    sd = ann_stdev(r)
    return (cagr(r) - RF_ANNUAL) / sd if sd > 0 else np.nan


def max_dd(r):
    w = (1 + r).cumprod()
    return (w / w.cummax() - 1).min()


def stats_row(ticker, rets):
    name, fee, cat = UNIVERSE[ticker]
    c = cagr(rets)
    sd = ann_stdev(rets)
    return {
        "Ticker": ticker,
        "Category": cat,
        "Tracks": name,
        "Fee %": fee,
        "CAGR %": round(c * 100, 2),
        "StDev %": round(sd * 100, 2),
        "Return/Risk": round(c / sd, 2) if sd > 0 else np.nan,
        "MaxDD %": round(max_dd(rets) * 100, 1),
        "Net CAGR %": round((c - fee / 100) * 100, 2),
        "Start": rets.index[0].strftime("%Y-%m"),
        "Months": len(rets),
    }


ERA_COLS = ["Ticker", "Category", "Tracks", "Fee %", "CAGR %", "StDev %",
            "Return/Risk", "MaxDD %", "Net CAGR %", "From", "Months"]


def era_row(ticker, rets):
    """Stats for one fund in one era window; blank metrics if it wasn't there."""
    if len(rets) < MIN_MONTHS:
        name, fee, cat = UNIVERSE[ticker]
        return {"Ticker": ticker, "Category": cat, "Tracks": name, "Fee %": fee,
                "CAGR %": np.nan, "StDev %": np.nan, "Return/Risk": np.nan,
                "MaxDD %": np.nan, "Net CAGR %": np.nan, "From": "", "Months": ""}
    d = stats_row(ticker, rets)
    d["From"] = d.pop("Start")
    return d


# =============================================================================
# RUN
# =============================================================================

def main():
    print(f"Fetching {len(UNIVERSE)} tickers from Yahoo...\n")
    series = {}
    for t in UNIVERSE:
        s = fetch_monthly(t)
        if s is not None and len(s) > 24:
            series[t] = s
            print(f"  {t:6s} {len(s):>4d} months from {s.index[0]:%Y-%m}")
        time.sleep(0.3)

    px = pd.DataFrame(series)

    # Returns computed on full data, then floored at 2000-01 so a fund with
    # older prices still gets its January 2000 return.
    rets_all = px.pct_change()
    rets_all = rets_all[rets_all.index >= pd.Period(ANALYSIS_START).to_timestamp("M")]

    # ---------- PASS 1: era tables ----------
    saved = []
    for label, start, end in ERAS:
        s = pd.Period(start).to_timestamp("M")
        e = rets_all.index[-1] if end is None else pd.Period(end).to_timestamp("M")
        sub = rets_all.loc[s:e]
        tbl = pd.DataFrame([era_row(t, sub[t].dropna()) for t in px.columns])
        tbl = tbl[ERA_COLS].sort_values(["Category", "Return/Risk"],
                                        ascending=[True, False], na_position="last")
        tbl = tbl.fillna("")

        print("\n" + "=" * 118)
        print(f"PASS 1 — ERA: {label}  {s:%Y-%m} to {e:%Y-%m}.  Blank row = fund"
              f" didn't exist yet (or <{MIN_MONTHS} months of data in this era).")
        print(f"A 'From' later than {s:%Y-%m} = launched mid-era, partial window.")
        print("=" * 118)
        print(tbl.to_string(index=False))

        fname = f"screener_{label}.csv"
        tbl.to_csv(fname, index=False)
        saved.append(fname)

    # ---------- PASS 2: full history ----------
    rows = []
    for t in px.columns:
        r = rets_all[t].dropna()
        if len(r) >= MIN_MONTHS:
            rows.append(stats_row(t, r))
    tbl2 = pd.DataFrame(rows).sort_values(["Category", "Return/Risk"],
                                          ascending=[True, False])

    print("\n" + "=" * 118)
    print("PASS 2 — FULL HISTORY PER FUND (floored at 2000-01)."
          "  NOT COMPARABLE ACROSS ROWS — different start dates.")
    print("=" * 118)
    print(tbl2.to_string(index=False))

    tbl2.to_csv("screener_full_history.csv", index=False)
    saved.append("screener_full_history.csv")
    print("\nSaved: " + ", ".join(saved))
    print("\nREMINDERS")
    print("  - StDev is monthly-sampled, annualized by sqrt(12). Understates vs daily.")
    print("  - Fee column is hardcoded. Verify on the issuer page before buying.")
    print("  - CAGR is already net of fees (adjusted close reflects NAV after ER).")
    print("    'Net CAGR' double-counts the fee — use it only as a forward-looking haircut.")


if __name__ == "__main__":
    main()
